"""Table-driven tests for music URL parsing.

Deliberately plain `unittest` with no Django import, so this runs standalone:

    cd RideTunes/rideTunes && python -m unittest music.tests.test_parsers -v

Every URL form here is one a real share sheet produces. The cases marked
REGRESSION are ones the previous implementation (views.py:105-137) got wrong.
"""

import unittest

from resolvers import parse_url, is_short_link, app_url_for, web_url_for
from resolvers.errors import (
    MalformedURL,
    NeedsExpansion,
    UnsupportedEntity,
    UnsupportedURL,
)
from resolvers.types import EntityKind, Service

# Real-world identifiers, correct shapes: Spotify 22-char base62,
# Apple numeric, YouTube 11-char.
SP = "6rqhFgbbKwnb9MLmUQDhG6"
AP_SONG = "1440857785"
AP_ALBUM = "1440857781"
YT = "dQw4w9WgXcQ"


class ParseSpotify(unittest.TestCase):
    def test_accepted_forms(self):
        for url in [
            f"https://open.spotify.com/track/{SP}",
            f"https://open.spotify.com/track/{SP}?si=abc123def456",
            f"http://open.spotify.com/track/{SP}",
            f"https://open.spotify.com/track/{SP}/",
            f"open.spotify.com/track/{SP}",                    # scheme-less paste
            f"  https://open.spotify.com/track/{SP}  ",         # stray whitespace
            f"https://OPEN.SPOTIFY.COM/track/{SP}",             # host casing
            f"https://open.spotify.com/intl-de/track/{SP}",     # REGRESSION: locale prefix
            f"https://open.spotify.com/intl-pt/track/{SP}?si=x",
            f"https://open.spotify.com/embed/track/{SP}",
            f"spotify:track:{SP}",                              # REGRESSION: URI form
        ]:
            with self.subTest(url=url):
                ref = parse_url(url)
                self.assertEqual(ref.service, Service.SPOTIFY)
                self.assertEqual(ref.kind, EntityKind.TRACK)
                self.assertEqual(ref.id, SP)

    def test_collections_rejected_with_kind(self):
        for path, kind in [
            ("album", EntityKind.ALBUM),
            ("playlist", EntityKind.PLAYLIST),
            ("artist", EntityKind.ARTIST),
            ("episode", EntityKind.PODCAST),
        ]:
            with self.subTest(path=path):
                # REGRESSION: these all used to come back as if they were tracks.
                with self.assertRaises(UnsupportedEntity) as cm:
                    parse_url(f"https://open.spotify.com/{path}/{SP}")
                self.assertEqual(cm.exception.kind, kind)

    def test_bad_ids_rejected(self):
        for bad in ["tooshort", SP + "extra", "!!!!!!!!!!!!!!!!!!!!!!"]:
            with self.subTest(bad=bad):
                with self.assertRaises(MalformedURL):
                    parse_url(f"https://open.spotify.com/track/{bad}")

    def test_short_links_signal_expansion(self):
        # REGRESSION: silently dropped before, and this is Spotify's share-sheet default.
        for url in ["https://spotify.link/aBcDeFg", "https://spotify.app.link/xYz123"]:
            with self.subTest(url=url):
                self.assertTrue(is_short_link(url))
                with self.assertRaises(NeedsExpansion):
                    parse_url(url)

    def test_full_links_are_not_short_links(self):
        self.assertFalse(is_short_link(f"https://open.spotify.com/track/{SP}"))


class ParseApple(unittest.TestCase):
    def test_album_plus_i_returns_the_song_not_the_album(self):
        """THE regression. Apple's share sheet emits this form for one song, and
        the old parser returned the album id from the path."""
        ref = parse_url(
            f"https://music.apple.com/us/album/blinding-lights/{AP_ALBUM}?i={AP_SONG}"
        )
        self.assertEqual(ref.service, Service.APPLE)
        self.assertEqual(ref.kind, EntityKind.TRACK)
        self.assertEqual(ref.id, AP_SONG)
        self.assertNotEqual(ref.id, AP_ALBUM)
        self.assertEqual(ref.storefront, "us")

    def test_i_wins_with_extra_query_params(self):
        ref = parse_url(
            f"https://music.apple.com/gb/album/x/{AP_ALBUM}?i={AP_SONG}&uo=4&app=music"
        )
        self.assertEqual(ref.id, AP_SONG)
        self.assertEqual(ref.storefront, "gb")

    def test_song_forms(self):
        for url, sf in [
            (f"https://music.apple.com/us/song/blinding-lights/{AP_SONG}", "us"),
            (f"https://music.apple.com/de/song/x/{AP_SONG}", "de"),
            (f"https://music.apple.com/jp/song/{AP_SONG}", "jp"),       # slugless
            (f"https://music.apple.com/song/x/{AP_SONG}", "us"),         # no storefront -> default
        ]:
            with self.subTest(url=url):
                ref = parse_url(url)
                self.assertEqual(ref.id, AP_SONG)
                self.assertEqual(ref.storefront, sf)

    def test_legacy_itunes_host(self):
        ref = parse_url(f"https://itunes.apple.com/us/album/x/{AP_ALBUM}?i={AP_SONG}")
        self.assertEqual(ref.service, Service.APPLE)
        self.assertEqual(ref.id, AP_SONG)

    def test_bare_album_rejected(self):
        with self.assertRaises(UnsupportedEntity) as cm:
            parse_url(f"https://music.apple.com/us/album/blinding-lights/{AP_ALBUM}")
        self.assertEqual(cm.exception.kind, EntityKind.ALBUM)

    def test_playlist_rejected(self):
        with self.assertRaises(UnsupportedEntity) as cm:
            parse_url("https://music.apple.com/us/playlist/chill/pl.u-abc123")
        self.assertEqual(cm.exception.kind, EntityKind.PLAYLIST)

    def test_bad_i_param_rejected(self):
        with self.assertRaises(MalformedURL):
            parse_url(f"https://music.apple.com/us/album/x/{AP_ALBUM}?i=notanumber")

    def test_storefront_is_required_on_refs(self):
        self.assertIsNotNone(parse_url(f"https://music.apple.com/fr/song/x/{AP_SONG}").storefront)


class ParseYouTube(unittest.TestCase):
    def test_accepted_forms(self):
        for url in [
            f"https://www.youtube.com/watch?v={YT}",
            f"https://youtube.com/watch?v={YT}",
            f"https://m.youtube.com/watch?v={YT}",
            f"https://music.youtube.com/watch?v={YT}",
            f"https://music.youtube.com/watch?v={YT}&list=PLabc&index=2",  # song *from* a playlist
            f"https://youtu.be/{YT}",                                       # REGRESSION
            f"https://youtu.be/{YT}?t=42",                                  # REGRESSION
            f"https://youtu.be/{YT}?si=xyz",
            f"https://www.youtube.com/shorts/{YT}",                         # REGRESSION
            f"https://www.youtube.com/embed/{YT}",
            f"https://www.youtube.com/v/{YT}",
        ]:
            with self.subTest(url=url):
                ref = parse_url(url)
                self.assertEqual(ref.service, Service.YOUTUBE)
                self.assertEqual(ref.kind, EntityKind.TRACK)
                self.assertEqual(ref.id, YT)

    def test_playlist_without_video_rejected(self):
        for url in [
            "https://music.youtube.com/playlist?list=PLabcdef",
            "https://www.youtube.com/playlist?list=PLabcdef",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(UnsupportedEntity) as cm:
                    parse_url(url)
                self.assertEqual(cm.exception.kind, EntityKind.PLAYLIST)

    def test_channel_rejected(self):
        with self.assertRaises(UnsupportedEntity):
            parse_url("https://www.youtube.com/channel/UCabcdefghijklmnop")

    def test_bad_id_rejected(self):
        for bad in ["short", YT + "toolong", "has spaces"]:
            with self.subTest(bad=bad):
                with self.assertRaises(MalformedURL):
                    parse_url(f"https://www.youtube.com/watch?v={bad}")


class ParseRejections(unittest.TestCase):
    def test_unknown_hosts(self):
        for url in [
            "https://soundcloud.com/artist/track",
            "https://tidal.com/browse/track/12345",
            "https://example.com/whatever",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(UnsupportedURL):
                    parse_url(url)

    def test_empty_and_garbage(self):
        for url in ["", "   ", None, "not a url at all"]:
            with self.subTest(url=url):
                with self.assertRaises((UnsupportedURL, MalformedURL, UnsupportedEntity)):
                    parse_url(url)

    def test_errors_carry_the_offending_url(self):
        try:
            parse_url("https://soundcloud.com/x/y")
        except UnsupportedURL as exc:
            self.assertEqual(exc.url, "https://soundcloud.com/x/y")
            self.assertTrue(exc.user_message)
        else:
            self.fail("expected UnsupportedURL")


class RoundTrip(unittest.TestCase):
    """Canonical URLs built from a ref must parse back to that same ref."""

    def test_web_urls_round_trip(self):
        for original in [
            f"https://open.spotify.com/track/{SP}?si=x",
            f"https://music.apple.com/gb/album/x/{AP_ALBUM}?i={AP_SONG}",
            f"https://youtu.be/{YT}",
        ]:
            with self.subTest(original=original):
                ref = parse_url(original)
                again = parse_url(web_url_for(ref))
                self.assertEqual((again.service, again.id), (ref.service, ref.id))

    def test_app_urls_have_native_schemes(self):
        self.assertTrue(
            app_url_for(parse_url(f"spotify:track:{SP}")).startswith("spotify:track:")
        )
        self.assertTrue(
            app_url_for(parse_url(f"https://youtu.be/{YT}")).startswith("vnd.youtube://")
        )
        self.assertTrue(
            app_url_for(
                parse_url(f"https://music.apple.com/us/song/x/{AP_SONG}")
            ).startswith("music://")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

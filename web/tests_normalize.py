"""Tests for title/artist normalisation. Plain unittest, no Django.

    cd RideTunes/rideTunes && python -m unittest music.tests.test_normalize -v

Inputs here are shaped like real YouTube video titles and channel names,
because that is the path with no ISRC and therefore the one carrying all the
matching risk.
"""

import unittest

from resolvers.normalize import (
    extract_featured,
    extract_version_tags,
    normalize_artist,
    normalize_text,
    normalize_title,
    parse_iso8601_duration,
    search_query_for,
    split_artist_title,
    strip_noise,
)


class StripNoise(unittest.TestCase):
    def test_promotional_markers_removed(self):
        for raw, expect in [
            ("Blinding Lights (Official Video)", "Blinding Lights"),
            ("Blinding Lights [Official Music Video]", "Blinding Lights"),
            ("Blinding Lights (Official Audio)", "Blinding Lights"),
            ("Blinding Lights (Lyrics)", "Blinding Lights"),
            ("Blinding Lights (Lyric Video)", "Blinding Lights"),
            ("Blinding Lights (Visualizer)", "Blinding Lights"),
            ("Blinding Lights | The Weeknd", "Blinding Lights"),
            ("Blinding Lights 4K", "Blinding Lights"),
            ("Blinding Lights (Explicit)", "Blinding Lights"),
            ("Blinding Lights (Remastered 2020)", "Blinding Lights"),
            ("Blinding Lights - Remastered", "Blinding Lights"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(strip_noise(raw), expect)

    def test_real_song_words_are_never_eaten(self):
        """The noise list must not damage titles that legitimately contain
        words like 'video' or 'audio'."""
        for raw in ["Video Games", "Radio Ga Ga", "Live and Let Die", "Videotape"]:
            with self.subTest(raw=raw):
                self.assertEqual(strip_noise(raw), raw)


class VersionTags(unittest.TestCase):
    def test_detected(self):
        for raw, tag in [
            ("Song (Live at Wembley)", "live"),
            ("Song (Tiesto Remix)", "remix"),
            ("Song - Acoustic", "acoustic"),
            ("Song (Instrumental)", "instrumental"),
            ("Song (Karaoke Version)", "karaoke"),
            ("Song (sped up)", "sped_up"),
            ("Song (slowed + reverb)", "slowed"),
            ("Song [8D AUDIO]", "spatial"),
            ("Song (Extended Mix)", "extended"),
            ("Song - Radio Edit", "radio_edit"),
        ]:
            with self.subTest(raw=raw):
                self.assertIn(tag, extract_version_tags(raw))

    def test_clean_title_has_no_tags(self):
        self.assertEqual(extract_version_tags("Blinding Lights"), frozenset())

    def test_live_word_in_a_real_title_not_flagged(self):
        # "Live and Let Die" must not read as a live recording.
        self.assertNotIn("live", extract_version_tags("Live and Let Die"))

    def test_tags_are_stripped_from_normalized_title(self):
        # The whole clause goes, not just the tag word -- otherwise "(Tiesto Remix)"
        # would leave "(Tiesto )" behind and poison the similarity comparison.
        self.assertEqual(normalize_title("Blinding Lights (Tiesto Remix)"), "Blinding Lights")
        self.assertEqual(normalize_title("Song (Live at Wembley)"), "Song")
        self.assertEqual(normalize_title("Song - Acoustic"), "Song")
        self.assertEqual(normalize_title("Song [8D AUDIO]"), "Song")

    def test_normalizing_away_a_tag_does_not_lose_the_signal(self):
        """Titles collapse to the same string, but the tags still differ -- which
        is what lets the matcher penalise a remix served for a studio request."""
        self.assertEqual(
            normalize_title("Blinding Lights (Tiesto Remix)"),
            normalize_title("Blinding Lights"),
        )
        self.assertNotEqual(
            extract_version_tags("Blinding Lights (Tiesto Remix)"),
            extract_version_tags("Blinding Lights"),
        )


class Featured(unittest.TestCase):
    def test_extracted(self):
        for raw, names in [
            ("Song (feat. Drake)", {"drake"}),
            ("Song ft. Drake", {"drake"}),
            ("Song featuring Drake", {"drake"}),
            ("Song (feat. Drake & Future)", {"drake", "future"}),
            ("Song (feat. Drake, Future)", {"drake", "future"}),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(set(extract_featured(raw)), names)

    def test_feature_clause_ignored_when_comparing(self):
        self.assertEqual(
            normalize_text("Song (feat. Drake)"), normalize_text("Song")
        )


class Artists(unittest.TestCase):
    def test_youtube_channel_suffixes_removed(self):
        for raw, expect in [
            ("The Weeknd - Topic", "The Weeknd"),
            ("TheWeekndVEVO", "TheWeeknd"),
            ("Arctic Monkeys - Official", "Arctic Monkeys"),
            ("The Weeknd", "The Weeknd"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_artist(raw), expect)


class SplitArtistTitle(unittest.TestCase):
    def test_standard_youtube_shape(self):
        artist, title = split_artist_title(
            "The Weeknd - Blinding Lights (Official Video)", "TheWeekndVEVO"
        )
        self.assertEqual(artist, "The Weeknd")
        self.assertEqual(title, "Blinding Lights")

    def test_falls_back_to_channel_when_no_dash(self):
        artist, title = split_artist_title("Blinding Lights", "The Weeknd - Topic")
        self.assertEqual(artist, "The Weeknd")
        self.assertEqual(title, "Blinding Lights")

    def test_does_not_split_on_a_dash_inside_a_long_title(self):
        long_left = "A Really Quite Extraordinarily Long Song Name Indeed Yes"
        artist, title = split_artist_title(f"{long_left} - Part Two", "Some Channel")
        self.assertEqual(artist, "Some Channel")

    def test_never_invents_an_artist(self):
        artist, _ = split_artist_title("Blinding Lights", "")
        self.assertEqual(artist, "")


class Durations(unittest.TestCase):
    def test_iso8601(self):
        for raw, ms in [
            ("PT3M20S", 200_000),
            ("PT4M", 240_000),
            ("PT45S", 45_000),
            ("PT1H2M3S", 3_723_000),
            ("PT0S", None),      # zero is not a usable duration
            ("garbage", None),
            ("", None),
            (None, None),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(parse_iso8601_duration(raw), ms)


class SearchQuery(unittest.TestCase):
    def test_built_from_cleaned_parts(self):
        """The exact case that produced
        'The Weeknd - Blinding Lights (Official Video) [4K] TheWeekndVEVO'
        under views.py:1344."""
        artist, title = split_artist_title(
            "The Weeknd - Blinding Lights (Official Video) [4K]", "TheWeekndVEVO"
        )
        q = search_query_for(title, artist)
        self.assertEqual(q, "Blinding Lights The Weeknd")
        for junk in ("Official", "Video", "4K", "VEVO"):
            self.assertNotIn(junk, q)

    def test_punctuation_heavy_titles_survive(self):
        # These are the titles that corrupted the unencoded URL at views.py:1346.
        for title, artist in [("Blood // Water", "grandson"), ("Sk8er Boi", "Avril Lavigne")]:
            with self.subTest(title=title):
                self.assertTrue(search_query_for(title, artist).strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)

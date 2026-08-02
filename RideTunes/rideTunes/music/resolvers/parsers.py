"""Music URL -> ServiceRef. Pure functions: no network, no I/O, no Django.

This module exists because the thing it replaces was three lines of
`path.split('/')[-1]` (views.py:105-137) that got the common cases wrong:

  * `music.apple.com/us/album/<slug>/<albumid>?i=<songid>` returned the ALBUM
    id. That `?i=` form is exactly what Apple Music's own share sheet produces,
    which is why Apple sharing has never worked.
  * `youtu.be/<id>` and `youtube.com/shorts/<id>` matched no branch and were
    dropped with a `print()` and a `continue`.
  * `spotify.link/<code>`, the default from Spotify's share sheet, was dropped
    the same way (`'spotify.com' not in 'spotify.link'`).
  * Album and playlist URLs were happily returned as though they were tracks.

Keeping this module free of Django imports is deliberate — the test suite runs
standalone in milliseconds, with no settings module and no database.
"""

import re
from urllib.parse import parse_qs, urlsplit, unquote

from .errors import MalformedURL, NeedsExpansion, UnsupportedEntity, UnsupportedURL
from .types import EntityKind, Service, ServiceRef

# --------------------------------------------------------------------------
# Identifier shapes. Validated before a ref is built so a malformed link fails
# here rather than as a confusing 404 from an upstream API later.
# --------------------------------------------------------------------------
SPOTIFY_ID = re.compile(r"^[0-9A-Za-z]{22}$")
APPLE_ID = re.compile(r"^\d{4,15}$")
YOUTUBE_ID = re.compile(r"^[0-9A-Za-z_-]{11}$")

#: Spotify localises share links as /intl-de/, /intl-pt/, etc.
_SPOTIFY_INTL = re.compile(r"^intl-[a-z]{2,3}$")

#: Apple storefronts are two-letter country codes in the first path segment.
_STOREFRONT = re.compile(r"^[a-z]{2}$")

DEFAULT_STOREFRONT = "us"

_SHORT_LINK_HOSTS = frozenset({"spotify.link", "spotify.app.link"})

_SPOTIFY_HOSTS = frozenset({"open.spotify.com", "play.spotify.com", "spotify.com"})
_APPLE_HOSTS = frozenset({"music.apple.com", "itunes.apple.com", "geo.music.apple.com"})
_YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "music.youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com"}
)

#: Spotify path segment -> what it points at. Anything not TRACK is a collection.
_SPOTIFY_KINDS = {
    "track": EntityKind.TRACK,
    "album": EntityKind.ALBUM,
    "playlist": EntityKind.PLAYLIST,
    "artist": EntityKind.ARTIST,
    "episode": EntityKind.PODCAST,
    "show": EntityKind.PODCAST,
}

_APPLE_KINDS = {
    "song": EntityKind.TRACK,
    "album": EntityKind.ALBUM,
    "playlist": EntityKind.PLAYLIST,
    "artist": EntityKind.ARTIST,
    "music-video": EntityKind.UNKNOWN,
}


def _normalise_host(host):
    """Lowercase, drop the port, drop a leading `www.`."""
    host = (host or "").lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _segments(path):
    """Path split into non-empty, percent-decoded segments."""
    return [unquote(s) for s in (path or "").split("/") if s]


def is_short_link(raw):
    """True if `raw` must be expanded over the network before it can be parsed."""
    try:
        return _normalise_host(urlsplit(_with_scheme(raw)).netloc) in _SHORT_LINK_HOSTS
    except ValueError:
        return False


def _with_scheme(raw):
    """Tolerate scheme-less input (`open.spotify.com/track/...`) from pasted text.

    Left alone if it already has any scheme, so the `spotify:track:` URI form
    still reaches its own branch.
    """
    raw = (raw or "").strip()
    if not raw or "://" in raw or raw.startswith("spotify:"):
        return raw
    return "https://" + raw


def parse_url(raw):
    """Parse a music URL into a validated `ServiceRef`.

    Raises `UnsupportedURL` (host not recognised), `UnsupportedEntity` (an
    album/playlist/artist rather than one song), `MalformedURL` (identifier
    failed validation), or `NeedsExpansion` (a short link).
    """
    if not raw or not raw.strip():
        raise UnsupportedURL("Empty URL", url=raw)

    candidate = _with_scheme(raw)

    # `spotify:track:<id>` is a URI, not an http(s) URL — handle before splitting.
    if candidate.startswith("spotify:"):
        return _parse_spotify_uri(candidate, raw)

    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise MalformedURL(f"Unparseable URL: {exc}", url=raw) from exc

    host = _normalise_host(parts.netloc)
    if not host:
        raise UnsupportedURL("No host in URL", url=raw)

    if host in _SHORT_LINK_HOSTS:
        raise NeedsExpansion(f"{host} links must be expanded first", url=raw)

    if host in _SPOTIFY_HOSTS:
        return _parse_spotify(parts, raw)
    if host in _APPLE_HOSTS:
        return _parse_apple(parts, raw)
    if host in _YOUTUBE_HOSTS:
        return _parse_youtube(host, parts, raw)

    raise UnsupportedURL(f"Unrecognised host: {host}", url=raw)


# --------------------------------------------------------------------------
# Spotify
# --------------------------------------------------------------------------
def _parse_spotify_uri(candidate, raw):
    """`spotify:track:<id>` — also the album/playlist/artist variants."""
    bits = candidate.split(":")
    if len(bits) < 3:
        raise MalformedURL("Malformed Spotify URI", url=raw)

    kind_word, ident = bits[-2], bits[-1]
    kind = _SPOTIFY_KINDS.get(kind_word, EntityKind.UNKNOWN)
    if kind is not EntityKind.TRACK:
        raise UnsupportedEntity(
            f"Spotify URI points to a {kind_word}, not a track", kind=kind, url=raw
        )
    if not SPOTIFY_ID.match(ident):
        raise MalformedURL(f"Invalid Spotify track id: {ident!r}", url=raw)
    return ServiceRef(Service.SPOTIFY, EntityKind.TRACK, ident, source_url=raw)


def _parse_spotify(parts, raw):
    segs = _segments(parts.path)

    # Drop the locale prefix on /intl-de/track/<id>, and the /embed/ variant.
    while segs and (_SPOTIFY_INTL.match(segs[0]) or segs[0] in ("embed", "embed-podcast")):
        segs.pop(0)

    if len(segs) < 2:
        raise UnsupportedEntity(
            "Spotify link doesn't point at a specific item", kind=EntityKind.UNKNOWN, url=raw
        )

    kind_word, ident = segs[0], segs[1]
    kind = _SPOTIFY_KINDS.get(kind_word, EntityKind.UNKNOWN)
    if kind is not EntityKind.TRACK:
        raise UnsupportedEntity(
            f"Spotify link points to a {kind_word}, not a track", kind=kind, url=raw
        )
    if not SPOTIFY_ID.match(ident):
        raise MalformedURL(f"Invalid Spotify track id: {ident!r}", url=raw)
    return ServiceRef(Service.SPOTIFY, EntityKind.TRACK, ident, source_url=raw)


# --------------------------------------------------------------------------
# Apple Music
# --------------------------------------------------------------------------
def _parse_apple(parts, raw):
    """Apple Music, including the `?i=` album-plus-track form.

    Apple's share sheet emits `/<cc>/album/<slug>/<albumid>?i=<songid>` for a
    single song. `?i=` therefore always wins over the album id in the path —
    getting this backwards is the single bug that broke Apple sharing.
    """
    segs = _segments(parts.path)

    storefront = DEFAULT_STOREFRONT
    if segs and _STOREFRONT.match(segs[0]):
        storefront = segs.pop(0)

    if not segs:
        raise UnsupportedEntity(
            "Apple Music link doesn't point at a specific item",
            kind=EntityKind.UNKNOWN,
            url=raw,
        )

    kind_word = segs[0]
    kind = _APPLE_KINDS.get(kind_word, EntityKind.UNKNOWN)

    # `?i=<songid>` designates a track regardless of what the path says.
    track_id = (parse_qs(parts.query).get("i") or [None])[0]
    if track_id:
        if not APPLE_ID.match(track_id):
            raise MalformedURL(f"Invalid Apple track id in ?i=: {track_id!r}", url=raw)
        return ServiceRef(
            Service.APPLE, EntityKind.TRACK, track_id, storefront=storefront, source_url=raw
        )

    if kind is not EntityKind.TRACK:
        raise UnsupportedEntity(
            f"Apple Music link points to a {kind_word}, not a song", kind=kind, url=raw
        )

    # /<cc>/song/<slug>/<id> or the slugless /<cc>/song/<id>.
    ident = segs[-1] if len(segs) > 1 else ""
    if not APPLE_ID.match(ident):
        raise MalformedURL(f"Invalid Apple song id: {ident!r}", url=raw)
    return ServiceRef(
        Service.APPLE, EntityKind.TRACK, ident, storefront=storefront, source_url=raw
    )


# --------------------------------------------------------------------------
# YouTube / YouTube Music
# --------------------------------------------------------------------------
def _parse_youtube(host, parts, raw):
    segs = _segments(parts.path)
    query = parse_qs(parts.query)

    # youtu.be/<id> puts the id in the path, not ?v=.
    if host == "youtu.be":
        ident = segs[0] if segs else ""
        return _youtube_ref(ident, raw)

    if segs and segs[0] in ("shorts", "embed", "v", "live"):
        return _youtube_ref(segs[1] if len(segs) > 1 else "", raw)

    if "v" in query:
        return _youtube_ref(query["v"][0], raw)

    # /playlist?list=… and /watch?list=… without a v= are collections. A `list`
    # alongside a `v` is fine — that's just "this song, from that playlist".
    if (segs and segs[0] == "playlist") or "list" in query:
        raise UnsupportedEntity(
            "YouTube link points to a playlist, not a single video",
            kind=EntityKind.PLAYLIST,
            url=raw,
        )
    if segs and segs[0] in ("channel", "c", "user") or (segs and segs[0].startswith("@")):
        raise UnsupportedEntity(
            "YouTube link points to a channel", kind=EntityKind.ARTIST, url=raw
        )

    raise UnsupportedEntity(
        "YouTube link doesn't point at a specific video", kind=EntityKind.UNKNOWN, url=raw
    )


def _youtube_ref(ident, raw):
    if not YOUTUBE_ID.match(ident or ""):
        raise MalformedURL(f"Invalid YouTube video id: {ident!r}", url=raw)
    return ServiceRef(Service.YOUTUBE, EntityKind.TRACK, ident, source_url=raw)


# --------------------------------------------------------------------------
# Canonical URL construction (the inverse of parsing)
# --------------------------------------------------------------------------
def web_url_for(ref):
    """The https URL for a ref. Preferred in browsers and share sheets: it opens
    the installed app when there is one and falls through to web when there isn't."""
    if ref.service is Service.SPOTIFY:
        return f"https://open.spotify.com/track/{ref.id}"
    if ref.service is Service.APPLE:
        sf = ref.storefront or DEFAULT_STOREFRONT
        return f"https://music.apple.com/{sf}/song/{ref.id}"
    return f"https://music.youtube.com/watch?v={ref.id}"


def app_url_for(ref):
    """Native-scheme URL, for handing off to an app already known to be installed
    (check `canOpenURL` first — these fail silently when the app is absent)."""
    if ref.service is Service.SPOTIFY:
        return f"spotify:track:{ref.id}"
    if ref.service is Service.APPLE:
        sf = ref.storefront or DEFAULT_STOREFRONT
        return f"music://music.apple.com/{sf}/song/{ref.id}"
    return f"vnd.youtube://www.youtube.com/watch?v={ref.id}"

"""Title/artist normalisation and version-tag extraction. Pure stdlib.

Most of the cross-service match accuracy lives here rather than in the scorer.
A YouTube video title is not a song title:

    "The Weeknd - Blinding Lights (Official Video) [4K]"  channel "TheWeekndVEVO"

against Spotify's:

    title "Blinding Lights"                                artist "The Weeknd"

The old code (views.py:1288-1289) took the raw video title as `name` and the
channel with only `" - Topic"` stripped as `artist`, then searched Spotify for
`"{name} {artist}"` — producing
`"The Weeknd - Blinding Lights (Official Video) [4K] TheWeekndVEVO"`. Duplicated
artist, plus junk. The LangChain step meant to fix this is commented out at
views.py:1206-1267 while its OpenAI client is still constructed at import.

Version tags are extracted rather than merely deleted: a live take and a studio
take have near-identical titles once the noise is stripped, so the matcher needs
to know a tag was *there* to tell them apart.
"""

import re
import unicodedata

# --------------------------------------------------------------------------
# Version tags. Extracted before cleanup so the matcher can compare them.
# Order matters only for readability; all patterns are tried.
# --------------------------------------------------------------------------
VERSION_TAGS = {
    "live": r"\blive\b(?!\s*(?:wire|and\s+let))",
    "remix": r"\bremix(?:es)?\b|\brmx\b",
    "acoustic": r"\bacoustic\b|\bunplugged\b",
    "instrumental": r"\binstrumental\b",
    "karaoke": r"\bkaraoke\b|\bsing[\s-]?along\b",
    "cover": r"\bcover(?:ed)?\s+(?:by|version)\b|\btribute\b",
    "sped_up": r"\bsped[\s-]?up\b|\bspeed[\s-]?up\b|\bnightcore\b",
    "slowed": r"\bslowed\b|\breverb(?:ed)?\b|\bdaycore\b",
    "spatial": r"\b8d\b|\b3d\s+audio\b|\bbinaural\b",
    "extended": r"\bextended\b|\blong\s+version\b",
    "radio_edit": r"\bradio\s+edit\b",
    "demo": r"\bdemo\b",
    "reprise": r"\breprise\b",
}
_VERSION_RE = {tag: re.compile(pat, re.I) for tag, pat in VERSION_TAGS.items()}

# Noise that carries no identity: promotional and format markers.
_NOISE_PATTERNS = [
    r"\((?:official\s+)?(?:music\s+)?video\)",
    r"\[(?:official\s+)?(?:music\s+)?video\]",
    r"\((?:official\s+)?(?:audio|lyric|lyrics|visualizer|visualiser|version)\)",
    r"\[(?:official\s+)?(?:audio|lyric|lyrics|visualizer|visualiser)\]",
    r"\(official\)|\[official\]",
    r"\((?:lyric|lyrics)\s+video\)|\[(?:lyric|lyrics)\s+video\]",
    r"\(explicit\)|\[explicit\]|\(clean\)|\[clean\]",
    r"\(remaster(?:ed)?(?:\s+\d{4})?\)|\[remaster(?:ed)?(?:\s+\d{4})?\]",
    r"[-–—]\s*remaster(?:ed)?(?:\s+\d{4})?\s*$",
    r"\(\s*\d{4}\s+remaster(?:ed)?\s*\)",
    r"\b(?:hd|hq|4k|1080p|720p)\b",
    r"\|\s*.*$",                       # everything after a pipe is channel dressing
    r"\(\s*\)|\[\s*\]",                # empties left by the above
]
_NOISE_RE = [re.compile(p, re.I) for p in _NOISE_PATTERNS]

# "(feat. X)", "ft. X", "featuring X" — pulled out so it can be compared
# separately; a match that differs only by a featured artist is still a match.
_FEAT_RE = re.compile(
    r"[\(\[]?\s*\b(?:feat|ft|featuring|with)\b\.?\s+([^)\]]+)[\)\]]?", re.I
)

# Channel-name suffixes that are not artist names. VEVO is matched without a
# word boundary because it is glued on ("TheWeekndVEVO"), so `\bvevo\b` misses it.
_CHANNEL_SUFFIX_RE = re.compile(r"\s*-\s*topic\s*$|\s*-\s*official\s*$|vevo\s*$", re.I)

#: A parenthesised/bracketed group. Used to drop a whole clause when it turns
#: out to be a version marker — deleting just the tag word leaves "(Tiesto )".
_BRACKETED_RE = re.compile(r"[\(\[][^)\]]*[\)\]]")

#: Longest a leading "Artist - Title" segment may be before we stop believing
#: it is an artist name. Real ones are comfortably under this ("Nick Cave and
#: the Bad Seeds" is 27); song titles containing a dash are not.
MAX_ARTIST_LEN = 40

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?$",
    re.I,
)


def extract_version_tags(text):
    """Version markers present in `text`, as a set of tag names.

    Compared between source and candidate by the matcher: a candidate carrying
    "remix" when the source doesn't is the classic wrong-result failure.
    """
    if not text:
        return frozenset()
    return frozenset(tag for tag, rx in _VERSION_RE.items() if rx.search(text))


def extract_featured(text):
    """Featured-artist names mentioned in `text`, lowercased."""
    if not text:
        return frozenset()
    names = set()
    for chunk in _FEAT_RE.findall(text):
        for name in re.split(r"\s*(?:,|&|\band\b|\bx\b)\s*", chunk):
            name = name.strip().lower()
            if name:
                names.add(name)
    return frozenset(names)


def strip_noise(text):
    """Remove promotional/format markers, preserving word content."""
    if not text:
        return ""
    out = text
    for rx in _NOISE_RE:
        out = rx.sub(" ", out)
    return _WS_RE.sub(" ", out).strip(" -–—_|")


def normalize_text(text):
    """Aggressive fold for similarity comparison.

    Unicode NFKC, casefold, featured-artist clause removed, punctuation dropped,
    whitespace collapsed. Lossy by design — never store or display the result.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = strip_noise(out)
    out = _FEAT_RE.sub(" ", out)
    out = out.casefold()
    out = _PUNCT_RE.sub(" ", out)
    return _WS_RE.sub(" ", out).strip()


def _drop_version_clauses(text):
    """Remove whole bracketed groups that are version markers.

    "(Tiesto Remix)" goes entirely, rather than leaving "(Tiesto )" behind.
    """
    return _BRACKETED_RE.sub(
        lambda m: " " if extract_version_tags(m.group(0)) else m.group(0), text
    )


def normalize_title(title):
    """Clean a track/video title down to the song name, version markers removed.

    Aggressive on purpose: "Song (Live at Wembley)" becomes "Song" so it still
    matches the studio recording on title. Telling the two apart is the job of
    `extract_version_tags` and the matcher's tag penalty, not of this function.
    """
    if not title:
        return ""
    out = strip_noise(unicodedata.normalize("NFKC", title))
    out = _drop_version_clauses(out)
    for rx in _VERSION_RE.values():
        out = rx.sub(" ", out)
    out = re.sub(r"[\(\[]\s*[\)\]]", " ", out)
    return _WS_RE.sub(" ", out).strip(" -–—_|")


def normalize_artist(artist):
    """Clean an artist or channel name.

    Handles `" - Topic"` (YouTube's auto-generated artist channels) and `VEVO`.
    The client already does the `- Topic` half at
    MusicLibraryViewModel.swift:478-479; this is the server-side equivalent.
    """
    if not artist:
        return ""
    out = unicodedata.normalize("NFKC", artist)
    out = _CHANNEL_SUFFIX_RE.sub(" ", out)
    out = strip_noise(out)
    return _WS_RE.sub(" ", out).strip(" -–—_|")


def split_artist_title(video_title, channel=""):
    """Best-effort `(artist, title)` from a YouTube video title.

    YouTube titles are overwhelmingly `"Artist - Title (Official Video)"`. When
    that shape is present and the leading part corroborates the channel name, it
    is a better artist source than the channel itself. Falls back to
    `(channel, title)` when the shape isn't there — never invents an artist.
    """
    cleaned = strip_noise(unicodedata.normalize("NFKC", video_title or ""))
    channel_norm = normalize_artist(channel)

    parts = re.split(r"\s+[-–—]\s+", cleaned, maxsplit=1)
    if len(parts) == 2 and all(p.strip() for p in parts):
        left, right = parts[0].strip(), parts[1].strip()
        # Guard against titles that merely contain a dash ("Hello - Goodbye").
        if len(left) <= MAX_ARTIST_LEN:
            return normalize_artist(left), normalize_title(right)

    return channel_norm, normalize_title(cleaned)


def parse_iso8601_duration(value):
    """ISO-8601 duration -> milliseconds, or None.

    YouTube's `contentDetails.duration` is the only place this format appears
    (`PT3M20S`). Spotify and Apple both return integer milliseconds already.
    """
    if not value or not isinstance(value, str):
        return None
    m = _ISO_DURATION_RE.match(value.strip())
    if not m:
        return None
    parts = {k: float(v) for k, v in m.groupdict(default="0").items()}
    total = (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )
    return int(round(total * 1000)) or None


def search_query_for(title, artist):
    """The query string to send to a target service's search endpoint.

    Deliberately `"title artist"` with noise and version tags stripped — the old
    inline path (views.py:1344) built `f"{track['name']} {track['artist']}"` from
    raw values and interpolated it into the URL *unencoded*, so any `&`, `#` or
    `?` in a title truncated the query.
    """
    return _WS_RE.sub(" ", f"{normalize_title(title)} {normalize_artist(artist)}").strip()

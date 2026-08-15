"""Value types shared across the resolver package.

Pure stdlib on purpose: `parsers` imports this and must stay importable without
Django configured, so the URL-parsing test suite runs in milliseconds with no
settings module, no database, and no celery.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Service(str, Enum):
    """The three music services, in *wire* form.

    These values are what the resolver and the new v1 API speak. They are
    deliberately NOT the values `UserProfile.music_service` stores, which are
    display strings ('Spotify' / 'YouTube' / 'Apple Music'), nor the OAuth
    backend names ('spotify' / 'google-oauth2' / 'apple-id'). Three vocabularies
    already exist in this codebase; `music.providers` is the single place that
    translates between them. Do not add a fourth conversion site here.
    """

    SPOTIFY = "spotify"
    APPLE = "apple"
    YOUTUBE = "youtube"

    def __str__(self):
        return self.value


class EntityKind(str, Enum):
    """What a URL points at. Only TRACK is resolvable; the rest exist so
    `UnsupportedEntity` can say *which* kind of collection was pasted."""

    TRACK = "track"
    ALBUM = "album"
    PLAYLIST = "playlist"
    ARTIST = "artist"
    PODCAST = "podcast"
    UNKNOWN = "unknown"


class MatchMethod(str, Enum):
    """How a cross-service match was arrived at. Surfaced to the client so the
    UI can decide whether to show the 'not the right version?' affordance."""

    #: The link the sender actually pasted — no matching was needed.
    ORIGIN = "origin"
    #: Exact, via ISRC. Treat as certain.
    ISRC = "isrc"
    #: Title/artist/duration scoring. Confidence is meaningful here.
    FUZZY = "fuzzy"


@dataclass(frozen=True, slots=True)
class ServiceRef:
    """A validated pointer to one track on one service. The output of parsing.

    Carries no metadata — resolving a ref into a `SongIdentity` is a separate,
    network-bound step.
    """

    service: Service
    kind: EntityKind
    id: str
    #: Two-letter storefront, Apple Music only. Catalog IDs are global but
    #: availability is storefront-scoped, so a `us` ID can 404 in `de`.
    storefront: Optional[str] = None
    #: The URL this was parsed from, for logging and error messages.
    source_url: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("ServiceRef requires a non-empty id")
        if self.service is Service.APPLE and self.storefront is None:
            raise ValueError("Apple refs require a storefront")


@dataclass(frozen=True, slots=True)
class SongIdentity:
    """Service-agnostic identity of a song — what a share link actually carries.

    `isrc` is the strong key when present. Everything else is both the fallback
    identity for fuzzy matching and the display payload the client renders, so
    a resolved identity needs no second round trip to show a song card.
    """

    title: str
    artist: str
    isrc: Optional[str] = None
    album: str = ""
    duration_ms: Optional[int] = None
    artwork_url: str = ""
    explicit: Optional[bool] = None
    release_year: Optional[int] = None

    @property
    def has_strong_key(self):
        """True when this can be matched exactly rather than fuzzily.

        YouTube never supplies an ISRC, which is why YouTube-as-source is
        structurally the lowest-confidence path in the system.
        """
        return bool(self.isrc)


@dataclass(frozen=True, slots=True)
class Match:
    """One candidate result of matching a `SongIdentity` onto a target service."""

    ref: ServiceRef
    identity: SongIdentity
    method: MatchMethod
    #: 0.0–1.0. Always 1.0 for ORIGIN and ISRC matches.
    confidence: float = 1.0
    web_url: str = ""
    #: Native scheme (`spotify:track:…`) for handing off to an installed app.
    app_url: str = ""

    @property
    def is_exact(self):
        return self.method in (MatchMethod.ORIGIN, MatchMethod.ISRC)


@dataclass
class ResolveResult:
    """What `resolve_url()` hands back: the song, plus the best link per service.

    `alternates` ships in the same payload so the client's "not the right
    version?" swap is instant rather than a second network call.
    """

    identity: SongIdentity
    source: ServiceRef
    matches: dict = field(default_factory=dict)      # Service -> Match
    alternates: dict = field(default_factory=dict)   # Service -> list[Match]

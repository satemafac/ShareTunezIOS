"""Cross-service music link resolution.

Public surface is deliberately small. Import from here, not from submodules —
the internals will grow (spotify/apple/youtube clients, matcher, cache) and
callers should not couple to that layout.

    from music.resolvers import parse_url, is_short_link, UnsupportedEntity

`parse_url` is pure and importable without Django configured. The service
clients are not — they need settings for credentials — so they are imported
lazily rather than at module load.
"""

from .errors import (
    MalformedURL,
    NeedsExpansion,
    NotFound,
    ResolverError,
    UnsupportedEntity,
    UnsupportedURL,
    UpstreamError,
)
from .parsers import app_url_for, is_short_link, parse_url, web_url_for
from .types import (
    EntityKind,
    Match,
    MatchMethod,
    ResolveResult,
    Service,
    ServiceRef,
    SongIdentity,
)

__all__ = [
    # parsing
    "parse_url",
    "is_short_link",
    "web_url_for",
    "app_url_for",
    # types
    "Service",
    "EntityKind",
    "ServiceRef",
    "SongIdentity",
    "Match",
    "MatchMethod",
    "ResolveResult",
    # errors
    "ResolverError",
    "UnsupportedURL",
    "MalformedURL",
    "UnsupportedEntity",
    "NeedsExpansion",
    "UpstreamError",
    "NotFound",
]

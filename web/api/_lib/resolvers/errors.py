"""Typed errors for the resolver package.

Every failure mode a caller might reasonably want to distinguish gets its own
class. The old `receive_music_urls` (views.py:105) swallowed everything into a
bare `except Exception` and silently dropped unparseable URLs from its result
list, so callers could not tell *which* input failed or *why*. That is the
behaviour these types exist to replace.
"""


class ResolverError(Exception):
    """Base for everything this package raises."""

    #: Safe to show a user as-is. Subclasses override.
    user_message = "Couldn't read that link."

    def __init__(self, message="", *, url=None):
        self.url = url
        super().__init__(message or self.user_message)


class UnsupportedURL(ResolverError):
    """The host isn't one we recognise at all."""

    user_message = "That doesn't look like a Spotify, Apple Music, or YouTube link."


class MalformedURL(ResolverError):
    """Recognised host and entity type, but the identifier failed validation."""

    user_message = "That link looks incomplete. Try copying it again."


class UnsupportedEntity(ResolverError):
    """Recognised, but it points at an album/playlist/artist rather than one song.

    Carries `kind` so the caller can tailor the message — telling someone
    "that's an album, not a song" is far more useful than a generic failure.
    """

    user_message = "That link points to a collection, not a single song."

    def __init__(self, message="", *, kind=None, url=None):
        self.kind = kind
        super().__init__(message, url=url)


class NeedsExpansion(ResolverError):
    """A short link that must be resolved over the network before parsing.

    `parsers` is deliberately pure — no network, no I/O — so it signals rather
    than expands. The caller is expected to run it through `shortlinks.expand()`
    and parse the result.
    """

    user_message = "That's a short link that needs expanding."


class UpstreamError(ResolverError):
    """A music service's API failed or returned something unusable."""

    user_message = "A music service isn't responding right now. Try again shortly."

    def __init__(self, message="", *, service=None, status=None, url=None):
        self.service = service
        self.status = status
        super().__init__(message, url=url)


class NotFound(ResolverError):
    """The identifier parsed fine but no such track exists on that service."""

    user_message = "That song doesn't seem to exist anymore."

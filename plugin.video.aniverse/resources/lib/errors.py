"""Typed errors so views can choose a notification or a dialog (DEC-035).

Messages must already be redacted when an error is created.
"""


class AniVerseError(Exception):
    pass


class NetworkError(AniVerseError):
    """Timeout, DNS, TLS or connection failure."""


class HttpError(AniVerseError):
    """Non-success HTTP status that is not retried."""

    def __init__(self, message, status, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class ServiceUnavailable(HttpError):
    """5xx after retries."""


class RateLimited(HttpError):
    def __init__(self, message, retry_after=None, status=429, payload=None):
        super().__init__(message, status, payload)
        self.retry_after = retry_after


class SchemaTooNew(AniVerseError):
    """user.db was written by a newer AniVerse; refuse to touch it (DEC-039)."""


class AuthError(AniVerseError):
    """Real-Debrid authorization missing, expired or revoked: owner must reconnect."""


class AccountError(AniVerseError):
    """Real-Debrid account problem (not premium, limits reached). `code` is RD's error_code."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code

"""Typed errors so views can choose a notification or a dialog (DEC-035).

Messages must already be redacted when an error is created.
"""


class NovaFlixError(Exception):
    pass


class NetworkError(NovaFlixError):
    """Timeout, DNS, TLS or connection failure."""


class HttpError(NovaFlixError):
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


class SchemaTooNew(NovaFlixError):
    """user.db was written by a newer NovaFlix; refuse to touch it (DEC-039)."""


class AuthError(NovaFlixError):
    """TorBox or TMDB rejected the key, or no key is set: the owner fixes it in Settings."""


class AccountError(NovaFlixError):
    """TorBox account problem (limits reached, plan restriction). `code` is the service's error code."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code

"""Masks secrets in anything that may reach a log, exception or notification.

Two layers (DEC-037, SEC-03/04):
- known secret values registered at runtime (tokens, client IDs) are replaced
  wherever they appear;
- pattern rules catch credentials we never registered: URL query strings,
  Bearer values, JSON/form token fields, magnets.
"""

import re

MASK = "<redacted>"
_MIN_SECRET_LEN = 6
_secrets = set()

_SENSITIVE_HEADERS = {"authorization", "x-mal-client-id", "cookie", "set-cookie"}
_SENSITIVE_KEYS = (
    "access_token|refresh_token|client_secret|client_id|device_code|code|token|"
    "auth_token|apikey|api_key|password|secret"
)

_PATTERNS = [
    (re.compile(r"magnet:\?\S+", re.I), "magnet:?" + MASK),
    (re.compile(r"(https?://[^\s?#\"']+)[?#][^\s\"']*"), r"\1?" + MASK),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.I), r"\1" + MASK),
    # "key": "value"  /  key=value  /  key: value
    (re.compile(r'(["\']?(?:%s)["\']?\s*[:=]\s*["\']?)[^"\'&\s,}]+' % _SENSITIVE_KEYS, re.I), r"\1" + MASK),
]


def register_secret(value):
    if value and len(str(value)) >= _MIN_SECRET_LEN:
        _secrets.add(str(value))


def clear_secrets():
    _secrets.clear()


def text(value):
    out = str(value)
    # Longest first so a secret containing another is masked whole.
    for secret in sorted(_secrets, key=len, reverse=True):
        out = out.replace(secret, MASK)
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def url(value):
    """Scheme, host and path only; anything after ? or # is dropped."""
    base = re.split(r"[?#]", value, maxsplit=1)[0]
    return text(base) + ("?" + MASK if base != value else "")


def headers(values):
    return {k: (MASK if k.lower() in _SENSITIVE_HEADERS else v) for k, v in values.items()}

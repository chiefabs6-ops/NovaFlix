"""The only HTTP client in AniVerse (SEC-05/08/09).

- HTTPS only, certificate verification on.
- Timeouts on every request.
- GET retried at most MAX_RETRIES times on network errors, 5xx and short
  429s, with exponential backoff; POST/DELETE never retried.
- Per-host rate limit inside this process (each Kodi plugin call is its own
  process, so cross-call limits rely on servers' 429 + Retry-After).
- Error messages carry a redacted URL only.
"""

import gzip
import json
import ssl
import time
import urllib.error
import uuid
import urllib.request
from collections import defaultdict, deque
from urllib.parse import urlencode, urlsplit

from resources.lib import errors, redact

DEFAULT_TIMEOUT = 10
MAX_RETRIES = 2
MAX_RETRY_AFTER = 30  # longer server waits are raised, not slept through
MAX_LIMITER_WAIT = 20
BACKOFF_BASE = 1.0

DEFAULT_RATE_LIMIT = 60  # requests per minute per host
RATE_LIMITS = {
    "api.real-debrid.com": 200,   # documented limit 250/min
    "graphql.anilist.co": 30,     # documented 90/min, reported degraded
}

USER_AGENT = "AniVerse"
_UNCONFIGURED_UA = USER_AGENT + "/unknown"

_sleep = time.sleep
_clock = time.monotonic
_ca_file = None
_context = None
_user_agent = _UNCONFIGURED_UA
_history = defaultdict(deque)


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8")) if self.body else None

    @property
    def text(self):
        return self.body.decode("utf-8", "replace")


def _urllib_transport(method, url, headers, body, timeout, context):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read() or b""


_transport = _urllib_transport


def set_transport(transport):
    global _transport
    _transport = transport


def configure(ca_file=None, version=None):
    global _ca_file, _context, _user_agent
    _ca_file = ca_file
    _context = None
    _user_agent = f"{USER_AGENT}/{version}" if version else _UNCONFIGURED_UA


def reset():
    global _transport, _ca_file, _context, _user_agent
    _transport = _urllib_transport
    _ca_file = None
    _context = None
    _user_agent = _UNCONFIGURED_UA
    _history.clear()


def _ssl_context():
    global _context
    if _context is None:
        _context = ssl.create_default_context(cafile=_ca_file)
        _context.minimum_version = ssl.TLSVersion.TLSv1_2
    return _context


def _wait_for_rate_limit(host):
    limit = RATE_LIMITS.get(host, DEFAULT_RATE_LIMIT)
    window = _history[host]
    now = _clock()
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= limit:
        wait = 60 - (now - window[0])
        if wait > MAX_LIMITER_WAIT:
            raise errors.RateLimited(f"local rate limit for {host}", retry_after=wait)
        _sleep(wait)
        now = _clock()
        while window and now - window[0] >= 60:
            window.popleft()
    window.append(now)


def _decode_payload(body):
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _retry_after(headers):
    for key, value in headers.items():
        if key.lower() == "retry-after":
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


CRLF = "\r\n"


def _multipart(fields):
    boundary = "----AniVerse" + uuid.uuid4().hex
    lines = []
    for name, value in fields.items():
        lines += [f"--{boundary}", f'Content-Disposition: form-data; name="{name}"', "", str(value)]
    lines += [f"--{boundary}--", ""]
    return CRLF.join(lines).encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def request(method, url, params=None, data=None, json_body=None, multipart=None, headers=None, timeout=DEFAULT_TIMEOUT):
    if not url.lower().startswith("https://"):
        raise ValueError(f"refusing non-HTTPS URL: {redact.url(url)}")
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)

    send_headers = {"User-Agent": _user_agent, "Accept-Encoding": "gzip"}
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        send_headers["Content-Type"] = "application/json"
    elif multipart is not None:
        body, send_headers["Content-Type"] = _multipart(multipart)
    elif data is not None:
        body = urlencode(data).encode("utf-8")
        send_headers["Content-Type"] = "application/x-www-form-urlencoded"
    send_headers.update(headers or {})

    host = urlsplit(url).hostname or ""
    safe_url = redact.url(url)
    retryable = method in ("GET", "HEAD")
    attempts = MAX_RETRIES + 1 if retryable else 1

    for attempt in range(attempts):
        last = attempt == attempts - 1
        _wait_for_rate_limit(host)
        try:
            status, resp_headers, resp_body = _transport(method, url, send_headers, body, timeout, _ssl_context())
        except (OSError, ssl.SSLError) as exc:
            # socket.timeout, URLError, ConnectionError and SSL errors are all OSError.
            if last:
                raise errors.NetworkError(f"{method} {safe_url} failed: {type(exc).__name__}") from None
            _sleep(BACKOFF_BASE * 2 ** attempt)
            continue

        if any(k.lower() == "content-encoding" and v.lower() == "gzip" for k, v in resp_headers.items()):
            resp_body = gzip.decompress(resp_body)

        if 200 <= status < 300:
            return Response(status, resp_headers, resp_body)

        payload = _decode_payload(resp_body)
        message = f"{method} {safe_url} returned HTTP {status}"
        if status == 429:
            wait = _retry_after(resp_headers)
            if last or (wait is not None and wait > MAX_RETRY_AFTER):
                raise errors.RateLimited(message, retry_after=wait, payload=payload)
            _sleep(wait if wait is not None else BACKOFF_BASE * 2 ** attempt)
            continue
        if status >= 500:
            if last:
                raise errors.ServiceUnavailable(message, status, payload)
            _sleep(BACKOFF_BASE * 2 ** attempt)
            continue
        raise errors.HttpError(message, status, payload)


def get(url, **kwargs):
    return request("GET", url, **kwargs)


def post(url, **kwargs):
    return request("POST", url, **kwargs)


def delete(url, **kwargs):
    return request("DELETE", url, **kwargs)

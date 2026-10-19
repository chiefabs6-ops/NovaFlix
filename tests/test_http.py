import gzip
import json
import socket

import pytest

from resources.lib import errors, redact
from resources.lib.net import http


class FakeTransport:
    """Returns queued responses; records every call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout, context):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def ok(data, status=200, headers=None):
    return status, headers or {}, json.dumps(data).encode()


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(http, "_sleep", recorded.append)
    return recorded


def use(transport):
    http.set_transport(transport)
    return transport


def test_get_returns_json_and_sends_user_agent(sleeps):
    t = use(FakeTransport(ok({"a": 1})))
    resp = http.get("https://api.example.com/x", params={"q": "frieren"})
    assert resp.json() == {"a": 1}
    assert t.calls[0]["url"] == "https://api.example.com/x?q=frieren"
    assert t.calls[0]["headers"]["User-Agent"].startswith("NovaFlix/")
    assert t.calls[0]["timeout"] == http.DEFAULT_TIMEOUT


def test_plain_http_is_refused():
    with pytest.raises(ValueError):
        http.get("http://api.example.com/x")


def test_get_retries_5xx_twice_then_raises(sleeps):
    t = use(FakeTransport((502, {}, b""), (503, {}, b""), (500, {}, b"")))
    with pytest.raises(errors.ServiceUnavailable):
        http.get("https://api.example.com/x")
    assert len(t.calls) == 3
    assert len(sleeps) == 2


def test_get_retries_network_error_then_succeeds(sleeps):
    t = use(FakeTransport(socket.timeout("timed out"), ok({"ok": True})))
    assert http.get("https://api.example.com/x").json() == {"ok": True}
    assert len(t.calls) == 2


def test_network_error_after_retries_raises_network_error(sleeps):
    use(FakeTransport(OSError("down"), OSError("down"), OSError("down")))
    with pytest.raises(errors.NetworkError):
        http.get("https://api.example.com/x")


def test_post_is_never_retried(sleeps):
    t = use(FakeTransport((503, {}, b"")))
    with pytest.raises(errors.ServiceUnavailable):
        http.post("https://api.example.com/x", data={"magnet": "m"})
    assert len(t.calls) == 1
    assert sleeps == []


def test_post_network_error_is_not_retried(sleeps):
    t = use(FakeTransport(OSError("reset")))
    with pytest.raises(errors.NetworkError):
        http.post("https://api.example.com/x", data={"a": "b"})
    assert len(t.calls) == 1


def test_post_form_body_is_urlencoded(sleeps):
    t = use(FakeTransport(ok({})))
    http.post("https://api.example.com/x", data={"a": "1 2"})
    assert t.calls[0]["body"] == b"a=1+2"
    assert t.calls[0]["headers"]["Content-Type"] == "application/x-www-form-urlencoded"


def test_post_json_body(sleeps):
    t = use(FakeTransport(ok({})))
    http.post("https://api.example.com/x", json_body={"query": "{ x }"})
    assert json.loads(t.calls[0]["body"]) == {"query": "{ x }"}
    assert t.calls[0]["headers"]["Content-Type"] == "application/json"


def test_429_honours_retry_after(sleeps):
    t = use(FakeTransport((429, {"Retry-After": "7"}, b""), ok({"ok": 1})))
    assert http.get("https://api.example.com/x").json() == {"ok": 1}
    assert sleeps[0] == 7
    assert len(t.calls) == 2


def test_429_with_long_retry_after_raises_instead_of_waiting(sleeps):
    use(FakeTransport((429, {"Retry-After": "600"}, b"")))
    with pytest.raises(errors.RateLimited) as info:
        http.get("https://api.example.com/x")
    assert info.value.retry_after == 600
    assert sleeps == []


def test_4xx_is_not_retried_and_keeps_status_and_payload(sleeps):
    t = use(FakeTransport((401, {}, json.dumps({"error": "bad_token", "error_code": 8}).encode())))
    with pytest.raises(errors.HttpError) as info:
        http.get("https://api.example.com/x")
    assert info.value.status == 401
    assert info.value.payload == {"error": "bad_token", "error_code": 8}
    assert len(t.calls) == 1


def test_error_messages_never_contain_secrets_or_query(sleeps):
    redact.register_secret("SENTINELTOKEN0123456789")
    use(FakeTransport((500, {}, b"SENTINELTOKEN0123456789"), (500, {}, b""), (500, {}, b"")))
    with pytest.raises(errors.ServiceUnavailable) as info:
        http.get("https://api.example.com/x", params={"auth_token": "SENTINELTOKEN0123456789"})
    message = str(info.value)
    assert "SENTINELTOKEN0123456789" not in message
    assert "auth_token" not in message
    assert "api.example.com/x" in message


def test_gzip_body_is_decoded(sleeps):
    body = gzip.compress(json.dumps({"z": 1}).encode())
    use(FakeTransport((200, {"Content-Encoding": "gzip"}, body)))
    assert http.get("https://api.example.com/x").json() == {"z": 1}


def test_custom_timeout_is_passed(sleeps):
    t = use(FakeTransport(ok({})))
    http.get("https://api.example.com/x", timeout=15)
    assert t.calls[0]["timeout"] == 15


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_rate_limiter_waits_when_host_budget_used(monkeypatch):
    clock = FakeClock()
    waited = []

    def fake_sleep(seconds):
        waited.append(seconds)
        clock.now += seconds

    monkeypatch.setattr(http, "_sleep", fake_sleep)
    monkeypatch.setattr(http, "_clock", clock)
    monkeypatch.setitem(http.RATE_LIMITS, "limited.example.com", 3)
    use(FakeTransport(*[ok({}) for _ in range(4)]))
    for _ in range(4):
        http.get("https://limited.example.com/x")
        clock.now += 15
    # Requests at t=0,15,30 fill the 3/min budget; the 4th (t=45) waits until t=60.
    assert waited == [15]


def test_rate_limiter_raises_when_wait_too_long(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(http, "_clock", clock)
    monkeypatch.setattr(http, "_sleep", lambda s: None)
    monkeypatch.setitem(http.RATE_LIMITS, "limited.example.com", 1)
    monkeypatch.setattr(http, "MAX_LIMITER_WAIT", 5)
    use(FakeTransport(ok({}), ok({})))
    http.get("https://limited.example.com/x")
    with pytest.raises(errors.RateLimited):
        http.get("https://limited.example.com/x")


def test_default_rate_limits_match_design():
    assert http.RATE_LIMITS["api.themoviedb.org"] == 120
    assert http.DEFAULT_RATE_LIMIT == 60

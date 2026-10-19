"""M13: the phone hands the MyAnimeList login to the TV — address rules, listener, relay page."""

import os
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest
import xbmc

from resources.lib.myanimelist import relay

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PAGE = os.path.join(ROOT, "pages", "mal-login.html")
NONCE = "AbCdEfGhIjKlMn_-"
STATE = f"{NONCE}~192.168.1.86~41234"
LOGIN = "https://myanimelist.net/v1/oauth2/authorize?x=1"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    try:
        with opener.open(url, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8")


@pytest.fixture
def server():
    s = relay.CallbackServer("127.0.0.1")
    s.expect(STATE, LOGIN)
    s.start()
    yield s
    s.stop()


def base(s):
    return f"http://127.0.0.1:{s.port}"


@pytest.mark.parametrize("state,expected", [
    (f"{NONCE}~192.168.1.86~41234", (NONCE, "192.168.1.86", 41234)),
    (f"{NONCE}~10.0.0.5~1024", (NONCE, "10.0.0.5", 1024)),
    (f"{NONCE}~172.31.255.1~65535", (NONCE, "172.31.255.1", 65535)),
    (f"{NONCE}~172.32.0.1~41234", None),        # outside 172.16/12
    (f"{NONCE}~8.8.8.8~41234", None),
    (f"{NONCE}~127.0.0.1~41234", None),
    (f"{NONCE}~192.168.1.300~41234", None),
    (f"{NONCE}~192.168.1.86~80", None),         # port below 1024
    (f"{NONCE}~192.168.1.86~70000", None),
    ("short~192.168.1.86~41234", None),
    (f"{NONCE}~evil.example~41234", None),
    (f"{NONCE}~192.168.1.86~41234~x", None),
    ("", None),
])
def test_parse_state(state, expected):
    assert relay.parse_state(state) == expected


def test_lan_address_uses_the_route_and_requires_a_private_ip():
    class Sock:
        def __init__(self, ip):
            self.ip, self.closed = ip, False

        def connect(self, address):
            self.address = address

        def getsockname(self):
            return (self.ip, 50000)

        def close(self):
            self.closed = True

    home = Sock("192.168.1.86")
    assert relay.lan_address(lambda: home) == "192.168.1.86" and home.closed
    assert relay.lan_address(lambda: Sock("100.64.0.1")) is None   # carrier NAT, not a home network


def test_lan_address_without_network():
    class Down:
        def connect(self, address):
            raise OSError("network unreachable")

        def close(self):
            pass

    assert relay.lan_address(lambda: Down()) is None


def test_root_redirects_the_phone_to_the_mal_login(server):
    status, headers, _ = get(base(server) + "/")
    assert status == 302 and headers["Location"] == LOGIN


def test_callback_with_right_state_is_accepted_once(server):
    url = f"{base(server)}/callback?code=AUTHCODE123456&state={quote(STATE)}"
    status, _, body = get(url)
    assert status == 200 and "return to your TV" in body
    assert server.result == ("code", "AUTHCODE123456")
    status, _, body = get(url)  # phone reloads the page
    assert status == 400 and "expired" in body and server.result == ("code", "AUTHCODE123456")


def test_wrong_state_is_rejected(server):
    status, _, body = get(f"{base(server)}/callback?code=AUTHCODE123456&state=other")
    assert status == 400 and "expired" in body and server.result is None


def test_deny_on_mal_ends_the_login_as_cancelled(server):
    status, _, body = get(f"{base(server)}/callback?error=access_denied&state={quote(STATE)}")
    assert status == 200 and "cancelled" in body and server.result == ("denied", "access_denied")


def test_other_paths_are_not_served(server):
    assert get(base(server) + "/favicon.ico")[0] == 404


def test_request_lines_are_never_logged(server):
    get(f"{base(server)}/callback?code=AUTHCODE123456&state=wrong")
    assert not any("AUTHCODE" in msg for _, msg in xbmc.log_records)


def test_relay_page_is_static_and_forwards_only_to_a_private_address():
    with open(PAGE, encoding="utf-8") as f:
        html = f.read()
    lower = html.lower()
    assert "<script src" not in lower and "<link" not in lower and "@import" not in lower
    assert re.findall(r"https?://[^\s\"'<]*", html) == ["http://"]  # the only address is built from state
    assert '"http://" + ip + ":" + port + "/callback?"' in html
    for rule in ("a === 10", "a === 172 && b >= 16 && b <= 31", "a === 192 && b === 168",
                 "p >= 1024 && p <= 65535", "/^[A-Za-z0-9_-]{16}$/"):
        assert rule in html
    assert "same Wi-Fi as your TV" in html


def test_idle_extra_connection_does_not_block_the_callback_or_stop():
    # Phone browsers open spare connections that send nothing.
    s = relay.CallbackServer("127.0.0.1")
    s.expect(STATE, LOGIN)
    s.start()
    idle = socket.create_connection(("127.0.0.1", s.port))
    try:
        time.sleep(0.5)  # let the server pick up the idle connection first
        status, _, _ = get(f"{base(s)}/callback?code=AUTHCODE123456&state={quote(STATE)}")
        assert status == 200 and s.result == ("code", "AUTHCODE123456")
        started = time.monotonic()
        s.stop()
        assert time.monotonic() - started < 3
    finally:
        idle.close()

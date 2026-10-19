"""MyAnimeList login relay (M13 spec §4): the phone hands the login code to the TV over the home Wi-Fi.

While the login screen is open (<= 5 minutes) the TV listens on its LAN address:
  GET /          -> redirect to the MyAnimeList login (the short address shown on the TV)
  GET /callback  -> code + state forwarded by pages/mal-login.html
One callback with the matching state (constant-time compare) ends it. Request lines are
never logged: they carry the authorization code.
"""

import hmac
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

NONCE = re.compile(r"^[A-Za-z0-9_-]{16}$")
IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")

PAGE = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>NovaFlix</title></head>'
        '<body style="font-family:sans-serif;background:#050b18;color:#f5f7ff;text-align:center;padding:48px 16px">'
        '<h1>NovaFlix</h1><p>{}</p></body></html>')
DONE = "Done — you can return to your TV."
DENIED = "Login cancelled. You can return to your TV."
EXPIRED = "This login link has expired. Start the login again on your TV."


def is_private(ip):
    match = IPV4.match(ip or "")
    if not match:
        return False
    a, b, c, d = (int(x) for x in match.groups())
    if max(a, b, c, d) > 255:
        return False
    return a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def valid_port(text):
    return bool(re.fullmatch(r"\d{1,5}", text or "")) and 1024 <= int(text) <= 65535


def parse_state(state):
    """(nonce, ip, port) when state has the shape NovaFlix makes, else None.
    pages/mal-login.html applies the same rules in JavaScript."""
    parts = (state or "").split("~")
    if len(parts) != 3 or not NONCE.match(parts[0]) or not is_private(parts[1]) or not valid_port(parts[2]):
        return None
    return parts[0], parts[1], int(parts[2])


def _udp():
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def lan_address(make_socket=None):
    """This device's address on the home network, or None.
    Connecting a UDP socket only picks the route; no packet is sent."""
    sock = (make_socket or _udp)()
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()
    return ip if is_private(ip) else None


class CallbackServer:
    def __init__(self, host):
        self.result = None  # ("code", code) or ("denied", error)
        self._state = None
        self._login_url = None
        self._lock = threading.Lock()
        self._thread = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 5  # a spare connection that sends nothing is dropped, never waited on

            def do_GET(self):  # noqa: N802 - http.server API
                owner._handle(self)

            def log_message(self, *args):
                pass  # the request line holds the authorization code

        # Threaded: phone browsers open spare connections; one idle socket must not block /callback.
        self._server = ThreadingHTTPServer((host, 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]

    def expect(self, state, login_url):
        self._state, self._login_url = state, login_url

    def start(self):
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.25},
                                        daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread:
            self._server.shutdown()
            self._thread.join(2)
            self._thread = None
        self._server.server_close()

    def _handle(self, request):
        parts = urlsplit(request.path)
        if parts.path == "/" and self._login_url and self.result is None:
            request.send_response(302)
            request.send_header("Location", self._login_url)
            request.send_header("Content-Length", "0")
            request.end_headers()
            return
        if parts.path != "/callback":
            self._reply(request, 404, EXPIRED)
            return
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        with self._lock:
            accepted = (self.result is None and self._state is not None
                        and hmac.compare_digest(query.get("state", "").encode(), self._state.encode()))
            if accepted:
                code = query.get("code")
                self.result = ("code", code) if code else ("denied", query.get("error") or "unknown")
        if not accepted:
            self._reply(request, 400, EXPIRED)
        else:
            self._reply(request, 200, DONE if self.result[0] == "code" else DENIED)

    @staticmethod
    def _reply(request, status, text):
        body = PAGE.format(text).encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "text/html; charset=utf-8")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)

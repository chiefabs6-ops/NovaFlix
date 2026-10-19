"""Phone keyboard for Search: the owner types on a phone, the TV receives the text over the home Wi-Fi.

Paired once: the code and port are saved in the profile (PAIRING_FILE), so the page the phone
bookmarked keeps working. While the NovaFlix window is open (gui/app.py) the TV listens on its LAN
address only (same approach as the MyAnimeList login relay, myanimelist/relay.py):
  GET  /p/<code>  -> the typing page (mobile browser, no app)
  POST /p/<code>  -> text=<title>&search=0|1 from that page
  GET  /p/<code>/manifest.webmanifest -> name, colours and icon for "Add to Home screen"
  GET  /icon.png (and the addresses phones ask for on their own) -> the NovaFlix icon, no code:
       public artwork, so a bookmark or home-screen shortcut shows the add-on's icon
<code> is compared in constant time. Requests from outside the private network ranges (and this
device) are refused; after MAX_BAD_REQUESTS wrong codes the server refuses everything until
NovaFlix is opened again. "Unpair phone" makes a new code. Typed text is never logged, and the
page carries nothing but the code: no logins, keys or tokens.
"""

import hmac
import json
import os
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from resources.lib.kodi import log
from resources.lib.myanimelist.relay import is_private

CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i: easy to type from the TV screen
CODE_LENGTH = 8
MAX_TEXT = 100
MAX_BODY = 2048
MAX_BAD_REQUESTS = 10
PAIRING_FILE = "phone_keyboard.json"
ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "novaflix-icon.png")
ICON_PATHS = {"/icon.png", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png", "/favicon.ico"}

EXPIRED = ('<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" '
           'content="width=device-width, initial-scale=1"><title>NovaFlix</title></head>'
           '<body style="font-family:sans-serif;background:#050b18;color:#f5f7ff;text-align:center;'
           'padding:48px 16px"><h1>NovaFlix</h1><p>This page no longer works. Choose '
           '"Use phone to type" on your TV and scan the new QR code.</p></body></html>')

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>NovaFlix</title>
<meta name="theme-color" content="#050b18"><meta name="apple-mobile-web-app-title" content="NovaFlix">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="icon" type="image/png" href="/icon.png"><link rel="apple-touch-icon" href="/icon.png">
<link rel="manifest" href="MANIFEST_URL">
<style>
body{margin:0;font-family:sans-serif;background:#050b18;color:#f5f7ff;padding:32px 16px}
h1{font-size:24px;margin:0 0 4px;background:linear-gradient(90deg,#a855f7,#00cfff);
-webkit-background-clip:text;background-clip:text;color:transparent}
p{color:#a8b5d1;margin:0 0 20px}
input{box-sizing:border-box;width:100%;font-size:20px;padding:14px;border-radius:12px;
border:2px solid #5a6bff;background:#0c1930;color:#f5f7ff;outline:none}
input:focus{border-color:#00cfff}
.row{display:flex;gap:12px;margin-top:16px}
button{flex:1;font-size:18px;padding:14px;border:0;border-radius:12px;color:#fff;background:#132443}
#go{background:linear-gradient(90deg,#702cff,#087bff)}
button:disabled{opacity:.4}
#state{margin-top:20px;min-height:24px;color:#00cfff}
.tip{margin-top:28px;font-size:14px}
</style></head><body>
<h1>NovaFlix</h1><p>Type an anime title, then press Search on TV.</p>
<form id="f"><input id="t" maxlength="100" autocomplete="off" autofocus placeholder="Anime title">
<div class="row"><button type="button" id="clear">Clear</button>
<button type="submit" id="go" disabled>Search on TV</button></div></form>
<div id="state">Connected to your TV</div>
<p class="tip">Tip: bookmark this page or add it to your home screen. Next time, open it while
NovaFlix is open on your TV: no QR code needed.</p>
<script>
var t=document.getElementById("t"),go=document.getElementById("go"),st=document.getElementById("state"),timer=null,done=false;
function send(search){
  if(done)return;
  var body="text="+encodeURIComponent(t.value)+"&search="+(search?1:0);
  fetch(location.pathname,{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:body})
  .then(function(r){return r.text().then(function(m){
    st.textContent=m;if(r.status==410){done=true;go.disabled=true;}});})
  .catch(function(){st.textContent="Could not reach the TV. Is NovaFlix open on your TV, on the same Wi-Fi?";});
}
t.addEventListener("input",function(){go.disabled=!t.value.trim();clearTimeout(timer);timer=setTimeout(function(){send(false);},300);});
document.getElementById("clear").addEventListener("click",function(){t.value="";go.disabled=true;send(false);t.focus();});
document.getElementById("f").addEventListener("submit",function(e){e.preventDefault();if(t.value.trim()){clearTimeout(timer);send(true);}});
</script></body></html>"""


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # Windows: SO_REUSEADDR would let a second server share the port; refuse it instead.
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # Elsewhere (Android, Linux) SO_REUSEADDR only lets the saved port open again at once
        # after NovaFlix closed it; a port another server listens on still fails.
        super().server_bind()


def manifest(code):
    return json.dumps({
        "name": "NovaFlix", "short_name": "NovaFlix", "start_url": f"/p/{code}", "scope": f"/p/{code}",
        "display": "standalone", "background_color": "#050b18", "theme_color": "#050b18",
        "icons": [{"src": "/icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}],
    })


def _icon():
    try:
        with open(ICON_FILE, "rb") as f:
            return f.read()
    except OSError:
        return None


def new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def clean(text):
    """One line of at most MAX_TEXT printable characters."""
    text = "".join(ch if ch.isprintable() else " " for ch in text or "")
    return " ".join(text.split())[:MAX_TEXT]


class PhoneKeyboard:
    """Thread-safe state read by the TV: connected, text, changed_at, locked; take_search()."""

    def __init__(self, host, code=None, port=0, clock=None):
        self._clock = clock or time.monotonic
        self.code = code or new_code()
        self.connected = False  # the phone reached this server since it started
        self.text = ""
        self.locked = False     # too many wrong codes: refuses everything until restarted
        self.changed_at = 0.0
        self._pending = None    # a search the phone asked for, not yet taken by the TV
        self._bad = 0
        self._lock = threading.Lock()
        self._thread = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 5  # a spare connection that sends nothing is dropped, never waited on

            def do_GET(self):  # noqa: N802 - http.server API
                owner._get(self)

            def do_POST(self):  # noqa: N802 - http.server API
                owner._post(self)

            def log_message(self, *args):
                pass  # request lines carry the pairing code

        try:
            self._server = _Server((host, port), Handler)
        except OSError:
            if not port:
                raise
            log.warning(f"phone keyboard: port {port} in use, using another (the phone scans once more)")
            self._server = _Server((host, 0), Handler)
        self.port = self._server.server_address[1]
        self.url = f"http://{host}:{self.port}/p/{self.code}"

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

    def take_search(self):
        """The title the phone asked to search for, once; None if none."""
        with self._lock:
            text, self._pending = self._pending, None
        return text

    # -- requests (server threads) -------------------------------------------------

    def _allowed(self, request):
        """True for the pairing code from a private-network address; counts wrong codes."""
        ip = request.client_address[0]
        if not (is_private(ip) or ip == "127.0.0.1"):
            return False
        path = request.path.split("?", 1)[0]
        if not path.startswith("/p/"):
            return False  # browser extras: not a guess at the code
        given = path[len("/p/"):].split("/", 1)[0]
        with self._lock:
            if self.locked:
                return False
            if hmac.compare_digest(given.encode(), self.code.encode()):
                return True
            self._bad += 1
            if self._bad >= MAX_BAD_REQUESTS:
                self.locked = True
            return False

    def _get(self, request):
        path = request.path.split("?", 1)[0]
        if path in ICON_PATHS and (is_private(request.client_address[0]) or request.client_address[0] == "127.0.0.1"):
            icon = _icon()
            if icon:
                self._send(request, 200, "image/png", icon, cache=True)
                return
        if not self._allowed(request):
            self._reply(request, 410, "text/html", EXPIRED)
            return
        if path.endswith("/manifest.webmanifest"):
            self._reply(request, 200, "application/manifest+json", manifest(self.code))
            return
        with self._lock:
            self.connected = True
            self.changed_at = self._clock()
        self._reply(request, 200, "text/html", PAGE.replace("MANIFEST_URL", f"/p/{self.code}/manifest.webmanifest"))

    def _post(self, request):
        if not self._allowed(request):
            self._reply(request, 410, "text/plain", "This page no longer works. Pair your phone again on the TV.")
            return
        try:
            length = int(request.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:
            self._reply(request, 413, "text/plain", "Too long.")
            return
        fields = {k: v[0] for k, v in parse_qs(request.rfile.read(length).decode("utf-8", "replace")).items()}
        text = clean(fields.get("text", ""))
        search = fields.get("search") == "1"
        if search and not text:
            self._reply(request, 400, "text/plain", "Type a title first.")
            return
        with self._lock:
            self.connected = True
            self.text = text
            self.changed_at = self._clock()
            if search:
                self._pending = text
        self._reply(request, 200, "text/plain", "Searching on your TV..." if search else
                    ("Ready: press Search on TV" if text else "Cleared"))

    @classmethod
    def _reply(cls, request, status, kind, text):
        cls._send(request, status, f"{kind}; charset=utf-8", text.encode("utf-8"))

    @staticmethod
    def _send(request, status, kind, body, cache=False):
        request.send_response(status)
        request.send_header("Content-Type", kind)
        request.send_header("Content-Length", str(len(body)))
        request.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        request.send_header("X-Content-Type-Options", "nosniff")
        request.send_header("Referrer-Policy", "no-referrer")
        request.end_headers()
        request.wfile.write(body)


# -- pairing, and the server that runs while NovaFlix is open -------------------------------------

_active = None
_active_lock = threading.Lock()


def _pairing_path(directory):
    return os.path.join(directory, PAIRING_FILE)


def load_pairing(directory):
    """{"code", "port"} of the paired phone, or None."""
    try:
        with open(_pairing_path(directory), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    code, port = data.get("code"), data.get("port")
    if not isinstance(code, str) or len(code) != CODE_LENGTH or not isinstance(port, int):
        return None
    return {"code": code, "port": port}


def _save_pairing(directory, code, port):
    with open(_pairing_path(directory), "w", encoding="utf-8") as f:
        json.dump({"code": code, "port": port}, f)


def active():
    """The running server, or None."""
    return _active


def start(directory, host, pair=False):
    """Run the server for the paired phone (pair=True: pair one first if none). Returns it, or None
    when nothing is paired. Raises OSError when no port can be opened."""
    global _active
    with _active_lock:
        if _active is not None:
            return _active
        pairing = load_pairing(directory)
        if pairing is None and not pair:
            return None
        keyboard = PhoneKeyboard(host, code=pairing["code"] if pairing else None,
                                 port=pairing["port"] if pairing else 0)
        if pairing is None or pairing["port"] != keyboard.port:
            _save_pairing(directory, keyboard.code, keyboard.port)
        keyboard.start()
        _active = keyboard
        return keyboard


def stop():
    global _active
    with _active_lock:
        keyboard, _active = _active, None
    if keyboard is not None:
        keyboard.stop()


def unpair(directory):
    """Forget the phone: its saved page stops working; the next pairing gets a new code."""
    stop()
    try:
        os.remove(_pairing_path(directory))
    except OSError:
        pass

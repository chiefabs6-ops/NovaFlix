# tests/test_phone_keyboard.py
"""Search: the phone keyboard server and pairing (net/phone_keyboard.py), the TV screen
(gui/actions.search_phone) and searches sent while no screen waits (actions.phone_search)."""

import http.client
import json
import os
from urllib.parse import urlencode

import pytest
import xbmc
import xbmcgui

from resources.lib.gui import actions
from resources.lib.kodi import paths
from resources.lib.myanimelist import relay
from resources.lib.net import phone_keyboard as pk


@pytest.fixture
def kb():
    keyboard = pk.PhoneKeyboard("127.0.0.1", code="abcdefgh")
    keyboard.start()
    yield keyboard
    keyboard.stop()


@pytest.fixture(autouse=True)
def no_server_left():
    yield
    pk.stop()


def call(port, method, path, fields=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    body = urlencode(fields) if fields is not None else None
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if body is not None else {}
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    result = resp.status, resp.read().decode("utf-8")
    conn.close()
    return result


# -- server ----------------------------------------------------------------------------------------

def test_page_needs_the_pairing_code(kb):
    status, page = call(kb.port, "GET", "/p/abcdefgh")
    assert status == 200 and "Search on TV" in page and "bookmark" in page and kb.connected
    assert call(kb.port, "GET", "/p/wrongcod")[0] == 410
    assert call(kb.port, "GET", "/")[0] == 410
    assert kb.url == f"http://127.0.0.1:{kb.port}/p/abcdefgh"


def test_bookmark_and_home_screen_get_the_novaflix_icon(kb):
    conn = http.client.HTTPConnection("127.0.0.1", kb.port, timeout=5)
    for path in ("/icon.png", "/apple-touch-icon.png", "/favicon.ico"):
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        assert resp.status == 200 and resp.getheader("Content-Type") == "image/png"
        assert body[1:4] == b"PNG" and body == open(pk.ICON_FILE, "rb").read()
    conn.close()
    assert not kb.locked and not kb.connected  # no code needed, and not a guess at it
    page = call(kb.port, "GET", "/p/abcdefgh")[1]
    assert 'rel="apple-touch-icon" href="/icon.png"' in page
    assert 'rel="manifest" href="/p/abcdefgh/manifest.webmanifest"' in page
    status, text = call(kb.port, "GET", "/p/abcdefgh/manifest.webmanifest")
    data = json.loads(text)
    assert status == 200 and data["short_name"] == "NovaFlix" and data["start_url"] == "/p/abcdefgh"
    assert data["icons"][0]["src"] == "/icon.png"
    assert call(kb.port, "GET", "/p/wrongcod/manifest.webmanifest")[0] == 410  # the address needs the code


def test_typed_text_arrives_cleaned_and_each_search_is_taken_once(kb):
    assert call(kb.port, "POST", "/p/abcdefgh", {"text": "  Frieren\n\x00 2 ", "search": "0"}) == (
        200, "Ready: press Search on TV")
    assert kb.text == "Frieren 2" and kb.take_search() is None
    assert call(kb.port, "POST", "/p/abcdefgh", {"text": "", "search": "1"})[0] == 400  # empty search refused
    assert call(kb.port, "POST", "/p/abcdefgh", {"text": "x" * 500, "search": "1"})[0] == 200
    assert kb.take_search() == "x" * pk.MAX_TEXT and kb.take_search() is None
    assert call(kb.port, "POST", "/p/abcdefgh", {"text": "Bocchi", "search": "1"})[0] == 200  # works again
    assert kb.take_search() == "Bocchi"


def test_wrong_codes_lock_the_server_but_browser_extras_do_not(kb):
    for _ in range(20):
        call(kb.port, "GET", "/robots.txt")
    assert not kb.locked
    for _ in range(pk.MAX_BAD_REQUESTS):
        call(kb.port, "POST", "/p/guessing", {"text": "x", "search": "1"})
    assert kb.locked and kb.take_search() is None
    assert call(kb.port, "GET", "/p/abcdefgh")[0] == 410  # even the right code once locked


def test_oversized_body_is_refused(kb):
    conn = http.client.HTTPConnection("127.0.0.1", kb.port, timeout=5)
    conn.request("POST", "/p/abcdefgh", body="text=" + "a" * 5000,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert conn.getresponse().status == 413
    conn.close()


def test_public_addresses_are_refused():
    keyboard = pk.PhoneKeyboard("127.0.0.1", code="abcdefgh")
    try:
        class Request:
            client_address = ("8.8.8.8", 5000)
            path = "/p/abcdefgh"
        assert not keyboard._allowed(Request())
        Request.client_address = ("192.168.1.20", 5000)
        assert keyboard._allowed(Request())
    finally:
        keyboard.stop()


def test_codes_are_random_and_easy_to_type():
    codes = {pk.new_code() for _ in range(50)}
    assert len(codes) == 50 and all(len(c) == pk.CODE_LENGTH and set(c) <= set(pk.CODE_ALPHABET) for c in codes)


# -- pairing -----------------------------------------------------------------------------------------

def test_pairing_is_saved_and_reused_with_the_same_address():
    directory = paths.profile_dir()
    assert pk.start(directory, "127.0.0.1") is None  # nothing paired: no server
    first = pk.start(directory, "127.0.0.1", pair=True)
    url = first.url
    assert pk.load_pairing(directory) == {"code": first.code, "port": first.port}
    pk.stop()                                         # NovaFlix closed
    assert pk.active() is None
    again = pk.start(directory, "127.0.0.1")          # NovaFlix opened again
    assert again.url == url and call(again.port, "GET", f"/p/{again.code}")[0] == 200


def test_busy_port_moves_the_pairing_to_another():
    directory = paths.profile_dir()
    blocker = pk.PhoneKeyboard("127.0.0.1")
    try:
        with open(os.path.join(directory, pk.PAIRING_FILE), "w", encoding="utf-8") as f:
            json.dump({"code": "abcdefgh", "port": blocker.port}, f)
        keyboard = pk.start(directory, "127.0.0.1")
        assert keyboard.code == "abcdefgh" and keyboard.port != blocker.port
        assert pk.load_pairing(directory)["port"] == keyboard.port
    finally:
        blocker.stop()


def test_unpair_stops_the_server_and_the_next_pairing_has_a_new_code():
    directory = paths.profile_dir()
    first = pk.start(directory, "127.0.0.1", pair=True)
    port, code = first.port, first.code
    pk.unpair(directory)
    assert pk.active() is None and pk.load_pairing(directory) is None
    with pytest.raises(OSError):
        call(port, "GET", f"/p/{code}")
    assert pk.start(directory, "127.0.0.1", pair=True).code != code


def test_unreadable_pairing_is_ignored():
    with open(os.path.join(paths.profile_dir(), pk.PAIRING_FILE), "w", encoding="utf-8") as f:
        f.write("{not json")
    assert pk.load_pairing(paths.profile_dir()) is None


# -- TV screen -----------------------------------------------------------------------------------------

class FakeKeyboard:
    def __init__(self):
        self.url = "http://192.168.1.86:5000/p/abcdefgh"
        self.connected, self.text, self.locked, self.changed_at = False, "", False, 0.0
        self.pending = None
        self.script = []  # one change per screen check

    def take_search(self):
        text, self.pending = self.pending, None
        return text


@pytest.fixture
def screen(monkeypatch):
    keyboard = FakeKeyboard()
    starts = []
    monkeypatch.setattr(relay, "lan_address", lambda: "192.168.1.86")
    monkeypatch.setattr(pk, "start", lambda directory, host, pair=False: starts.append(pair) or keyboard)
    monkeypatch.setattr(actions, "_clock", lambda: 10.0)
    from resources.lib.kodi import login_dialog
    shown = []

    def wait(self, seconds):
        shown.append(dict(self._window.properties))
        if keyboard.script:
            keyboard.script.pop(0)(keyboard)
            return False
        return True  # owner pressed Back
    monkeypatch.setattr(login_dialog.KodiLoginPresenter, "wait", wait)
    keyboard.shown, keyboard.starts = shown, starts
    return keyboard


def test_phone_screen_pairs_shows_typing_and_returns_the_search(screen):
    screen.pending = "old search"  # sent before the screen opened: not this one
    screen.script = [lambda k: setattr(k, "changed_at", 11.0),
                     lambda k: setattr(k, "text", "Frieren"),
                     lambda k: setattr(k, "pending", "Frieren")]
    assert actions.search_phone() == "Frieren"
    shown = screen.shown
    assert screen.starts == [True]
    assert shown[0]["heading"] == "Type on your phone" and shown[0]["url"] == screen.url
    assert shown[0]["status"].startswith("Waiting for your phone") and shown[0]["code"] == ""
    assert shown[2]["status"].startswith("Phone connected") and shown[2]["code"] == "Frieren"
    assert xbmcgui.xml_dialogs[-1].closed


def test_back_on_the_tv_closes_the_screen_only(screen):
    assert actions.search_phone() is None and xbmcgui.xml_dialogs[-1].closed


def test_idle_phone_screen_closes(screen, monkeypatch):
    times = iter([0.0] + [actions.PHONE_IDLE_S + 1.0] * 5)
    monkeypatch.setattr(actions, "_clock", lambda: next(times))
    assert actions.search_phone() is None and screen.shown == []


def test_too_many_wrong_codes_is_announced(screen):
    screen.locked = True
    assert actions.search_phone() is None
    assert "too many wrong addresses" in xbmcgui.notifications[-1][1]


def test_no_home_network_explains_instead(monkeypatch):
    from resources.lib.net import lan
    monkeypatch.setattr(lan, "lan_address", lambda: None)
    assert actions.search_phone() is None
    assert "No home network address" in xbmcgui.ok_calls[-1][1]


def test_unpair_asks_first(monkeypatch):
    forgotten = []
    monkeypatch.setattr(pk, "unpair", lambda directory: forgotten.append(directory))
    xbmcgui.yesno_answers.append(False)
    assert actions.unpair_phone() is False and forgotten == []
    xbmcgui.yesno_answers.append(True)
    assert actions.unpair_phone() is True and len(forgotten) == 1
    assert xbmcgui.notifications[-1][1] == "Phone unpaired"


# -- searches sent while no screen waits -------------------------------------------------------------------

def test_phone_search_waits_while_video_plays(monkeypatch):
    keyboard = FakeKeyboard()
    keyboard.pending = "Frieren"
    monkeypatch.setattr(pk, "active", lambda: keyboard)
    xbmc.cond_visibility["Player.HasVideo"] = True
    assert actions.phone_search() is None
    xbmc.cond_visibility["Player.HasVideo"] = False
    assert actions.phone_search() == "Frieren" and actions.phone_search() is None


def test_app_start_runs_the_server_only_for_a_paired_phone(monkeypatch):
    monkeypatch.setattr(relay, "lan_address", lambda: "127.0.0.1")
    actions.start_phone_keyboard()
    assert pk.active() is None
    pk.start(paths.profile_dir(), "127.0.0.1", pair=True)
    pk.stop()
    actions.start_phone_keyboard()
    assert pk.active() is not None


def test_home_screen_name_is_novaflix_not_the_address(kb):
    page = call(kb.port, "GET", "/p/abcdefgh")[1]
    assert "<title>NovaFlix</title>" in page and 'name="apple-mobile-web-app-title" content="NovaFlix"' in page
    data = json.loads(call(kb.port, "GET", "/p/abcdefgh/manifest.webmanifest")[1])
    assert data["name"] == data["short_name"] == "NovaFlix"

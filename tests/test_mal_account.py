"""M13: MyAnimeList account setting — QR login through the relay, check, log out."""

import os
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit

import pytest
import xbmcaddon
import xbmcgui
from helpers import MAL_CLIENT, MAL_TOKEN, FakeNet, mal_login

from resources.lib import router
from resources.lib.kodi import paths
from resources.lib.myanimelist import auth, relay
from resources.lib.views import mal_account

BASE = "plugin://plugin.video.aniverse/"
ADDON_DIR = os.path.join(os.path.dirname(__file__), "..", "plugin.video.aniverse")


def dispatch(path):
    router.dispatch([BASE + path, "-1", ""])


class FakeServer:
    def __init__(self, host):
        self.host, self.port, self.result = host, 41234, None
        self.state = self.login_url = None
        self.started = self.stopped = False

    def expect(self, state, login_url):
        self.state, self.login_url = state, login_url

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class Phone:
    """The TV dialog plus the owner's phone: by default the phone approves on the first wait."""

    def __init__(self):
        self.answer = ("code", "AUTHCODE123456")
        self.cancel = False
        self.servers = []
        self.info, self.updates, self.closed = None, [], False

    def server(self, host):
        self.servers.append(FakeServer(host))
        return self.servers[-1]

    def show(self, info):
        self.info = info

    def update(self, seconds):
        self.updates.append(seconds)

    def wait(self, seconds):
        if self.cancel:
            return True
        if self.answer is not None:
            self.servers[-1].result = self.answer
        return False

    def close(self):
        self.closed = True


@pytest.fixture
def phone(monkeypatch):
    xbmcaddon.settings["mal_client_id"] = MAL_CLIENT
    p = Phone()
    monkeypatch.setattr(relay, "lan_address", lambda: "192.168.1.86")
    monkeypatch.setattr(mal_account, "_server", p.server)
    monkeypatch.setattr(mal_account, "_presenter", lambda: p)
    return p


def linked():
    return auth.MalStore(paths.profile_dir()).linked


def test_settings_action_runs_the_account_route():
    tree = ET.parse(os.path.join(ADDON_DIR, "resources", "settings.xml"))
    setting = next(s for s in tree.iter("setting") if s.get("id") == "mal_account")
    assert setting.find("data").text == "RunPlugin(plugin://plugin.video.aniverse/mal/account)"
    assert router.ROUTES["mal/account"] == "resources.lib.views.mal_account:menu"


def test_login_shows_qr_and_short_address_then_stores_login(phone):
    net = FakeNet().route("oauth2/token", MAL_TOKEN).route("users/@me", {"name": "owner"})
    dispatch("mal/account")  # "Log in?" answered yes (fake default)
    server = phone.servers[0]
    assert server.host == "192.168.1.86" and server.started and server.stopped and phone.closed
    assert phone.info["url"] == "http://192.168.1.86:41234" and phone.info["qr"] == server.login_url
    assert phone.info["heading"] == "Log in to MyAnimeList"
    query = {k: v[0] for k, v in parse_qs(urlsplit(server.login_url).query).items()}
    assert query["state"] == server.state and server.state.endswith("~192.168.1.86~41234")
    sent = {k: v[0] for k, v in parse_qs(net.calls[0][2]).items()}
    assert sent["code"] == "AUTHCODE123456" and sent["code_verifier"] == query["code_challenge"]
    assert auth.MalStore(paths.profile_dir()).data["username"] == "owner"
    assert xbmcgui.notifications[-1][:2] == ("MyAnimeList", "Logged in as owner")


def test_no_client_id_offers_settings(phone):
    xbmcaddon.settings["mal_client_id"] = ""
    dispatch("mal/account")
    assert phone.servers == [] and xbmcaddon.opened_settings


def test_no_lan_address_explains(phone, monkeypatch):
    monkeypatch.setattr(relay, "lan_address", lambda: None)
    dispatch("mal/account")
    assert phone.servers == [] and "Wi-Fi or Ethernet" in xbmcgui.ok_calls[-1][1]


def test_cancel_on_tv_stores_nothing(phone):
    phone.cancel = True
    FakeNet()
    dispatch("mal/account")
    assert phone.servers[0].stopped and phone.closed and not linked() and xbmcgui.ok_calls == []


def test_timeout_stores_nothing(phone, monkeypatch):
    phone.answer = None
    times = iter([0, 100, 200, 301])
    monkeypatch.setattr(mal_account, "_clock", lambda: next(times))
    FakeNet()
    dispatch("mal/account")
    assert phone.updates == [200, 100] and phone.servers[0].stopped and not linked()


def test_deny_on_phone_says_cancelled(phone):
    phone.answer = ("denied", "access_denied")
    FakeNet()
    dispatch("mal/account")
    assert "cancelled" in xbmcgui.ok_calls[-1][1] and not linked()


def test_refused_token_names_both_setup_items(phone):
    FakeNet().route("oauth2/token", {"error": "invalid_client"}, status=401)
    dispatch("mal/account")
    text = xbmcgui.ok_calls[-1][1]
    assert "mal-login.html" in text and '"web"' in text and not linked()


def test_logged_in_menu_checks_and_logs_out():
    mal_login()
    FakeNet().route("users/@me", {"name": "owner"})
    xbmcgui.select_answers.append(0)
    dispatch("mal/account")
    assert xbmcgui.select_calls[-1][0] == "Logged in as owner"
    assert xbmcgui.ok_calls[-1][1] == "Logged in as owner"
    xbmcgui.select_answers.append(1)
    dispatch("mal/account")
    assert "Settings → API" in xbmcgui.yesno_calls[-1][1] and not linked()


def test_check_with_expired_login_says_so():
    mal_login()
    FakeNet().route("users/@me", {"error": "invalid_token"}, status=401).route(
        "oauth2/token", {"error": "invalid_grant"}, status=400)
    xbmcgui.select_answers.append(0)
    dispatch("mal/account")
    assert "expired" in xbmcgui.ok_calls[-1][1]


def test_real_debrid_login_screen_keeps_its_texts(monkeypatch):
    from resources.lib.kodi.login_dialog import KodiLoginPresenter
    presenter = KodiLoginPresenter()
    monkeypatch.setattr(presenter, "_make_qr", lambda url: "")
    presenter.show({"verification_url": "https://real-debrid.com/device", "user_code": "ABCD1234"})
    props = presenter._window.properties
    assert props["heading"] == "Connect Real-Debrid" and props["code"] == "ABCD1234"
    assert props["url"] == "https://real-debrid.com/device"
    presenter.close()

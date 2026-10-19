"""M5: Real-Debrid device login, refresh, status, disconnect, error mapping.

Response shapes come from live probes on 2026-10-10 (device/code fields,
pending credentials = nulls with HTTP 200, bad token = 401 error_code 8) and
the api.real-debrid.com docs. No real account is used.
"""

import json
import os

import pytest
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import errors, router
from resources.lib.debrid import auth, realdebrid
from resources.lib.debrid.realdebrid import RealDebrid
from resources.lib.kodi import paths
from resources.lib.views import account

BASE = "plugin://plugin.video.novaflix/"
NOW = 1_800_000_000.0

DEVICE = {
    "device_code": "DEVICECODE1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "user_code": "ABCD1234",
    "interval": 5,
    "expires_in": 900,
    "verification_url": "https://real-debrid.com/device",
    "direct_verification_url": "https://real-debrid.com/authorize?client_id=X245A4XAIBGVM&device_id=XYZ",
}
CREDS = {"client_id": "USERCLIENTID000000001", "client_secret": "USERSECRET00000000000000000001"}
TOKEN = {"access_token": "ACCESSTOKEN0000000000000000000001", "expires_in": 3600,
         "token_type": "Bearer", "refresh_token": "REFRESHTOKEN000000000000000000001"}
TOKEN2 = dict(TOKEN, access_token="ACCESSTOKEN0000000000000000000002")
USER = {"id": 1, "username": "owner", "type": "premium", "premium": 30 * 86400,
        "expiration": "2027-04-01T00:00:00.000Z", "points": 0}
SECRETS = [DEVICE["device_code"], CREDS["client_id"], CREDS["client_secret"],
           TOKEN["access_token"], TOKEN["refresh_token"], TOKEN2["access_token"]]


class Net:
    """Scripted Real-Debrid: a list of (method, path-substring, status, body) consumed in order per route."""

    def __init__(self):
        self.queue = {}
        self.calls = []
        from resources.lib.net import http
        http.set_transport(self)

    def on(self, method, part, status=200, body=None, times=1):
        self.queue.setdefault((method, part), []).extend([(status, body)] * times)
        return self

    def __call__(self, method, url, headers, body, timeout, context):
        self.calls.append((method, url, headers, body.decode() if body else ""))
        for (m, part), responses in self.queue.items():
            if m == method and part in url and responses:
                status, data = responses.pop(0) if len(responses) > 1 else responses[0]
                return status, {}, json.dumps(data).encode() if data is not None else b""
        raise AssertionError(f"unexpected {method} {url}")

    def count(self, part):
        return sum(1 for _, url, _, _ in self.calls if part in url)


class Presenter:
    def __init__(self, cancel_after=None):
        self.shown = None
        self.updates = []
        self.closed = False
        self.waits = 0
        self.cancel_after = cancel_after

    def show(self, info):
        self.shown = info

    def update(self, seconds_left):
        self.updates.append(seconds_left)

    def close(self):
        self.closed = True

    def wait(self, seconds):
        self.waits += 1
        auth._clock = lambda: NOW + self.waits * seconds
        return self.cancel_after is not None and self.waits >= self.cancel_after


@pytest.fixture(autouse=True)
def clocks(monkeypatch):
    monkeypatch.setattr(auth, "_clock", lambda: NOW)
    monkeypatch.setattr(realdebrid, "_clock", lambda: NOW)


def store():
    return auth.TokenStore(paths.profile_dir())


def connected_store(expires_at=NOW + 3600):
    s = store()
    s.save(client_id=CREDS["client_id"], client_secret=CREDS["client_secret"],
           access_token=TOKEN["access_token"], refresh_token=TOKEN["refresh_token"], expires_at=expires_at)
    return s


def all_logs():
    return "\n".join(m for _, m in xbmc.log_records)


# -- device login -------------------------------------------------------------

def login_net(pending=2):
    # Pending answers as observed live: 403 with null error fields.
    return (Net()
            .on("GET", "/device/code", body=DEVICE)
            .on("GET", "/device/credentials", status=403, body={"error": None, "error_code": None}, times=pending)
            .on("GET", "/device/credentials", body=CREDS)
            .on("POST", "/oauth/v2/token", body=TOKEN))


def test_device_login_happy_path_stores_tokens():
    net = login_net()
    p = Presenter()
    assert auth.run_device_login(store(), p, p.wait) is True
    assert p.shown["user_code"] == "ABCD1234" and p.closed
    saved = store().data
    assert saved["access_token"] == TOKEN["access_token"] and saved["refresh_token"] == TOKEN["refresh_token"]
    assert saved["client_id"] == CREDS["client_id"]
    assert saved["expires_at"] > NOW
    code_call = net.calls[0][1]
    assert "client_id=X245A4XAIBGVM" in code_call and "new_credentials=yes" in code_call
    token_body = net.calls[-1][3]
    assert "grant_type=http%3A%2F%2Foauth.net%2Fgrant_type%2Fdevice%2F1.0" in token_body
    assert f"code={DEVICE['device_code']}" in token_body


def test_device_login_cancel_stores_nothing():
    login_net(pending=10)
    p = Presenter(cancel_after=2)
    assert auth.run_device_login(store(), p, p.wait) is False
    assert p.closed and not store().connected


def test_device_login_expiry_stops_polling():
    net = Net().on("GET", "/device/code", body=dict(DEVICE, expires_in=12)).on(
        "GET", "/device/credentials", body={"client_id": None, "client_secret": None}, times=50)
    p = Presenter()
    assert auth.run_device_login(store(), p, p.wait) is False
    assert net.count("/device/credentials") <= 3
    assert not store().connected


def test_login_secrets_never_logged():
    login_net()
    p = Presenter()
    auth.run_device_login(store(), p, p.wait)
    logged = all_logs()
    assert "valid for 3600 s" in logged  # records the real expires_in (unknown D1)
    for secret in SECRETS[:5]:
        assert secret not in logged


def test_token_file_lives_in_profile_not_settings(kodi_profile):
    login_net()
    p = Presenter()
    auth.run_device_login(store(), p, p.wait)
    assert os.path.exists(os.path.join(paths.profile_dir(), auth.FILENAME))


# -- refresh --------------------------------------------------------------------

def test_proactive_refresh_before_expiry():
    connected_store(expires_at=NOW + 60)
    net = Net().on("POST", "/oauth/v2/token", body=TOKEN2).on("GET", "/rest/1.0/user", body=USER)
    RealDebrid(store()).user()
    assert net.count("/oauth/v2/token") == 1
    assert net.calls[-1][2]["Authorization"] == f"Bearer {TOKEN2['access_token']}"
    assert f"code={TOKEN['refresh_token']}" in net.calls[0][3]


def test_no_refresh_when_token_fresh():
    connected_store()
    net = Net().on("GET", "/rest/1.0/user", body=USER)
    RealDebrid(store()).user()
    assert net.count("/oauth/v2/token") == 0


def test_reactive_refresh_on_401_then_retry_once():
    connected_store()
    net = (Net()
           .on("GET", "/rest/1.0/user", status=401, body={"error": "bad_token", "error_code": 8})
           .on("GET", "/rest/1.0/user", body=USER)
           .on("POST", "/oauth/v2/token", body=TOKEN2))
    assert RealDebrid(store()).user()["username"] == "owner"
    assert net.count("/rest/1.0/user") == 2 and net.count("/oauth/v2/token") == 1


def test_second_401_after_refresh_raises_auth_error():
    connected_store()
    Net().on("GET", "/rest/1.0/user", status=401, body={"error": "bad_token", "error_code": 8}).on(
        "POST", "/oauth/v2/token", body=TOKEN2)
    with pytest.raises(errors.AuthError):
        RealDebrid(store()).user()


def test_refresh_rejected_raises_auth_error():
    connected_store(expires_at=NOW)
    Net().on("POST", "/oauth/v2/token", status=400, body={"error": "invalid_grant", "error_code": 2})
    with pytest.raises(errors.AuthError):
        RealDebrid(store()).user()


def test_not_connected_raises_auth_error():
    with pytest.raises(errors.AuthError):
        RealDebrid(store()).user()


# -- error mapping ----------------------------------------------------------------

@pytest.mark.parametrize("code,status", [(21, 503), (23, 503), (36, 503), (14, 403), (22, 403)])
def test_account_codes_become_account_errors(code, status):
    connected_store()
    Net().on("GET", "/rest/1.0/user", status=status, body={"error": "x", "error_code": code})
    with pytest.raises(errors.AccountError) as info:
        RealDebrid(store()).user()
    assert info.value.code == code


def test_403_without_code_is_account_problem():
    connected_store()
    Net().on("GET", "/rest/1.0/user", status=403, body={"error": "permission_denied"})
    with pytest.raises(errors.AccountError):
        RealDebrid(store()).user()


def test_rd_slow_down_code_is_rate_limited():
    connected_store()
    Net().on("GET", "/rest/1.0/user", status=429, body={"error": "too_many_requests", "error_code": 34})
    with pytest.raises(errors.RateLimited):
        RealDebrid(store()).user()


# -- account screen ------------------------------------------------------------------

def test_status_text_formats():
    assert account.status_text(None) == "Real-Debrid: not connected"
    text = account.status_text({"username": "owner", "type": "premium", "premium_until": NOW + 86400})
    assert text.startswith("Connected as owner · Premium until ")
    assert "free" in account.status_text({"username": "owner", "type": "free"})


def test_connect_view_says_connected_only_after_user_call(monkeypatch):
    login_net().on("GET", "/rest/1.0/user", body=USER)
    monkeypatch.setattr(account, "_presenter", lambda: Presenter())
    account.connect(None)
    assert xbmcgui.notifications[-1][1].startswith("Connected as owner")
    assert store().data["account"]["type"] == "premium"


def test_connect_view_status_failure_is_not_reported_as_connected(monkeypatch):
    login_net().on("GET", "/rest/1.0/user", status=503, body={"error": "x", "error_code": 25})
    monkeypatch.setattr(account, "_presenter", lambda: Presenter())
    account.connect(None)
    assert xbmcgui.notifications == []
    assert "could not confirm" in xbmcgui.ok_calls[-1][1]


def test_connect_view_warns_when_not_premium(monkeypatch):
    login_net().on("GET", "/rest/1.0/user", body=dict(USER, type="free", premium=0))
    monkeypatch.setattr(account, "_presenter", lambda: Presenter())
    account.connect(None)
    assert "not premium" in xbmcgui.ok_calls[-1][1]


def test_disconnect_revokes_and_clears():
    connected_store()
    net = Net().on("GET", "/disable_access_token", status=204, body=None)
    xbmcgui.yesno_answers.append(True)
    account.disconnect(None)
    assert net.count("/disable_access_token") == 1
    assert not store().connected
    assert "revoked" in xbmcgui.ok_calls[-1][1]


def test_disconnect_when_revoke_fails_is_truthful():
    connected_store()
    Net().on("GET", "/disable_access_token", status=503, body={"error": "x"}, times=3)
    xbmcgui.yesno_answers.append(True)
    account.disconnect(None)
    assert not store().connected
    assert "could not be reached" in xbmcgui.ok_calls[-1][1]


def test_disconnect_declined_keeps_login():
    connected_store()
    xbmcgui.yesno_answers.append(False)
    account.disconnect(None)
    assert store().connected


def test_account_menu_offers_connect_when_disconnected(monkeypatch):
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "rd/account", "-1", ""])
    assert "not connected" in xbmcgui.yesno_calls[-1][1]


def test_account_menu_shows_status_heading_when_connected():
    s = connected_store()
    s.save(account={"username": "owner", "type": "premium", "premium_until": NOW + 86400})
    router.dispatch([BASE + "rd/account", "-1", ""])
    heading, options = xbmcgui.select_calls[-1]
    assert heading.startswith("Connected as owner")
    assert options == ["Check account status", "Disconnect Real-Debrid"]


@pytest.fixture
def boom_route(monkeypatch):
    """A view that raises the given error type."""
    import sys, types

    def install(exc):
        module = types.ModuleType("tests.boom_view")

        def handle(req):
            raise exc

        module.handle = handle
        monkeypatch.setitem(sys.modules, "tests.boom_view", module)
        monkeypatch.setitem(router.ROUTES, "boom", "tests.boom_view:handle")
    return install


def test_torbox_rejected_key_points_to_settings(boom_route):
    boom_route(errors.AuthError("TorBox rejected the API key"))
    router.dispatch([BASE + "boom", "2", ""])
    heading, message = xbmcgui.yesno_calls[-1]
    assert heading == "TorBox" and "API key" in message
    assert xbmcaddon.opened_settings


def test_torbox_account_problem_names_torbox(boom_route):
    boom_route(errors.AccountError("TorBox: monthly download limit reached", "MONTHLY_LIMIT"))
    router.dispatch([BASE + "boom", "2", ""])
    assert xbmcgui.ok_calls[-1] == ("TorBox", "TorBox reports a problem with your account: monthly download limit reached.")


def test_router_turns_auth_error_into_reconnect_prompt(monkeypatch):
    xbmcaddon.settings["playback_service"] = 1  # Real-Debrid
    import sys, types
    module = types.ModuleType("tests.rd_view")

    def boom(req):
        raise errors.AuthError("expired")

    module.handle = boom
    monkeypatch.setitem(sys.modules, "tests.rd_view", module)
    monkeypatch.setitem(router.ROUTES, "rdboom", "tests.rd_view:handle")
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "rdboom", "2", ""])
    assert "Reconnect" in xbmcgui.yesno_calls[-1][1]
    assert xbmcplugin.end_calls[-1][1] is False


def test_router_turns_account_error_into_dialog(monkeypatch):
    import sys, types
    module = types.ModuleType("tests.rd_view2")

    def boom(req):
        raise errors.AccountError("Real-Debrid: traffic exhausted", 23)

    module.handle = boom
    monkeypatch.setitem(sys.modules, "tests.rd_view2", module)
    monkeypatch.setitem(router.ROUTES, "rdboom2", "tests.rd_view2:handle")
    router.dispatch([BASE + "rdboom2", "2", ""])
    assert "traffic exhausted" in xbmcgui.ok_calls[-1][1]


# -- service warning ---------------------------------------------------------------

def test_service_warns_once_per_day_when_premium_ends_soon():
    from resources.lib import service_main
    s = connected_store()
    s.save(account={"username": "owner", "type": "premium", "premium_until": NOW + 3 * 86400, "checked_at": NOW})
    service_main.check_real_debrid(paths.profile_dir(), now=NOW)
    service_main.check_real_debrid(paths.profile_dir(), now=NOW + 60)
    warnings = [n for n in xbmcgui.notifications if "Premium ends" in n[1]]
    assert len(warnings) == 1 and "3 day" in warnings[0][1]


def test_service_refreshes_stale_status_daily():
    from resources.lib import service_main
    s = connected_store(expires_at=NOW + 10 * 86400)
    s.save(account={"username": "owner", "type": "premium", "premium_until": NOW + 300 * 86400, "checked_at": NOW - 2 * 86400})
    net = Net().on("GET", "/rest/1.0/user", body=USER)
    service_main.check_real_debrid(paths.profile_dir(), now=NOW)
    assert net.count("/rest/1.0/user") == 1
    assert [n for n in xbmcgui.notifications if "Premium ends" in n[1]] == []


def test_service_does_nothing_when_disconnected():
    from resources.lib import service_main
    service_main.check_real_debrid(paths.profile_dir(), now=NOW)
    assert xbmcgui.notifications == []


def test_credentials_server_error_still_fails():
    Net().on("GET", "/device/code", body=DEVICE).on("GET", "/device/credentials", status=500, body={}, times=3)
    p = Presenter()
    with pytest.raises(errors.ServiceUnavailable):
        auth.run_device_login(store(), p, p.wait)
    assert p.closed


def test_report_error_works_outside_a_plugin_view():
    # Windows (M12) report errors without a plugin handle.
    try:
        raise errors.NetworkError("GET https://graphql.anilist.co failed: timeout")
    except errors.NetworkError as exc:
        router.report_error(exc, "home window")
    assert xbmcgui.notifications[-1][1] == "Couldn't load this. Check your internet connection and try again."
    assert xbmcplugin.end_calls == []

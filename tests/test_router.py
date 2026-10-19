import xbmc
import xbmcplugin

from resources.lib import router

BASE = "plugin://plugin.video.novaflix/"


def test_parse_root():
    req = router.parse([BASE, "7", ""])
    assert req.handle == 7
    assert req.path == ""
    assert req.params == {}


def test_parse_path_and_query():
    req = router.parse([BASE + "browse/genre/", "3", "?name=Action&page=2"])
    assert req.path == "browse/genre"
    assert req.params == {"name": "Action", "page": "2"}


def test_build_url_round_trip():
    url = router.build_url("browse/genre", name="Slice of Life", page=2)
    req = router.parse([url, "1", "?" + url.split("?", 1)[1]])
    assert req.path == "browse/genre"
    assert req.params == {"name": "Slice of Life", "page": "2"}


def test_build_url_without_params():
    assert router.build_url("") == BASE


def test_dispatch_calls_registered_view(monkeypatch):
    calls = []
    monkeypatch.setitem(router.ROUTES, "probe", "tests.probe_view:handle")

    import types, sys
    module = types.ModuleType("tests.probe_view")
    module.handle = lambda req: calls.append(req)
    monkeypatch.setitem(sys.modules, "tests.probe_view", module)

    router.dispatch([BASE + "probe", "5", "?x=1"])
    assert len(calls) == 1
    assert calls[0].params == {"x": "1"}


def test_dispatch_unknown_route_ends_directory_unsuccessfully():
    router.dispatch([BASE + "no/such/route", "9", ""])
    assert xbmcplugin.end_calls == [(9, False, False, False)]
    assert any("no/such/route" in msg for _, msg in xbmc.log_records)


def test_crashing_view_is_logged_redacted_and_reported(monkeypatch):
    import sys, types
    import xbmcgui
    from resources.lib import redact

    redact.register_secret("SENTINELTOKEN0123456789")
    module = types.ModuleType("tests.boom_view")

    def handle(req):
        raise RuntimeError("token SENTINELTOKEN0123456789 rejected")

    module.handle = handle
    monkeypatch.setitem(sys.modules, "tests.boom_view", module)
    monkeypatch.setitem(router.ROUTES, "boom", "tests.boom_view:handle")

    router.dispatch([BASE + "boom", "3", ""])

    assert xbmcplugin.end_calls == [(3, False, False, False)]
    assert xbmcgui.notifications and xbmcgui.notifications[0][2] == xbmcgui.NOTIFICATION_ERROR
    logged = "\n".join(msg for _, msg in xbmc.log_records)
    assert "RuntimeError" in logged
    assert "SENTINELTOKEN0123456789" not in logged


def test_auth_error_opens_torbox_settings():
    import xbmcaddon
    import xbmcgui
    from resources.lib import errors
    xbmcaddon.settings["playback_service"] = 1  # leftover value must not lead to Real-Debrid
    try:
        raise errors.AuthError("rejected")
    except errors.AuthError as exc:
        router.report_error(exc, "play")
    assert xbmcgui.yesno_calls and xbmcgui.yesno_calls[0][0] == "TorBox"
    assert xbmcaddon.opened_settings == [True]


def test_rejected_tmdb_key_names_tmdb_not_torbox():
    import xbmcaddon
    import xbmcgui
    from resources.lib import errors
    try:
        raise errors.AuthError("TMDB rejected the key")
    except errors.AuthError as exc:
        router.report_error(exc, "title page")
    assert xbmcgui.yesno_calls[-1][0] == "TMDB" and "TMDB" in xbmcgui.yesno_calls[-1][1]
    assert xbmcaddon.opened_settings == [True]

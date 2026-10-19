import xbmc
import xbmcgui

from resources.lib import service_main
from resources.lib.kodi import paths
from resources.lib.myanimelist import sync


def test_service_runs_until_abort_and_logs_lifecycle():
    xbmc.Monitor.waits_before_abort = 2
    service_main.run()
    messages = [msg for _, msg in xbmc.log_records]
    assert any("service started" in m for m in messages)
    assert any("service stopped" in m for m in messages)


def test_log_lines_are_prefixed_with_addon_id():
    xbmc.Monitor.waits_before_abort = 0
    service_main.run()
    assert all(msg.startswith("[plugin.video.novaflix]") for _, msg in xbmc.log_records)


def test_service_sends_mal_changes_when_woken(monkeypatch):
    started = []
    monkeypatch.setattr(sync, "start_drain", lambda d: started.append(d) or True)
    xbmcgui.Window().setProperty(sync.KICK_PROPERTY, "1")
    xbmc.Monitor.waits_before_abort = 0
    service_main.run()
    assert paths.profile_dir() in started
    assert sync.KICK_PROPERTY not in xbmcgui.window_properties


def test_expired_mal_login_is_reminded_by_the_service():
    from helpers import mal_login
    from resources.lib.myanimelist import auth
    auth.expire(mal_login())
    service_main.housekeeping()
    service_main.housekeeping()
    assert [n[1] for n in xbmcgui.notifications].count("MyAnimeList login expired — log in again in Settings.") == 1

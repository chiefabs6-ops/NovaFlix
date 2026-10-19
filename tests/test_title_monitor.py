"""Player monitor for TMDB movies and episodes (Plan 3, Task 7): history, Up next across seasons."""

import copy
import json

import pytest
import xbmc
import xbmcaddon
import xbmcgui

from helpers import FakeNet, fixture
from resources.lib.kodi import paths
from resources.lib.playback import monitor as monitor_mod
from resources.lib.storage.watching import WatchHistory

LENGTH = 2800.0
TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"


def tmdb_net(seasons=None):
    tv = copy.deepcopy(fixture("tmdb/tv_1396.json"))
    if seasons is not None:
        tv["seasons"] = [s for s in tv["seasons"] if s["season_number"] in seasons]
    return (FakeNet().route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
            .route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json"))
            .route("/3/tv/1396", tv)
            .route("/3/movie/438631", fixture("tmdb/movie_438631.json")))


@pytest.fixture
def mon(monkeypatch):
    monkeypatch.setattr(monitor_mod.PlaybackMonitor, "_background", lambda self, target, *args: target(*args))
    xbmcaddon.settings.update(tmdb_token=TOKEN, audio_language=2)  # Kodi's own audio choice: no JSON-RPC needed
    presearched = []
    from resources.lib.views import watch
    monkeypatch.setattr(watch, "presearch", lambda title, season, episode, cancelled=None:
                        presearched.append((title.key, season, episode)))
    m = monitor_mod.PlaybackMonitor(paths.profile_dir())
    m.presearched = presearched
    return m


def start(m, payload):
    xbmcgui.Window().setProperty(monitor_mod.HANDOFF_PROPERTY, json.dumps(payload))
    xbmc.Player.playing, xbmc.Player.total, xbmc.Player.time = True, LENGTH, 0.0
    m.onAVStarted()


def play_to(m, position, now):
    xbmc.Player.time = position
    m.tick(now)


def test_title_session_saves_to_watch_history(mon):
    tmdb_net()
    start(mon, {"type": "tv", "id": 1396, "season": 2, "episode": 3})
    play_to(mon, 100, 0)
    play_to(mon, 600, 31)
    assert WatchHistory(paths.profile_dir()).states("tv", 1396) == {(2, 3): (600, LENGTH, False)}
    play_to(mon, 2700, 40)
    mon.onPlayBackEnded()
    assert WatchHistory(paths.profile_dir()).states("tv", 1396)[(2, 3)][2] is True


def test_up_next_crosses_season(mon):
    tmdb_net()
    start(mon, {"type": "tv", "id": 1396, "season": 1, "episode": 7})
    play_to(mon, LENGTH - 89, 0)
    assert mon.presearched == [("tv:1396", 2, 1)]
    dialog = xbmcgui.xml_dialogs[-1]
    assert dialog.properties["text"] == "Next: S2 E1"
    assert not any("PlayMedia" in b for b in xbmc.builtins_executed)  # never auto-plays (DEC-004)
    dialog.onClick(9000)
    mon.onPlayBackStopped()
    mon.tick(1)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=2&e=1)"


def test_no_up_next_after_last_aired(mon):
    tmdb_net(seasons={0, 1, 2})
    last = len(fixture("tmdb/tv_1396_season_2.json")["episodes"])
    start(mon, {"type": "tv", "id": 1396, "season": 2, "episode": last})
    play_to(mon, LENGTH - 89, 0)
    assert mon.presearched == [] and not any(d.properties.get("text") for d in xbmcgui.xml_dialogs)
    assert not any(level >= xbmc.LOGERROR for level, _ in xbmc.log_records)


def test_movie_has_no_up_next(mon):
    tmdb_net()
    start(mon, {"type": "movie", "id": 438631, "season": 0, "episode": 0})
    play_to(mon, LENGTH - 89, 0)
    assert mon.presearched == [] and not xbmcgui.xml_dialogs
    play_to(mon, 1000, 31)
    assert WatchHistory(paths.profile_dir()).states("movie", 438631) == {(0, 0): (1000, LENGTH, False)}


def test_title_playback_error_offers_watch_url(mon):
    tmdb_net()
    start(mon, {"type": "tv", "id": 1396, "season": 2, "episode": 3})
    mon.onPlayBackError()
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=2&e=3)"


def test_end_episode_for_a_title_only_stops(mon):
    tmdb_net()
    start(mon, {"type": "tv", "id": 1396, "season": 1, "episode": 7})
    play_to(mon, LENGTH - 89, 0)
    xbmcgui.xml_dialogs[-1].onClick(9001)  # End episode
    mon.onPlayBackStopped()
    mon.tick(1)
    assert monitor_mod.OPEN_SHOW_PROPERTY not in xbmcgui.window_properties
    assert not any("launch" in b or "ActivateWindow" in b for b in xbmc.builtins_executed)

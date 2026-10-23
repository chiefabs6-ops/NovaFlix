"""Player monitor and session timing: history, audio/subtitles, resume, Up next buttons and transitions."""

import json

import pytest
import xbmc
import xbmcaddon
import xbmcgui

from helpers import FakeNet, fixture
from resources.lib.kodi import paths
from resources.lib.playback import monitor as monitor_mod, streams
from resources.lib.playback.session import Session
from resources.lib.storage.watching import WatchHistory

LENGTH = 2800.0
TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"
BB_S1E7 = {"type": "tv", "id": 1396, "season": 1, "episode": 7}
NEXT_URL = "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=2&e=1)"


# -- session timing -----------------------------------------------------------------

def test_position_saved_every_30_seconds():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], None)
    saves = [t for t in range(0, 125) if ("save",) in s.tick(t, t)]
    assert saves == [30, 60, 90, 120]


def test_up_next_at_ending_start_else_90_seconds_before_end():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [{"type": "ed", "start": 2600.0, "end": 2700.0}], (1, 4))
    assert s.upnext_at == 2600.0
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], (2, 1))
    assert s.upnext_at == LENGTH - 90
    assert ("upnext", (2, 1)) not in s.tick(LENGTH - 91, 1)
    assert ("upnext", (2, 1)) in s.tick(LENGTH - 89, 2)
    assert ("upnext", (2, 1)) not in s.tick(LENGTH - 80, 3)  # offered once


def test_no_up_next_without_next_episode_or_for_short_clips():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], None)
    assert s.upnext_at is None
    s = Session("tv", 1, 1, 3)
    s.prepare(120, [], (1, 4))
    assert s.upnext_at is None


def test_skip_offered_once_inside_interval_only():
    s = Session("tv", 1, 1, 3)
    op = {"type": "op", "start": 60.0, "end": 150.0}
    s.prepare(LENGTH, [op], None)
    assert s.tick(59, 0) == []
    assert ("skip", op) in s.tick(61, 1)
    assert s.tick(62, 2) == []


# -- audio / subtitles ----------------------------------------------------------------

JPN = {"index": 0, "language": "jpn", "name": "Japanese", "isdefault": True}
ENG = {"index": 1, "language": "eng", "name": "English", "isdefault": False}


def test_pick_audio_prefers_language_and_falls_back_to_kodi():
    assert streams.pick_audio([JPN, ENG], "eng", current=0) == 1
    assert streams.pick_audio([JPN, ENG], "eng", current=1) is None
    assert streams.pick_audio([JPN], "eng", current=0) is None
    assert streams.pick_audio([JPN, ENG], None, current=0) is None


@pytest.mark.parametrize("subs, expected", [
    ([{"index": 0, "language": "eng", "name": "Full Subtitles"},
      {"index": 1, "language": "eng", "name": "Signs & Songs"}], ("on", 1)),
    ([{"index": 0, "language": "eng", "name": "English", "isforced": True}], ("on", 0)),
    ([{"index": 0, "language": "eng", "name": "Full Subtitles"}], ("off", None)),
])
def test_pick_forced_subtitles(subs, expected):
    assert streams.pick_subtitle(subs) == expected


# -- monitor with fake player ------------------------------------------------------------

@pytest.fixture
def mon(monkeypatch):
    monkeypatch.setattr(monitor_mod.PlaybackMonitor, "_background", lambda self, target, *args: target(*args))
    xbmcaddon.settings["tmdb_token"] = TOKEN
    from resources.lib.views import watch
    monkeypatch.setattr(watch, "presearch", lambda title, season, episode, cancelled=None: None)
    xbmc.jsonrpc_results.update({
        "Player.GetActivePlayers": [{"playerid": 1, "type": "video"}],
        "Player.GetProperties": {"audiostreams": [JPN, ENG], "currentaudiostream": JPN,
                                 "subtitles": [{"index": 0, "language": "eng", "name": "Full"},
                                               {"index": 1, "language": "eng", "name": "Forced", "isforced": True}]},
    })
    (FakeNet().route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
     .route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json"))
     .route("/3/tv/1396", fixture("tmdb/tv_1396.json")))
    return monitor_mod.PlaybackMonitor(paths.profile_dir())


def start(m, payload=None, **extra):
    xbmcgui.Window().setProperty(monitor_mod.HANDOFF_PROPERTY, json.dumps(dict(payload or BB_S1E7, **extra)))
    xbmc.Player.playing, xbmc.Player.total, xbmc.Player.time = True, LENGTH, 0.0
    m.onAVStarted()


def play_to(m, position, now):
    xbmc.Player.time = position
    m.tick(now)


def states():
    return WatchHistory(paths.profile_dir()).states("tv", 1396)


def test_start_sets_english_audio_and_forced_subtitles(mon):
    start(mon)
    calls = dict(xbmc.jsonrpc_calls)
    assert calls["Player.SetAudioStream"] == {"playerid": 1, "stream": 1}
    assert calls["Player.SetSubtitle"] == {"playerid": 1, "subtitle": 1, "enable": True}
    assert monitor_mod.HANDOFF_PROPERTY not in xbmcgui.window_properties


def test_kodi_default_audio_setting_changes_nothing(mon):
    xbmcaddon.settings["audio_language"] = 1
    start(mon)
    assert not any(m.startswith("Player.Set") for m, _ in xbmc.jsonrpc_calls)


def test_old_audio_setting_value_is_kodi_default(mon):
    xbmcaddon.settings["audio_language"] = 2  # "Kodi default" in 0.1.0 (Japanese was option 1)
    start(mon)
    assert not any(m.startswith("Player.Set") for m, _ in xbmc.jsonrpc_calls)


def test_playback_without_handoff_is_ignored(mon):
    xbmc.Player.playing, xbmc.Player.total = True, LENGTH
    mon.onAVStarted()
    assert mon.session is None
    mon.onPlayBackStopped()
    assert states() == {}


def test_progress_saved_during_playback_and_on_stop(mon):
    start(mon)
    play_to(mon, 100, 0)
    play_to(mon, 600, 31)
    assert states() == {(1, 7): (600, LENGTH, False)}
    play_to(mon, 700, 40)
    xbmc.Player.playing = False
    mon.onPlayBackStopped()
    assert states() == {(1, 7): (700, LENGTH, False)}


def test_file_without_english_audio_is_announced(mon):
    xbmc.jsonrpc_results["Player.GetProperties"] = {"audiostreams": [JPN], "currentaudiostream": JPN, "subtitles": []}
    start(mon)
    assert xbmcgui.notifications[-1][1] == "This file has no English audio track"


def test_playback_error_offers_another_source(mon):
    start(mon)
    xbmcgui.yesno_answers.append(True)
    mon.onPlayBackError()
    assert "Choose another source" in xbmcgui.yesno_calls[-1][1]
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=1&e=7)"


def test_list_refreshes_after_stop_when_showing_novaflix(mon):
    xbmc.info_labels["Container.FolderPath"] = "plugin://plugin.video.novaflix/"
    start(mon)
    play_to(mon, 700, 0)
    mon.onPlayBackStopped()
    assert "Container.Refresh" in xbmc.builtins_executed


def test_resume_position_is_sought_after_start(mon):
    start(mon, resume_s=754)
    assert xbmc.Player.seeks == [754]


def test_resume_too_close_to_the_end_starts_normally(mon):
    start(mon, resume_s=int(LENGTH) - 10)
    assert xbmc.Player.seeks == []


# -- Up next buttons: stop first, then one transition ------------------------------------------

class Key:
    def __init__(self, action_id):
        self.action_id = action_id

    def getId(self):
        return self.action_id


def up_next(m):
    start(m)
    play_to(m, LENGTH - 89, 0)
    return xbmcgui.xml_dialogs[-1]


def test_up_next_has_end_episode_next_to_choose_source(mon):
    dialog = up_next(mon)
    assert (dialog.properties["button"], dialog.properties["button2"]) == ("Choose source", "End episode")
    dialog.onAction(Key(1))  # left: to End episode, the prompt stays
    assert not dialog.closed
    dialog.onAction(Key(92))
    assert dialog.closed


def test_choose_source_stops_the_episode_before_the_source_list(mon):
    xbmc.Player.stop_closes = False  # Kodi closes the player a moment later
    dialog = up_next(mon)
    dialog.onClick(9000)
    assert xbmc.Player.stops == 1 and dialog.closed
    mon.tick(1)
    assert NEXT_URL not in xbmc.builtins_executed
    xbmc.Player.playing = False
    mon.onPlayBackStopped()
    assert states()[(1, 7)][2] is True
    mon.tick(2)
    mon.tick(3)
    assert xbmc.builtins_executed.count(NEXT_URL) == 1


def test_choose_source_without_a_stop_event_still_saves_and_continues(mon):
    dialog = up_next(mon)
    dialog.onClick(9000)
    mon.tick(1)
    assert mon.session is None and states()[(1, 7)][2] is True
    assert xbmc.builtins_executed[-1] == NEXT_URL


def test_repeated_presses_run_one_transition(mon):
    dialog = up_next(mon)
    dialog.onClick(9000)
    dialog.onClick(9000)
    dialog.onClick(9001)
    mon._begin_transition("end", Session("tv", 1396, 1, 7))  # a second prompt's press while the first runs
    mon.tick(1)
    assert xbmc.Player.stops == 1 and xbmc.builtins_executed.count(NEXT_URL) == 1
    assert monitor_mod.OPEN_SHOW_PROPERTY not in xbmcgui.window_properties


def test_player_that_will_not_stop_starts_nothing(mon):
    xbmc.Player.stop_closes = False
    dialog = up_next(mon)
    dialog.onClick(9000)
    mon.tick(100)
    mon.tick(100 + monitor_mod.STOP_WAIT_S)
    assert NEXT_URL not in xbmc.builtins_executed
    assert xbmcgui.notifications[-1][1] == "The episode did not stop. Try again."


def test_end_episode_returns_to_the_open_novaflix_window(mon):
    xbmcgui.Window(10000).setProperty(monitor_mod.GUI_PROPERTY, "true")
    dialog = up_next(mon)
    session = mon.session
    dialog.onClick(9001)
    assert xbmc.Player.stops == 1 and session.cancelled
    assert xbmcgui.Window(10000).getProperty(monitor_mod.OPEN_SHOW_PROPERTY) == "tv:1396"
    mon.onPlayBackStopped()
    mon.tick(1)
    assert not any("PlayMedia" in b or "RunPlugin" in b for b in xbmc.builtins_executed)
    assert states()[(1, 7)][2] is True


# -- Up next on the credits / last chapter (owner, 2026-10-19) ------------------------------------

def test_up_next_at_a_credits_chapter():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], (1, 4))
    s.chapter(5, 6, "End Credits", 2400)
    assert ("upnext", (1, 4)) in s.tick(2400, 1)


def test_up_next_at_the_last_chapter_near_the_end():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], (1, 4))
    s.chapter(8, 8, "Chapter 8", 2500)
    assert ("upnext", (1, 4)) in s.tick(2500, 1)


def test_last_chapter_far_from_the_end_offers_up_next_ten_minutes_before_the_end():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], (1, 4))
    s.chapter(3, 3, "Chapter 3", 1200)  # 26 minutes left: still the episode itself
    assert s.tick(1200, 1) == [] and s.upnext_at == LENGTH - 600
    assert ("upnext", (1, 4)) in s.tick(LENGTH - 599, 2)


def test_no_chapters_keeps_the_ninety_second_fallback():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], (1, 4))
    assert s.upnext_at == LENGTH - 90


def test_single_chapter_or_no_next_episode_changes_nothing():
    s = Session("tv", 1, 1, 3)
    s.prepare(LENGTH, [], (1, 4))
    s.chapter(1, 1, "", 2700)
    assert s.upnext_at == LENGTH - 90
    s = Session("movie", 1, 0, 0)
    s.prepare(LENGTH, [], None)
    s.chapter(8, 8, "Credits", 2700)
    assert s.upnext_at is None


def test_monitor_offers_up_next_when_kodi_enters_the_credits_chapter(mon):
    start(mon)
    xbmc.info_labels.update({"Player.Chapter": "7", "Player.ChapterCount": "8", "Player.ChapterName": "Credits"})
    play_to(mon, 2450, 0)
    assert xbmcgui.xml_dialogs and xbmcgui.xml_dialogs[-1].properties["text"] == "Next: S2 E1"


def test_up_next_shows_the_saved_next_episode(mon):
    from resources.lib.storage.cache import Cache
    Cache(paths.profile_dir()).set("tmdb:season:1396:2", [
        {"tmdb_id": 1396, "season": 2, "number": 1, "title": "Seven Thirty-Seven", "overview": "Walt and Jesse.",
         "air_date": "2009-03-08", "still": "https://image.tmdb.org/t/p/w300/s.jpg", "runtime_min": 47, "rating": 8.4}],
        3600)
    xbmc.info_labels.update({"Player.Chapter": "7", "Player.ChapterCount": "8", "Player.ChapterName": "Credits"})
    start(mon)
    play_to(mon, 2450, 0)
    props = xbmcgui.xml_dialogs[-1].properties
    assert props["text"] == "Next: S2 E1" and props["title"] == "Seven Thirty-Seven"
    assert props["plot"] == "Walt and Jesse." and props["art"].endswith("/s.jpg")


def test_up_next_without_saved_details_shows_the_number_only(mon, monkeypatch):
    from resources.lib.metadata.library import Library
    monkeypatch.setattr(Library, "cached_season_episodes", lambda self, title, season: None)
    xbmc.info_labels.update({"Player.Chapter": "7", "Player.ChapterCount": "8", "Player.ChapterName": "Credits"})
    start(mon)
    play_to(mon, 2450, 0)
    props = xbmcgui.xml_dialogs[-1].properties
    assert props["text"] == "Next: S2 E1" and (props["title"], props["plot"], props["art"]) == ("", "", "")

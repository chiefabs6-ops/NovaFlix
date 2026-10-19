"""Player monitor (DEC-026/027/028/030/041, SEC-15) with fake player events."""

import json

import pytest
import xbmc
import xbmcaddon
import xbmcgui

from helpers import FakeNet, mal_login
from resources.lib.kodi import paths
from resources.lib.metadata import aniskip, catalog
from resources.lib.myanimelist import sync
from resources.lib.models import Show
from resources.lib.playback import monitor as monitor_mod, streams
from resources.lib.playback.session import Session
from resources.lib.storage.history import History

LENGTH = 1440.0
ANISKIP = {"found": True, "statusCode": 200, "results": [
    {"interval": {"startTime": 60.0, "endTime": 150.0}, "skipType": "op", "episodeLength": 1441.2},
    {"interval": {"startTime": 1320.0, "endTime": 1410.0}, "skipType": "ed", "episodeLength": 1439.0},
]}


# -- session timing -----------------------------------------------------------------

def test_position_saved_every_30_seconds():
    s = Session(1, 3)
    s.prepare(LENGTH, [], False)
    saves = [t for t in range(0, 125) if ("save",) in s.tick(t, t)]
    assert saves == [30, 60, 90, 120]


def test_up_next_at_ending_start_else_90_seconds_before_end():
    s = Session(1, 3)
    s.prepare(LENGTH, [{"type": "ed", "start": 1320.0, "end": 1410.0}], True)
    assert s.upnext_at == 1320.0
    s = Session(1, 3)
    s.prepare(LENGTH, [], True)
    assert s.upnext_at == LENGTH - 90
    assert ("upnext", 4) not in s.tick(LENGTH - 91, 1)
    assert ("upnext", 4) in s.tick(LENGTH - 89, 2)
    assert ("upnext", 4) not in s.tick(LENGTH - 80, 3)  # offered once


def test_no_up_next_without_next_episode_or_for_short_clips():
    s = Session(1, 3)
    s.prepare(LENGTH, [], False)
    assert s.upnext_at is None
    s = Session(1, 3)
    s.prepare(120, [], True)
    assert s.upnext_at is None


def test_skip_offered_once_inside_interval_only():
    s = Session(1, 3)
    op = {"type": "op", "start": 60.0, "end": 150.0}
    s.prepare(LENGTH, [op], False)
    assert s.tick(59, 0) == []
    assert ("skip", op) in s.tick(61, 1)
    assert s.tick(62, 2) == []
    s2 = Session(1, 3)
    s2.prepare(LENGTH, [op], False)
    assert s2.tick(148, 0) == []  # last seconds: too late to offer


# -- audio / subtitles ----------------------------------------------------------------

JPN = {"index": 0, "language": "jpn", "name": "Japanese", "isdefault": True}
ENG = {"index": 1, "language": "eng", "name": "English", "isdefault": False}


def test_pick_audio_prefers_language_and_falls_back_to_kodi():
    assert streams.pick_audio([JPN, ENG], "eng", current=0) == 1
    assert streams.pick_audio([JPN, ENG], "eng", current=1) is None   # already playing
    assert streams.pick_audio([JPN], "eng", current=0) is None         # absent: Kodi default
    assert streams.pick_audio([JPN, ENG], None, current=0) is None     # "Kodi default" setting
    untagged = {"index": 2, "language": "", "name": "English 5.1"}
    assert streams.pick_audio([JPN, untagged], "eng", current=0) == 2


@pytest.mark.parametrize("subs, expected", [
    ([{"index": 0, "language": "eng", "name": "Full Subtitles"},
      {"index": 1, "language": "eng", "name": "Signs & Songs"}], ("on", 1)),
    ([{"index": 0, "language": "eng", "name": "English", "isforced": True}], ("on", 0)),
    ([{"index": 0, "language": "eng", "name": "Full Subtitles"}], ("off", None)),
    ([{"index": 0, "language": "eng", "name": "Signs"}, {"index": 1, "language": "eng", "name": "Songs"}],
     ("off", None)),                                                          # ambiguous
    ([{"index": 0, "language": "por", "name": "Signs & Songs"}], ("off", None)),
])
def test_pick_signs_and_songs(subs, expected):
    assert streams.pick_subtitle(subs) == expected


# -- AniSkip --------------------------------------------------------------------------

def test_aniskip_tolerance_accepts_close_and_rejects_other_cuts():
    intervals = [{"type": "op", "start": 60, "end": 150, "length": 1441.2},
                 {"type": "ed", "start": 1300, "end": 1390, "length": 1420.0}]
    assert [i["type"] for i in aniskip.matching(intervals, LENGTH)] == ["op"]


def test_aniskip_lookup_cached_and_failure_ignored():
    net = FakeNet().route("api.aniskip.com", ANISKIP)
    first = aniskip.skip_times(paths.profile_dir(), 52991, 3, LENGTH)
    second = aniskip.skip_times(paths.profile_dir(), 52991, 3, LENGTH)
    assert [i["type"] for i in first] == ["op", "ed"] and first == second
    assert net.count("aniskip") == 1
    assert "episodeLength=1440" in net.calls[0][1]
    FakeNet().route("api.aniskip.com", OSError("down"))
    assert aniskip.skip_times(paths.profile_dir(), 52991, 4, LENGTH) == []


def test_aniskip_not_found_is_a_quiet_miss():
    FakeNet().route("api.aniskip.com", {"found": False}, status=404)
    assert aniskip.skip_times(paths.profile_dir(), 52991, 5, LENGTH) == []


# -- monitor with fake player ------------------------------------------------------------

@pytest.fixture
def mon(monkeypatch):
    # Background work runs inline so tests are deterministic.
    monkeypatch.setattr(monitor_mod.PlaybackMonitor, "_background", lambda self, target, *args: target(*args))
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, _id: Show(
        anilist_id=154587, title="Frieren", mal_id=52991, format="TV", status="FINISHED", episodes_total=28))
    presearched = []
    from resources.lib.views import sources
    monkeypatch.setattr(sources, "presearch", lambda show, number, cancelled=None: presearched.append(number))
    xbmc.jsonrpc_results.update({
        "Player.GetActivePlayers": [{"playerid": 1, "type": "video"}],
        "Player.GetProperties": {"audiostreams": [JPN, ENG], "currentaudiostream": JPN,
                                 "subtitles": [{"index": 0, "language": "eng", "name": "Full"},
                                               {"index": 1, "language": "eng", "name": "Signs & Songs"}]},
    })
    FakeNet().route("api.aniskip.com", ANISKIP)
    m = monitor_mod.PlaybackMonitor(paths.profile_dir())
    m.presearched = presearched
    return m


def start(m, episode=3):
    xbmcgui.Window().setProperty(monitor_mod.HANDOFF_PROPERTY,
                                 json.dumps({"anilist_id": 154587, "episode": episode, "mal_id": 52991}))
    xbmc.Player.playing, xbmc.Player.total, xbmc.Player.time = True, LENGTH, 0.0
    m.onAVStarted()


def play_to(m, position, now):
    xbmc.Player.time = position
    m.tick(now)


def test_start_sets_english_audio_and_signs_subtitles(mon):
    start(mon)
    calls = dict(xbmc.jsonrpc_calls)
    assert calls["Player.SetAudioStream"] == {"playerid": 1, "stream": 1}
    assert calls["Player.SetSubtitle"] == {"playerid": 1, "subtitle": 1, "enable": True}
    assert monitor_mod.HANDOFF_PROPERTY not in xbmcgui.window_properties


def test_kodi_default_audio_setting_changes_nothing(mon):
    xbmcaddon.settings["audio_language"] = 2
    start(mon)
    assert not any(m.startswith("Player.Set") for m, _ in xbmc.jsonrpc_calls)


def test_playback_without_handoff_is_ignored(mon):
    xbmc.Player.playing, xbmc.Player.total = True, LENGTH
    mon.onAVStarted()
    assert mon.session is None
    mon.onPlayBackStopped()
    assert History(paths.profile_dir()).states(154587) == {}


def test_progress_saved_during_playback_and_on_stop(mon):
    start(mon)
    play_to(mon, 100, 0)
    play_to(mon, 600, 31)  # crash after this: history already has 600 s
    assert History(paths.profile_dir()).states(154587) == {3: (600, LENGTH, False)}
    play_to(mon, 700, 40)
    xbmc.Player.playing = False
    mon.onPlayBackStopped()
    assert History(paths.profile_dir()).states(154587) == {3: (700, LENGTH, False)}


def test_end_of_playback_marks_watched(mon):
    start(mon)
    play_to(mon, 1000, 0)
    mon.onPlayBackEnded()
    assert History(paths.profile_dir()).states(154587)[3][2] is True


def test_skip_button_seeks_past_opening(mon):
    start(mon)
    play_to(mon, 65, 0)
    dialog = xbmcgui.xml_dialogs[-1]
    assert dialog.xml_file == "novaflix-prompt.xml" and dialog.properties["button"] == "Skip intro"
    dialog.onClick(9000)
    assert xbmc.Player.seeks == [150.0] and dialog.closed


def test_mouse_movement_keeps_skip_button(mon):
    class Action:
        def __init__(self, action_id):
            self.action_id = action_id

        def getId(self):
            return self.action_id

    start(mon)
    play_to(mon, 65, 0)
    dialog = xbmcgui.xml_dialogs[-1]
    dialog.onAction(Action(107))  # ACTION_MOUSE_MOVE
    assert not dialog.closed
    dialog.onAction(Action(92))   # back
    assert dialog.closed


def test_file_without_english_audio_is_announced(mon):
    xbmc.jsonrpc_results["Player.GetProperties"] = {"audiostreams": [JPN], "currentaudiostream": JPN, "subtitles": []}
    start(mon)
    assert xbmcgui.notifications[-1][1] == "This file has no English audio track"
    assert not any(m == "Player.SetSubtitle" for m, _ in xbmc.jsonrpc_calls)  # Japanese audio: subs untouched


def test_skip_button_closes_itself(mon):
    start(mon)
    play_to(mon, 65, 0)
    play_to(mon, 70, monitor_mod.SKIP_SHOW_S + 1)
    assert xbmcgui.xml_dialogs[-1].closed and xbmc.Player.seeks == []


def test_up_next_presearches_and_opens_source_list_on_ok(mon):
    start(mon, episode=3)
    play_to(mon, 1321, 0)
    assert mon.presearched == [4]
    dialog = xbmcgui.xml_dialogs[-1]
    assert dialog.properties["text"] == "Next: Episode 4"
    assert not any("PlayMedia" in b for b in xbmc.builtins_executed)  # never auto-plays (DEC-004)
    dialog.onClick(9000)
    mon.onPlayBackStopped()
    mon.tick(1)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=154587&ep=4)"


def test_up_next_replaces_skip_ending(mon):
    start(mon, episode=3)
    play_to(mon, 1321, 0)
    assert [d.properties["button"] for d in xbmcgui.xml_dialogs] == ["Choose source"]


def test_no_up_next_after_last_episode_but_skip_ending_offered(mon):
    start(mon, episode=28)
    play_to(mon, 1321, 0)
    assert mon.presearched == [] and not any(d.properties.get("text") for d in xbmcgui.xml_dialogs)
    assert xbmcgui.xml_dialogs[-1].properties["button"] == "Skip ending"


def test_aniskip_failure_never_affects_playback(mon):
    FakeNet().route("api.aniskip.com", OSError("down"))
    start(mon)
    assert mon.session.skips == [] and mon.session.upnext_at == LENGTH - 90


def test_playback_error_offers_another_source(mon):
    start(mon)
    xbmcgui.yesno_answers.append(True)
    mon.onPlayBackError()
    assert "Choose another source" in xbmcgui.yesno_calls[-1][1]
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=154587&ep=3)"


def test_list_refreshes_after_stop_when_showing_novaflix(mon):
    xbmc.info_labels["Container.FolderPath"] = "plugin://plugin.video.novaflix/show?id=154587"
    start(mon)
    play_to(mon, 700, 0)
    mon.onPlayBackStopped()
    assert "Container.Refresh" in xbmc.builtins_executed


def start_with(m, resume_s, episode=3):
    xbmcgui.Window().setProperty(monitor_mod.HANDOFF_PROPERTY, json.dumps(
        {"anilist_id": 154587, "episode": episode, "mal_id": 52991, "resume_s": resume_s}))
    xbmc.Player.playing, xbmc.Player.total, xbmc.Player.time = True, LENGTH, 0.0
    m.onAVStarted()


def test_resume_position_is_sought_after_start(mon):
    start_with(mon, 754)
    assert xbmc.Player.seeks == [754]


def test_resume_too_close_to_the_end_starts_normally(mon):
    start_with(mon, int(LENGTH) - 10)
    assert xbmc.Player.seeks == []


def test_watched_episode_is_queued_for_mal_once(mon, monkeypatch):
    mal_login()
    queued = []
    monkeypatch.setattr(sync, "queue", lambda d, mal_id, kind, episode=0: queued.append((mal_id, kind, episode)) or True)
    start(mon)
    play_to(mon, 100, 0)
    play_to(mon, 600, 31)
    assert queued == []                       # not watched yet
    play_to(mon, LENGTH * 0.95, 62)           # save at >= 90 %
    play_to(mon, LENGTH * 0.97, 93)           # another save: no second change
    mon.onPlayBackEnded()
    assert queued == [(52991, "watched", 3)]


# -- Up next buttons: stop first, then one transition ------------------------------------------

NEXT_URL = "PlayMedia(plugin://plugin.video.novaflix/play?id=154587&ep=4)"


class Key:
    def __init__(self, action_id):
        self.action_id = action_id

    def getId(self):
        return self.action_id


def up_next(m):
    start(m, episode=3)
    play_to(m, 1321, 0)
    return xbmcgui.xml_dialogs[-1]


def test_up_next_has_end_episode_next_to_choose_source(mon):
    dialog = up_next(mon)
    assert (dialog.properties["button"], dialog.properties["button2"]) == ("Choose source", "End episode")
    dialog.onAction(Key(1))  # left: to End episode, the prompt stays
    assert not dialog.closed
    dialog.onAction(Key(92))
    assert dialog.closed


def test_skip_button_alone_still_closes_on_left(mon):
    start(mon)
    play_to(mon, 65, 0)
    dialog = xbmcgui.xml_dialogs[-1]
    dialog.onAction(Key(1))
    assert dialog.closed


def test_choose_source_stops_the_episode_before_the_source_list(mon):
    xbmc.Player.stop_closes = False  # Kodi closes the player a moment later
    dialog = up_next(mon)
    dialog.onClick(9000)
    assert xbmc.Player.stops == 1 and dialog.closed
    mon.tick(1)
    assert NEXT_URL not in xbmc.builtins_executed  # still playing: nothing started yet
    xbmc.Player.playing = False
    mon.onPlayBackStopped()
    assert History(paths.profile_dir()).states(154587)[3][2] is True
    mon.tick(2)
    assert xbmc.builtins_executed.count(NEXT_URL) == 1
    mon.tick(3)
    assert xbmc.builtins_executed.count(NEXT_URL) == 1


def test_choose_source_without_a_stop_event_still_saves_and_continues(mon):
    dialog = up_next(mon)
    dialog.onClick(9000)  # the player closes, but Kodi sends no onPlayBackStopped
    mon.tick(1)
    assert mon.session is None and History(paths.profile_dir()).states(154587)[3][2] is True
    assert xbmc.builtins_executed[-1] == NEXT_URL


def test_repeated_presses_run_one_transition(mon):
    dialog = up_next(mon)
    dialog.onClick(9000)
    dialog.onClick(9000)
    dialog.onClick(9001)
    session = monitor_mod.Session(154587, 3)
    mon._begin_transition("end", session)  # a second prompt's press while the first runs
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
    mon.tick(200)
    assert NEXT_URL not in xbmc.builtins_executed


def test_end_episode_returns_to_the_open_novaflix_window(mon):
    xbmcgui.Window(10000).setProperty(monitor_mod.GUI_PROPERTY, "true")
    dialog = up_next(mon)
    session = mon.session
    dialog.onClick(9001)
    assert xbmc.Player.stops == 1 and session.cancelled
    assert xbmcgui.Window(10000).getProperty(monitor_mod.OPEN_SHOW_PROPERTY) == "154587"
    mon.onPlayBackStopped()
    mon.tick(1)
    assert not any("PlayMedia" in b or "RunPlugin" in b for b in xbmc.builtins_executed)
    assert History(paths.profile_dir()).states(154587)[3][2] is True
    play_to(mon, 1330, 5)  # nothing tracked any more: no new prompt
    assert xbmcgui.xml_dialogs[-1] is dialog


@pytest.mark.parametrize("styled,command", [
    (True, "RunPlugin(plugin://plugin.video.novaflix/launch?show=154587)"),
    (False, "ActivateWindow(Videos,plugin://plugin.video.novaflix/show?id=154587,return)"),
])
def test_end_episode_opens_the_show_when_novaflix_is_not_open(mon, styled, command):
    xbmcaddon.settings["novaflix_look"] = styled
    dialog = up_next(mon)
    dialog.onClick(9001)
    mon.tick(1)
    assert xbmc.builtins_executed[-1] == command
    assert monitor_mod.OPEN_SHOW_PROPERTY not in xbmcgui.window_properties

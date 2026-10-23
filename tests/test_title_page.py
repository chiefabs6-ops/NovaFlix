# tests/test_title_page.py
"""Title page (Plan 4, Task 5): header, Play/Resume, My List, More like this, season picker, episodes."""

import copy

import pytest
import xbmc
import xbmcaddon
import xbmcgui

from helpers import FakeNet, fixture
from resources.lib.gui import ids, loader, title as title_view
from resources.lib.kodi import paths
from resources.lib.storage.mylist import MyList
from resources.lib.storage.watching import WatchHistory

TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"


def tmdb(tv=None):
    xbmcaddon.settings["tmdb_token"] = TOKEN
    return (FakeNet().route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
            .route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json"))
            .route("/3/tv/1396/season/", {"episodes": []})
            .route("/3/tv/1396", tv or fixture("tmdb/tv_1396.json"))
            .route("/3/movie/438631", fixture("tmdb/movie_438631.json")))


def open_page(media_type, tmdb_id):
    window = title_view.TitleWindow("novaflix-show.xml", "", "Default", "1080i")
    page = title_view.TitlePage(window, media_type, tmdb_id, loader.Loader(spawn=loader.inline))
    window.page = page
    window.onInit()
    return page


def episodes(p):
    return p.window.getControl(ids.SHOW_EPISODES).items


def choose_in_menu(choice):
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(choice), w.onClick(ids.MENU_LIST)))


def test_show_header_buttons_and_first_season():
    tmdb()
    p = open_page("tv", 1396)
    props = p.window.properties
    assert props["title"] == "Breaking Bad" and props["play_label"] == "Play S1 E1"
    assert props["season_label"] == "Season 1" and props["favourite_label"] == "Add to My List"
    assert props["has_related"] == "true" and props["related_label"] == "More like this" and props["dub"] == ""
    s1 = fixture("tmdb/tv_1396_season_1.json")["episodes"]
    assert [i.getLabel() for i in episodes(p)] == [f"{e['episode_number']}. {e['name']}" for e in s1]


def test_opening_season_follows_history_and_resume_label():
    tmdb()
    WatchHistory(paths.profile_dir()).save_position("tv", 1396, 2, 3, 500, 2800)
    p = open_page("tv", 1396)
    assert p.window.properties["season_label"] == "Season 2"
    assert p.window.properties["play_label"] == "Resume S2 E3 · 38:20 left"
    p.window.onClick(ids.SHOW_PLAY)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=2&e=3&resume=500)"


def test_season_choices_skip_missing_and_put_specials_last():
    tv = copy.deepcopy(fixture("tmdb/tv_1396.json"))
    tv["seasons"] = [s for s in tv["seasons"] if s["season_number"] in (0, 1, 3)]
    tmdb(tv)
    p = open_page("tv", 1396)
    shown = []
    xbmcgui.modal_scripts.append(lambda w: (shown.append([i.getLabel() for i in w.entries]),
                                            w.onAction(xbmcgui.Action(92))))
    p.window.onClick(ids.SHOW_SEASON)
    assert shown == [["Season 1", "Season 3", "Specials"]]


def test_season_switch_reloads_episodes():
    tmdb()
    p = open_page("tv", 1396)
    choose_in_menu(1)  # Season 2
    p.window.onClick(ids.SHOW_SEASON)
    s2 = fixture("tmdb/tv_1396_season_2.json")["episodes"]
    assert p.window.properties["season_label"] == "Season 2" and len(episodes(p)) == len(s2)
    assert p.window.properties["play_label"] == "Play S2 E1"


def test_episode_click_with_resume_point_asks_then_plays():
    tmdb()
    WatchHistory(paths.profile_dir()).save_position("tv", 1396, 1, 2, 300, 2800)
    p = open_page("tv", 1396)
    p.window.getControl(ids.SHOW_EPISODES).selectItem(1)
    choose_in_menu(0)  # Resume
    p.window.onClick(ids.SHOW_EPISODES)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=1&e=2&resume=300)"


def test_my_list_toggle():
    tmdb()
    p = open_page("tv", 1396)
    p.window.onClick(ids.SHOW_FAVOURITE)
    assert MyList(paths.profile_dir()).contains("tv", 1396)
    assert p.window.properties["favourite_label"] == "Remove from My List"
    p.window.onClick(ids.SHOW_FAVOURITE)
    assert not MyList(paths.profile_dir()).contains("tv", 1396)


def test_more_like_this_returns_to_the_app():
    tmdb()
    p = open_page("tv", 1396)
    p.window.onClick(ids.SHOW_RELATED)
    assert p.result == ("more", "tv", 1396) and p.window.closed


def test_movie_page():
    tmdb()
    p = open_page("movie", 438631)
    props = p.window.properties
    assert props["play_label"] == "Play Now" and props["season_label"] == ""
    assert [i.getLabel() for i in episodes(p)] == ["Dune"]
    p.window.onClick(ids.SHOW_PLAY)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=movie&id=438631)"


def test_non_english_title_says_so():
    tv = dict(fixture("tmdb/tv_1396.json"), original_language="ko")
    tmdb(tv)
    assert open_page("tv", 1396).window.properties["dub"] == "Not in English (Korean)"


def test_episode_long_press_marks_watched():
    tmdb()
    p = open_page("tv", 1396)
    choose_in_menu(0)
    p.window.setFocusId(ids.SHOW_EPISODES)
    p.window.onAction(xbmcgui.Action(117))
    assert WatchHistory(paths.profile_dir()).states("tv", 1396)[(1, 1)][2] is True
    assert episodes(p)[0].properties["watched"] == "true"


def test_end_episode_of_another_title_opens_that_page():
    from resources.lib.playback import monitor
    tmdb()
    p = open_page("tv", 1396)
    xbmcgui.Window(10000).setProperty(monitor.OPEN_SHOW_PROPERTY, "movie:438631")
    p.window.onInit()  # video closed
    assert p.result == ("title", "movie", 438631) and p.window.closed


# -- review fixes --------------------------------------------------------------------------------

def test_specials_episode_plays_with_season_zero():
    specials = {"episodes": [dict(fixture("tmdb/tv_1396_season_1.json")["episodes"][0], season_number=0,
                                  episode_number=1, air_date="2009-02-17")]}
    xbmcaddon.settings["tmdb_token"] = TOKEN
    (FakeNet().route("/3/tv/1396/season/0", specials).route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
     .route("/3/tv/1396", fixture("tmdb/tv_1396.json")))
    p = open_page("tv", 1396)
    choose_in_menu(5)  # Seasons 1-5, then Specials
    p.window.onClick(ids.SHOW_SEASON)
    assert p.window.properties["season_label"] == "Specials"
    p.window.onClick(ids.SHOW_EPISODES)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=0&e=1)"


def test_show_without_regular_seasons_opens():
    tv = dict(fixture("tmdb/tv_1396.json"), seasons=[])
    net = tmdb(tv)
    p = open_page("tv", 1396)
    assert not p.window.closed and p.window.properties["no_episodes"] and net.count("/season/") == 0


def test_show_with_only_specials_opens_on_specials():
    tv = dict(fixture("tmdb/tv_1396.json"))
    tv["seasons"] = [s for s in tv["seasons"] if s["season_number"] == 0]
    xbmcaddon.settings["tmdb_token"] = TOKEN
    FakeNet().route("/3/tv/1396/season/0", {"episodes": []}).route("/3/tv/1396", tv)
    assert open_page("tv", 1396).window.properties["season_label"] == "Specials"


def test_season_without_aired_episodes_has_no_play_label():
    tv = dict(fixture("tmdb/tv_1396.json"))
    xbmcaddon.settings["tmdb_token"] = TOKEN
    FakeNet().route("/3/tv/1396/season/", {"episodes": []}).route("/3/tv/1396", tv)
    p = open_page("tv", 1396)
    assert p.window.properties["play_label"] == "No episodes have aired yet"


# -- availability (availability plan, Task 4) ------------------------------------------------------------

def test_play_episode_status_line_checks_once_then_shows_the_result(monkeypatch):
    from resources.lib.sources import availability as av
    calls = []
    monkeypatch.setattr(av, "check", lambda m, i, s, e: calls.append((m, i, s, e)) or av.Availability(av.AVAILABLE))
    tmdb()
    p = open_page("tv", 1396)
    assert calls == [("tv", 1396, 1, 1)]
    assert (p.window.properties["avail"], p.window.properties["avail_line"]) == ("available", "S1 E1 · Available")
    assert episodes(p)[0].properties["avail"] == "available"
    p.refresh()
    assert calls == [("tv", 1396, 1, 1)]  # never checked twice


def test_unknown_reads_could_not_check(monkeypatch):
    from resources.lib.sources import availability as av
    monkeypatch.setattr(av, "check", lambda m, i, s, e: av.Availability(av.UNKNOWN))
    tmdb()
    p = open_page("tv", 1396)
    assert p.window.properties["avail_line"] == "S1 E1 · Could not check streams right now (try again later)"


def test_saved_results_put_dots_on_episodes(monkeypatch):
    from resources.lib.sources import availability as av
    monkeypatch.setattr(av, "cached_episodes", lambda m, i, s, numbers, directory=None:
                        {2: av.Availability(av.UNAVAILABLE), 1: av.Availability(av.AVAILABLE)})
    monkeypatch.setattr(av, "check", lambda *a: (_ for _ in ()).throw(AssertionError("searched")))
    tmdb()
    p = open_page("tv", 1396)
    assert [episodes(p)[i].properties["avail"] for i in range(3)] == ["available", "unavailable", ""]


def test_movie_status_line(monkeypatch):
    from resources.lib.sources import availability as av
    monkeypatch.setattr(av, "check", lambda m, i, s, e: av.Availability(av.NO_ENGLISH))
    tmdb()
    p = open_page("movie", 438631)
    assert (p.window.properties["avail"], p.window.properties["avail_line"]) == ("sub_only", "No English audio")


def test_title_page_sets_labelled_fields():
    tmdb()
    show = open_page("tv", 1396).window.properties
    assert show["kind"] == "TV series" and show["length_label"] == "Seasons" and show["length"].endswith("seasons")
    assert show["rating"].startswith("★ ") and show["year"] == "2008" and show["genres"]
    film = open_page("movie", 438631).window.properties
    assert film["kind"] == "Movie" and film["length_label"] == "Runtime" and film["length"].endswith(" min")

# tests/test_gui_app.py
"""App window (Plan 4): sidebar, views, stack, Back, actions, paging, long-press menu, More like this."""

import pytest
import xbmc
import xbmcaddon
import xbmcgui

from helpers import FakeNet, fixture
from resources.lib import errors, media
from resources.lib.gui import app as app_mod, ids, lists, loader
from resources.lib.gui.cards import Card
from resources.lib.kodi import paths
from resources.lib.storage.mylist import MyList
from resources.lib.storage.watching import WatchHistory

REAL_LOAD = lists.load
TOKEN = "eyJTESTTOKEN0000000000.eyJTESTPAYLOAD000000000.TESTSIGNATURE000000000"


def page(n, more=False, start=0):
    return lists.Page("Trending Now", [Card(label=f"S{i}", action=("title", "tv", i)) for i in range(start, start + n)],
                      more)


@pytest.fixture
def app(monkeypatch):
    calls = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))

    def fake_load(key, page_no=1):
        calls.append((key, page_no))
        return page(30, more=page_no < 2, start=(page_no - 1) * 30)
    monkeypatch.setattr(lists, "load", fake_load)
    window = app_mod.AppWindow("novaflix-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=loader.inline))
    window.app = a
    a.calls = calls
    window.onInit()
    return a


def sidebar_targets(a):
    return [i.properties["target"] for i in a.window.getControl(ids.SIDEBAR).items]


def select_sidebar(a, target):
    """Click the sidebar entry for `target`, opening Explore first when it sits inside it."""
    if target not in sidebar_targets(a):
        select_sidebar(a, "explore")
    a.window.getControl(ids.SIDEBAR).selectItem(sidebar_targets(a).index(target))
    a.window.onClick(ids.SIDEBAR)


def settings_menu(a, choice):
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(choice), w.onClick(ids.MENU_LIST)))
    a.window.onClick(ids.SIDEBAR_SETTINGS)


def long_press(a, choice):
    """Open the long-press menu on the focused grid card and pick option `choice` (labels returned)."""
    shown = []

    def script(w):
        shown.append([i.getLabel() for i in w.entries])
        w.getControl(ids.MENU_LIST).selectItem(choice)
        w.onClick(ids.MENU_LIST)
    xbmcgui.modal_scripts.append(script)
    a.window.setFocusId(ids.GRID)
    a.window.onAction(xbmcgui.Action(117))
    return shown[0] if shown else []


EXPLORE = ["trending", "popular_movies", "popular_tv", "top_movies", "top_tv", "airing_today", "genres"]


def test_sidebar_shows_main_entries_and_a_closed_explore(app):
    labels = [i.getLabel() for i in app.window.getControl(ids.SIDEBAR).items]
    assert labels == ["Home", "Search", "Continue Watching", "My List", "Explore"]
    assert [i.properties["kind"] for i in app.window.getControl(ids.SIDEBAR).items] == ["main"] * 4 + ["explore"]
    assert app.window.properties["explore_open"] == "" and app.window.properties["settings_label"] == "Settings"
    assert app.view == "home" and app.window.properties["view"] == "home"


def test_explore_opens_and_closes_in_place(app):
    select_sidebar(app, "explore")
    control = app.window.getControl(ids.SIDEBAR)
    assert [i.getLabel() for i in control.items][4:] == ["Explore", "Trending Now", "Popular movies", "Popular shows",
                                                         "Top rated movies", "Top rated shows", "Airing today", "Genres"]
    assert sidebar_targets(app)[5:] == EXPLORE
    assert app.window.properties["explore_open"] == "true" and control.getSelectedPosition() == 4
    select_sidebar(app, "explore")
    assert len(control.items) == 5 and app.window.properties["explore_open"] == ""


@pytest.mark.parametrize("target", EXPLORE)
def test_every_explore_entry_opens_its_grid(app, target):
    select_sidebar(app, target)
    assert app.view == "grid" and app.stack == [target] and app.window.properties["current"] == target
    assert app.window.properties["current_group"] == "explore"


@pytest.mark.parametrize("target", ["search", "continue", "mylist"])
def test_every_main_entry_opens_its_grid(app, target):
    select_sidebar(app, target)
    assert app.view == "grid" and app.stack == [target] and app.window.properties["current_group"] == ""


def test_sidebar_opens_grid_and_back_returns_home(app):
    select_sidebar(app, "trending")
    assert app.window.getControl(ids.GRID).size() == 30 and app.window.properties["grid_title"] == "Trending Now"
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home" and app.stack == []
    app.window.onAction(xbmcgui.Action(92))
    assert app.window.closed


def test_settings_menu_opens_addon_settings_and_my_torbox(app):
    settings_menu(app, 0)
    assert xbmcaddon.opened_settings and app.view == "home"
    settings_menu(app, 1)
    assert app.view == "grid" and app.stack == ["torbox"] and ("torbox", 1) in app.calls


def test_paging_loads_next_page_and_keeps_the_selected_card(app):
    select_sidebar(app, "trending")
    grid = app.window.getControl(ids.GRID)
    app.window.setFocusId(ids.GRID)
    grid.selectItem(28)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    assert grid.size() == 60 and grid.getSelectedPosition() == 28 and app.calls[-1] == ("trending", 2)


def test_next_page_drops_titles_already_listed(app, monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: page(30, more=page_no < 2, start=(page_no - 1) * 25))
    select_sidebar(app, "trending")
    app.window.setFocusId(ids.GRID)
    app.window.getControl(ids.GRID).selectItem(29)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    assert len(app.grid.cards) == 55


def test_page_from_before_a_reload_is_dropped(monkeypatch):
    jobs = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: page(30, more=True, start=(page_no - 1) * 30))
    window = app_mod.AppWindow("novaflix-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=jobs.append))
    window.app = a
    window.onInit()
    jobs.clear()
    a.open_grid("trending")
    jobs.pop(0)()
    window.setFocusId(ids.GRID)
    window.getControl(ids.GRID).selectItem(29)
    window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    late = jobs.pop(0)
    a.grid.load("trending")
    late()
    jobs.pop(0)()
    assert [i.getLabel() for i in window.getControl(ids.GRID).items] == [f"S{i}" for i in range(30)]


def related_page(*row_sizes):
    rows = [(f"Row {n}", [Card(label=f"R{n}-{i}", action=("title", "movie", 100 * n + i)) for i in range(size)])
            for n, size in enumerate(row_sizes)]
    return lists.RelatedPage("Dune", rows, "", "" if rows else "Nothing found")


def test_grid_card_opens_title_page_and_its_more_result_opens_more_like_this(app, monkeypatch):
    from resources.lib.gui import title as title_mod
    opened = []
    monkeypatch.setattr(title_mod, "open_title", lambda m, i: opened.append((m, i)) or ("more", m, i))
    monkeypatch.setattr(lists, "more_like_this", lambda m, i: related_page(2, 3))
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(3)
    app.window.onClick(ids.GRID)
    assert opened == [("tv", 3)] and app.stack == ["trending", "more:tv:3"] and app.view == "related"
    w = app.window
    assert w.properties["related_title"] == "Dune" and w.properties["rel1_title"] == "Row 1"
    assert w.getControl(ids.RELATED_ROWS[1]).size() == 3 and w.getFocusId() == ids.RELATED_ROWS[0]
    w.onAction(xbmcgui.Action(92))
    assert app.view == "grid" and app.stack == ["trending"]


def test_more_like_this_card_opens_title_page(app, monkeypatch):
    from resources.lib.gui import title as title_mod
    opened = []
    monkeypatch.setattr(title_mod, "open_title", lambda m, i: opened.append((m, i)))
    monkeypatch.setattr(lists, "more_like_this", lambda m, i: related_page(2, 3))
    app.run(("more", "movie", 438631))
    app.window.getControl(ids.RELATED_ROWS[1]).selectItem(2)
    app.window.onClick(ids.RELATED_ROWS[1])
    assert opened == [("movie", 102)]


def test_more_like_this_error_and_empty(app, monkeypatch):
    def boom(m, i):
        raise errors.NetworkError("down")
    monkeypatch.setattr(lists, "more_like_this", boom)
    app.run(("more", "tv", 3))
    assert app.window.properties["related_status"] == "Couldn't load"
    monkeypatch.setattr(lists, "more_like_this", lambda m, i: related_page())
    app.run(("more", "tv", 4))
    assert app.window.properties["related_status"] == "Nothing found"


def test_watch_and_search_actions(app):
    app.run(("watch", "tv", 1396, 2, 3, 754))
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=2&e=3&resume=754)"
    app.run(("watch", "movie", 438631, None, None, 0))
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=movie&id=438631)"
    xbmcgui.input_answers.append("severance")
    app.run(("search_new",))
    assert app.stack[-1] == "search:severance"


def test_grid_load_error_reports_and_goes_back(app, monkeypatch):
    def boom(key, page_no=1):
        raise errors.NetworkError("offline")
    monkeypatch.setattr(lists, "load", boom)
    select_sidebar(app, "trending")
    assert "internet" in xbmcgui.notifications[-1][1] and app.view == "home"


def test_missing_tmdb_key_asks_for_settings(app, monkeypatch):
    def missing(key, page_no=1):
        raise lists.TmdbKeyMissing()
    monkeypatch.setattr(lists, "load", missing)
    select_sidebar(app, "trending")
    assert "TMDB key" in xbmcgui.yesno_calls[-1][1] and xbmcaddon.opened_settings and app.view == "home"


def test_missing_service_offers_setup(app, monkeypatch):
    def missing(key, page_no=1):
        raise lists.ServiceMissing()
    monkeypatch.setattr(lists, "load", missing)
    xbmcgui.yesno_answers.append(False)
    settings_menu(app, 1)
    assert "TorBox API key" in xbmcgui.yesno_calls[-1][1] and app.view == "home"


def tmdb():
    xbmcaddon.settings["tmdb_token"] = TOKEN
    return (FakeNet().route("/3/tv/1396/season/1", fixture("tmdb/tv_1396_season_1.json"))
            .route("/3/tv/1396/season/2", fixture("tmdb/tv_1396_season_2.json"))
            .route("/3/tv/1396/season/", {"episodes": []})
            .route("/3/tv/1396", fixture("tmdb/tv_1396.json"))
            .route("/3/movie/438631", fixture("tmdb/movie_438631.json")))


def test_long_press_adds_to_my_list_and_removes_again(app, monkeypatch):
    tmdb()
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page(
        "x", [Card(label="Dune", action=("title", "movie", 438631))]))
    select_sidebar(app, "trending")
    labels = long_press(app, 0)
    assert labels == ["Add to My List", "Mark as watched", "Mark as unwatched", "More like this"]
    assert MyList(paths.profile_dir()).contains("movie", 438631)
    assert long_press(app, 0)[0] == "Remove from My List"
    assert not MyList(paths.profile_dir()).contains("movie", 438631)


def test_long_press_marks_a_movie_and_a_show_watched(app, monkeypatch):
    tmdb()
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page(
        "x", [Card(label="Dune", action=("title", "movie", 438631)),
              Card(label="BB", action=("watch", "tv", 1396, 2, 3, 0))]))
    select_sidebar(app, "continue")
    long_press(app, 1)
    assert WatchHistory(paths.profile_dir()).states("movie", 438631)[(0, 0)][2] is True
    app.window.getControl(ids.GRID).selectItem(1)
    long_press(app, 1)
    states = WatchHistory(paths.profile_dir()).states("tv", 1396)
    assert states[(1, 1)][2] and states[(2, 3)][2]
    xbmcgui.yesno_answers.append(True)
    app.window.getControl(ids.GRID).selectItem(1)
    long_press(app, 2)
    assert WatchHistory(paths.profile_dir()).states("tv", 1396) == {}


def test_long_press_more_like_this(app, monkeypatch):
    monkeypatch.setattr(lists, "more_like_this", lambda m, i: related_page(1))
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(4)
    long_press(app, 3)
    assert app.view == "related" and app.stack == ["trending", "more:tv:4"]


def test_end_episode_opens_the_title_page_when_the_video_closes(app, monkeypatch):
    from resources.lib.gui import title as title_mod
    from resources.lib.playback import monitor
    opened = []
    monkeypatch.setattr(title_mod, "open_title", lambda m, i: opened.append((m, i)))
    app.window.onInit()
    assert opened == []
    xbmcgui.Window(10000).setProperty(monitor.OPEN_SHOW_PROPERTY, "tv:1396")
    app.window.onInit()
    app.window.onInit()  # read once
    assert opened == [("tv", 1396)] and monitor.OPEN_SHOW_PROPERTY not in xbmcgui.window_properties


def test_app_started_for_a_title_opens_it_over_home(monkeypatch):
    from resources.lib.gui import title as title_mod
    from resources.lib.playback import monitor
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    opened, flags = [], []
    monkeypatch.setattr(title_mod, "open_title", lambda m, i: opened.append((m, i)))
    monkeypatch.setattr(app_mod, "Loader", lambda: loader.Loader(spawn=loader.inline))
    xbmcgui.modal_scripts.append(lambda w: flags.append(xbmcgui.Window(10000).getProperty(monitor.GUI_PROPERTY)))
    app_mod.run("movie:438631")
    assert opened == [("movie", 438631)] and flags == ["true"]
    assert monitor.GUI_PROPERTY not in xbmcgui.window_properties


def test_phone_search_opens_the_results_like_the_keyboard(app, monkeypatch):
    monkeypatch.setattr(app_mod.actions, "search_phone", lambda: "severance")
    app.run(("search_phone",))
    assert app.view == "grid" and app.grid.key == "search:severance"


def test_paired_phone_search_opens_results_unless_a_dialog_is_open(app, monkeypatch):
    sent = ["severance"]
    monkeypatch.setattr(app_mod.actions, "phone_search", lambda: sent.pop() if sent else None)
    with app.busy():
        app.tick()
    assert app.view == "home"
    app.tick()
    assert app.view == "grid" and app.grid.key == "search:severance"


def test_search_tab_offers_unpair_once_a_phone_is_paired(app, monkeypatch):
    from resources.lib.net import phone_keyboard
    monkeypatch.setattr(lists, "load", REAL_LOAD)
    app.open_grid("search")
    assert ("phone_unpair",) not in [c.action for c in app.grid.cards]
    phone_keyboard.start(paths.profile_dir(), "127.0.0.1", pair=True)
    phone_keyboard.stop()
    app.grid.load("search")
    assert ("phone_unpair",) in [c.action for c in app.grid.cards]


def test_back_while_loading_ignores_late_results(monkeypatch):
    pending = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, [Card(label="x", action=("title", "tv", 1))]))
    window = app_mod.AppWindow("novaflix-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=pending.append))
    window.app = a
    window.onInit()
    window.onAction(xbmcgui.Action(92))
    for job in pending:
        job()
    assert window.closed and all(window.getControl(c).size() == 0 for c in ids.HOME_ROWS)


def test_sidebar_choice_replaces_the_stack_and_reinit_focuses_the_grid(app):
    select_sidebar(app, "trending")
    select_sidebar(app, "popular_tv")
    assert app.stack == ["popular_tv"]
    app.window.setFocusId(None)
    app.window.onInit()
    assert app.window.focus_id == ids.GRID


def test_app_layout_does_not_force_focus_on_reinit():
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "plugin.video.novaflix", "resources", "skins",
                        "Default", "1080i")
    for name in ("novaflix-app.xml", "novaflix-show.xml"):
        assert 'always="true"' not in open(os.path.join(path, name), encoding="utf-8").read()


# -- review fixes --------------------------------------------------------------------------------

def test_mark_show_watched_runs_in_the_background(monkeypatch):
    tmdb()
    pending = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page(
        "x", [Card(label="BB", action=("title", "tv", 1396))]))
    window = app_mod.AppWindow("novaflix-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=pending.append))
    window.app = a
    window.onInit()
    a.open_grid("trending")
    pending.pop()()
    pending.clear()
    long_press(a, 1)  # Mark as watched
    assert WatchHistory(paths.profile_dir()).states("tv", 1396) == {}  # nothing done on the GUI thread
    for job in list(pending):
        job()
    assert WatchHistory(paths.profile_dir()).states("tv", 1396)[(2, 3)][2] is True


def test_missing_key_is_asked_once_across_grid_and_home(app, monkeypatch):
    def missing(key, page_no=1):
        raise lists.TmdbKeyMissing()
    monkeypatch.setattr(lists, "load", missing)
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []) if key.startswith("continue") else missing(key))
    xbmcgui.yesno_answers.append(False)
    select_sidebar(app, "trending")
    assert len(xbmcgui.yesno_calls) == 1 and app.view == "home"


def test_home_reloads_once_the_tmdb_key_is_added(app, monkeypatch):
    from resources.lib.kodi import ui
    reloads = []
    monkeypatch.setattr(app.home, "load", lambda: reloads.append(1))
    monkeypatch.setattr(ui, "open_settings", lambda: xbmcaddon.settings.update(tmdb_token=TOKEN))
    app.report(lists.TmdbKeyMissing())
    assert reloads == [1] and app.view == "home"



# -- availability (availability plan, Task 3) ------------------------------------------------------------

def test_grid_checks_availability_of_the_cards_around_the_selection(app, monkeypatch):
    from resources.lib.sources import availability as av
    calls = []
    monkeypatch.setattr(av, "check", lambda m, i, s, e: calls.append(i) or av.Availability(av.AVAILABLE))
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page("Continue Watching", [
        Card(label=f"T{i}", avail="checking", check=("tv", i, 1, 2), action=("watch", "tv", i, 1, 2, 0))
        for i in range(40)]))
    select_sidebar(app, "continue")
    assert calls == list(range(18))
    grid = app.window.getControl(ids.GRID)
    app.window.setFocusId(ids.GRID)
    grid.selectItem(24)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    assert calls == list(range(18)) + list(range(24, 40))  # from the selected card's row: 24-39


def test_search_action_searches_again(app):
    app.run(("search", "tv", 1396, 2, 3))
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=2&e=3&refresh=1)"


def test_filter_tile_changes_the_list_and_back_still_leaves_it(app, monkeypatch):
    from resources.lib.gui import actions
    asked = []
    monkeypatch.setattr(actions, "choose_filter", lambda name, encoded: asked.append((name, encoded))
                        or "popular_movies:sort=newest")
    select_sidebar(app, "popular_movies")
    app.run(("filter", "popular_movies", ""))
    assert asked == [("popular_movies", "")]
    assert app.stack == ["popular_movies:sort=newest"] and app.calls[-1] == ("popular_movies:sort=newest", 1)
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home" and app.stack == []


def test_filter_menu_picks_a_genre(monkeypatch):
    from resources.lib.gui import actions
    monkeypatch.setattr(actions.Library, "genres", lambda self, media_type: [(28, "Action"), (18, "Drama")])
    picks = iter([1, 2])  # "Genre: Any" row, then "Drama" (after "Any", "Action")
    shown = []

    def script(w):
        shown.append([i.getLabel() for i in w.entries])
        w.getControl(ids.MENU_LIST).selectItem(next(picks))
        w.onClick(ids.MENU_LIST)
    xbmcgui.modal_scripts.extend([script, script])
    assert actions.choose_filter("top_tv", "sort=newest") == "top_tv:sort=newest;genre=18"
    assert shown[0] == ["Sort: Newest first", "Genre: Any", "Year: Any", "Rating: Any", "Clear filters"]
    assert shown[1] == ["Any", "Action", "Drama"]


def test_filter_menu_back_changes_nothing(monkeypatch):
    from resources.lib.gui import actions
    monkeypatch.setattr(actions.Library, "genres", lambda self, media_type: [(28, "Action")])
    xbmcgui.modal_scripts.append(lambda w: w.onAction(xbmcgui.Action(92)))
    assert actions.choose_filter("popular_movies", "") is None


def test_back_from_the_open_menu_returns_to_the_view(app):
    app.window.setFocusId(ids.SIDEBAR)
    app.window.onAction(xbmcgui.Action(92))
    assert not app.window.closed and app.window.getFocusId() == ids.HERO_PLAY
    select_sidebar(app, "trending")
    app.window.setFocusId(ids.SIDEBAR_SETTINGS)
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "grid" and app.window.getFocusId() == ids.GRID


def test_empty_my_list_offers_trending(app, monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page("My List", [], False,
                                                                         "Nothing in My List yet."))
    select_sidebar(app, "mylist")
    w = app.window
    assert w.properties["grid_empty"] == "Nothing here yet"
    assert w.properties["grid_empty_hint"] == "Nothing in My List yet."
    assert w.properties["grid_empty_action"] == "Browse Trending Now" and w.getFocusId() == ids.GRID_EMPTY_ACTION
    opened = []
    monkeypatch.setattr(app, "open_grid", opened.append)
    w.onClick(ids.GRID_EMPTY_ACTION)
    assert opened == ["trending"]


def test_empty_search_results_offer_no_button(app, monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page("Results", [], False, "No results."))
    app.open_grid("search:zzz")
    assert app.window.properties["grid_empty_action"] == ""


def test_grid_peek_only_for_title_pages(app, monkeypatch):
    select_sidebar(app, "trending")
    assert app.window.properties["grid_peek"] == ""  # the fixture's cards carry no details
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page(
        "Trending", [Card(label="A", kind_label="Movie", action=("title", "movie", 1))]))
    app.open_grid("trending")
    assert app.window.properties["grid_peek"] == "true"


def _genre_page(key, page_no=1):
    media_type = "tv" if key == "genres:tv" else "movie"
    return lists.Page("Genres", [Card(label=f"{media_type} {i}", kind="genre",
                                      action=("grid", f"genre:{media_type}:{i}")) for i in range(3)])


def test_genre_tab_switches_without_growing_the_stack(app, monkeypatch):
    monkeypatch.setattr(lists, "load", _genre_page)
    monkeypatch.setattr(lists, "genre_pictures", lambda tiles: {0: "pic.jpg"})
    select_sidebar(app, "genres")
    w = app.window
    assert w.properties["grid_genre_tab"] == "movie" and len(app.stack) == 1
    assert w.getControl(ids.GRID).getListItem(0).art.get("fanart") == "pic.jpg"
    w.onClick(ids.GENRE_TAB_SHOWS)
    assert w.properties["grid_genre_tab"] == "tv" and app.stack == ["genres:tv"]
    assert w.getControl(ids.GRID).getListItem(0).getLabel() == "tv 0"
    w.onAction(xbmcgui.Action(92))
    assert app.view == "home"


def test_genre_tabs_hide_on_other_grids(app):
    select_sidebar(app, "trending")
    assert app.window.properties["grid_genre_tab"] == ""


def test_back_from_the_menu_leaves_a_view_with_nothing_to_focus(app, monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page("Results", [], False, "No results."))
    app.open_grid("search:zzz")
    app.window.setFocusId(ids.SIDEBAR)
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home"


def test_back_from_the_menu_on_an_empty_personal_list_goes_to_its_offer(app, monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page("My List", [], False, "Nothing yet."))
    select_sidebar(app, "mylist")
    app.window.setFocusId(ids.SIDEBAR)
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "grid" and app.window.getFocusId() == ids.GRID_EMPTY_ACTION


def test_search_page_gets_wide_tiles_and_a_backdrop(app, monkeypatch):
    monkeypatch.setattr(lists, "search_art", lambda: "trend.jpg")
    select_sidebar(app, "search")
    w = app.window
    assert w.properties["grid_tiles"] == "wide"
    assert xbmcgui.window_properties["novaflix.search_art"] == "trend.jpg"
    select_sidebar(app, "trending")
    assert w.properties["grid_tiles"] == ""

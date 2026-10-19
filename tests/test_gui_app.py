# tests/test_gui_app.py
"""M12: app window — sidebar, views, stack, Back, actions, paging, context menu."""

import pytest
import xbmc
import xbmcgui
from helpers import mal_login

from resources.lib import errors
from resources.lib.gui import app as app_mod, ids, lists, loader
from resources.lib.gui.cards import Card
from resources.lib.kodi import paths
from resources.lib.myanimelist import sync
from resources.lib.storage.favourites import Favourites


REAL_LOAD = lists.load


def page(n, more=False, start=0):
    return lists.Page("Trending Now", [Card(label=f"S{i}", action=("show", i)) for i in range(start, start + n)], more)


@pytest.fixture
def app(monkeypatch):
    calls = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    def fake_load(key, page_no=1):
        calls.append((key, page_no))
        return page(30, more=page_no < 2, start=(page_no - 1) * 30)
    monkeypatch.setattr(lists, "load", fake_load)
    window = app_mod.AppWindow("aniverse-app.xml", "", "Default", "1080i")
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


def test_sidebar_shows_main_entries_and_a_closed_explore(app):
    labels = [i.getLabel() for i in app.window.getControl(ids.SIDEBAR).items]
    assert labels == ["Home", "Search", "Continue Watching", "My Anime List", "Favourites", "Explore"]
    assert [i.properties["kind"] for i in app.window.getControl(ids.SIDEBAR).items] == ["main"] * 5 + ["explore"]
    assert app.window.getControl(ids.SIDEBAR).items[0].properties["icon"] == "av-icon-home.png"
    assert app.window.properties["explore_open"] == "" and app.window.properties["settings_label"] == "Settings"
    assert app.view == "home" and app.window.properties["view"] == "home"


def test_explore_opens_and_closes_in_place(app):
    select_sidebar(app, "explore")
    control = app.window.getControl(ids.SIDEBAR)
    assert [i.getLabel() for i in control.items][5:] == ["Explore", "Trending Now", "Most Popular", "Airing This Season",
                                                         "Upcoming", "Genres", "Recently Aired"]
    assert sidebar_targets(app)[6:] == ["trending", "popular", "airing", "upcoming", "genres", "recent"]
    assert app.window.properties["explore_open"] == "true" and control.getSelectedPosition() == 5
    assert app.view == "home"  # toggling Explore does not navigate
    select_sidebar(app, "explore")
    assert len(control.items) == 6 and app.window.properties["explore_open"] == ""
    assert control.getSelectedPosition() == 5


@pytest.mark.parametrize("target", ["trending", "popular", "airing", "upcoming", "genres", "recent"])
def test_every_explore_entry_opens_its_grid(app, target):
    select_sidebar(app, target)
    assert app.view == "grid" and app.stack == [target] and app.window.properties["current"] == target
    assert app.window.properties["current_group"] == "explore"
    active = [i.properties["target"] for i in app.window.getControl(ids.SIDEBAR).items if i.properties["active"]]
    assert active == [target]


@pytest.mark.parametrize("target", ["search", "continue", "favourites"])
def test_every_main_entry_opens_its_grid(app, target):
    select_sidebar(app, target)
    assert app.view == "grid" and app.stack == [target] and app.window.properties["current"] == target
    assert app.window.properties["current_group"] == ""


def test_torbox_is_not_in_the_sidebar(app):
    select_sidebar(app, "explore")
    assert "torbox" not in sidebar_targets(app) and "settings" not in sidebar_targets(app)


def test_sidebar_opens_grid_and_back_returns_home(app):
    select_sidebar(app, "trending")
    assert app.view == "grid" and app.stack == ["trending"] and app.window.properties["current"] == "trending"
    assert app.window.getControl(ids.GRID).size() == 30 and app.window.properties["grid_title"] == "Trending Now"
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home" and app.stack == []
    app.window.onAction(xbmcgui.Action(92))
    assert app.window.closed


def test_settings_menu_opens_addon_settings(app):
    import xbmcaddon
    settings_menu(app, 0)
    assert xbmcaddon.opened_settings and app.view == "home"


def test_settings_menu_opens_my_torbox(app):
    settings_menu(app, 1)
    assert app.view == "grid" and app.stack == ["torbox"] and ("torbox", 1) in app.calls
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home"


def test_settings_menu_cancel_does_nothing(app):
    import xbmcaddon
    xbmcgui.modal_scripts.append(lambda w: w.onAction(xbmcgui.Action(92)))
    app.window.onClick(ids.SIDEBAR_SETTINGS)
    assert not xbmcaddon.opened_settings and app.view == "home"


def test_paging_loads_next_page_near_the_end(app):
    select_sidebar(app, "trending")
    grid = app.window.getControl(ids.GRID)
    grid.selectItem(26)
    app.window.setFocusId(ids.GRID)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    assert grid.size() == 60 and app.calls[-1] == ("trending", 2)


def test_next_page_keeps_the_selected_card(app):
    select_sidebar(app, "trending")
    grid = app.window.getControl(ids.GRID)
    app.window.setFocusId(ids.GRID)
    grid.selectItem(28)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    assert grid.size() == 60 and grid.getSelectedPosition() == 28
    assert app.window.getFocusId() == ids.GRID
    assert [i.getLabel() for i in grid.items[28:32]] == ["S28", "S29", "S30", "S31"]


def test_next_page_drops_shows_already_listed(app, monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: page(30, more=page_no < 2, start=(page_no - 1) * 25))
    select_sidebar(app, "trending")
    grid = app.window.getControl(ids.GRID)
    app.window.setFocusId(ids.GRID)
    grid.selectItem(29)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    labels = [i.getLabel() for i in grid.items]
    assert labels == [f"S{i}" for i in range(55)] and len(app.grid.cards) == 55


def test_page_from_before_a_reload_is_dropped(monkeypatch):
    jobs = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: page(30, more=True, start=(page_no - 1) * 30))
    window = app_mod.AppWindow("aniverse-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=jobs.append))
    window.app = a
    window.onInit()
    jobs.clear()
    a.open_grid("trending")
    jobs.pop(0)()                         # page 1
    window.setFocusId(ids.GRID)
    window.getControl(ids.GRID).selectItem(29)
    window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))  # still loading: page 2 asked once
    assert len(jobs) == 1
    late = jobs.pop(0)
    a.grid.load("trending")               # reloaded meanwhile
    late()                                # old page 2 arrives: ignored
    jobs.pop(0)()
    assert [i.getLabel() for i in window.getControl(ids.GRID).items] == [f"S{i}" for i in range(30)]


def test_paging_stops_at_last_page(app):
    select_sidebar(app, "trending")
    grid = app.window.getControl(ids.GRID)
    app.window.setFocusId(ids.GRID)
    grid.selectItem(29)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))  # loads page 2 (last)
    grid.selectItem(59)
    app.window.onAction(xbmcgui.Action(ids.ACTION_MOVE_DOWN))
    assert grid.size() == 60 and app.calls[-1] == ("trending", 2)


def related_page(*row_sizes, notice=""):
    rows = [(f"Row {n}", [Card(label=f"R{n}-{i}", action=("show", 100 * n + i)) for i in range(size)])
            for n, size in enumerate(row_sizes)]
    return lists.RelatedPage("Show 3", rows, notice, "" if rows else "No related entries for this show")


def test_grid_card_opens_show_and_related_result_opens_related(app, monkeypatch):
    opened = []
    from resources.lib.gui import show
    monkeypatch.setattr(show, "open_show", lambda i: opened.append(i) or ("related", i))
    monkeypatch.setattr(lists, "related", lambda i: related_page(2, 3))
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(3)
    app.window.onClick(ids.GRID)
    assert opened == [3] and app.stack == ["trending", "related:3"] and app.view == "related"
    w = app.window
    assert w.properties["related_title"] == "Show 3" and w.properties["rel1_title"] == "Row 1"
    assert w.getControl(ids.RELATED_ROWS[0]).size() == 2 and w.getControl(ids.RELATED_ROWS[1]).size() == 3
    assert w.getControl(ids.RELATED_ROWS[2]).size() == 0 and w.properties["rel2_title"] == ""
    assert w.getFocusId() == ids.RELATED_ROWS[0]
    w.onAction(xbmcgui.Action(92))
    assert app.view == "grid" and app.stack == ["trending"]


def test_related_card_opens_show_and_back_goes_home(app, monkeypatch):
    opened = []
    from resources.lib.gui import show
    monkeypatch.setattr(show, "open_show", lambda i: opened.append(i))
    monkeypatch.setattr(lists, "related", lambda i: related_page(2, 3))
    app.run(("related", 3))
    app.window.getControl(ids.RELATED_ROWS[1]).selectItem(2)
    app.window.onClick(ids.RELATED_ROWS[1])
    assert opened == [102]
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home" and app.stack == []


def test_show_page_back_returns_to_related_with_focus(app, monkeypatch):
    from resources.lib.gui import show
    monkeypatch.setattr(lists, "related", lambda i: related_page(2))
    monkeypatch.setattr(show, "open_show", lambda i: None)
    app.run(("related", 3))
    app.window.onClick(ids.RELATED_ROWS[0])  # show page opens and closes again
    app.window.setFocusId(ids.SIDEBAR)
    app.window.onInit()  # Kodi re-inits the app window after the show page
    assert app.view == "related" and app.window.getFocusId() == ids.RELATED_ROWS[0]


def test_related_error_and_empty_and_notice(app, monkeypatch):
    def boom(i):
        raise errors.RateLimited("AniList 429", retry_after=60)
    monkeypatch.setattr(lists, "related", boom)
    app.run(("related", 3))
    assert app.view == "related" and app.window.properties["related_status"] == "Couldn't load"
    monkeypatch.setattr(lists, "related", lambda i: related_page())
    app.run(("related", 4))
    assert app.window.properties["related_status"] == "No related entries for this show"
    monkeypatch.setattr(lists, "related", lambda i: related_page(1, notice="Some related entries could not be loaded"))
    app.run(("related", 5))
    assert app.window.properties["related_notice"] == "Some related entries could not be loaded"
    assert app.window.properties["related_status"] == ""


def test_context_menu_related_opens_related_view(app, monkeypatch):
    from resources.lib.gui import dialogs
    monkeypatch.setattr(dialogs, "menu", lambda title, options: 3)
    monkeypatch.setattr(lists, "related", lambda i: related_page(1))
    monkeypatch.setattr(app_mod.App, "_mal_state", lambda self, i: None)
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(4)
    app.window.setFocusId(ids.GRID)
    app.window.onAction(xbmcgui.Action(117))
    assert app.view == "related" and app.stack == ["trending", "related:4"]


def test_play_and_search_actions(app, monkeypatch):
    app.run(("play", 7, 3, 754))
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.aniverse/play?id=7&ep=3&resume=754)"
    xbmcgui.input_answers.append("frieren")
    app.run(("search_new",))
    assert app.stack[-1] == "search:frieren"


def test_grid_load_error_reports_and_goes_back(app, monkeypatch):
    from resources.lib import errors
    def boom(key, page_no=1):
        raise errors.NetworkError("offline")
    monkeypatch.setattr(lists, "load", boom)
    select_sidebar(app, "trending")
    assert "internet" in xbmcgui.notifications[-1][1] and app.view == "home"


def test_missing_service_offers_setup(app, monkeypatch):
    def missing(key, page_no=1):
        raise lists.ServiceMissing()
    monkeypatch.setattr(lists, "load", missing)
    xbmcgui.yesno_answers.append(False)
    settings_menu(app, 1)  # My TorBox lives in the Settings menu now
    assert "TorBox API key" in xbmcgui.yesno_calls[-1][1] and app.view == "home"


def test_context_menu_adds_favourite(app, monkeypatch):
    from resources.lib.metadata import catalog
    from resources.lib.models import Show
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: Show(anilist_id=i, title=f"S{i}"))
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(4)
    app.window.setFocusId(ids.GRID)
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(0), w.onClick(ids.MENU_LIST)))
    app.window.onAction(xbmcgui.Action(117))
    favs = Favourites(paths.profile_dir())
    assert 4 in favs.ids()
    favs.close()


def test_back_while_loading_ignores_late_results(monkeypatch):
    pending = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, [Card(label="x", action=("show", 1))]))
    window = app_mod.AppWindow("aniverse-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=pending.append))
    window.app = a
    window.onInit()
    window.onAction(xbmcgui.Action(92))  # leave before any row arrives
    for job in pending:
        job()
    assert window.closed and all(window.getControl(c).size() == 0 for c in ids.HOME_ROWS)


# -- final review fixes --------------------------------------------------------------

@pytest.fixture
def deferred(monkeypatch):
    """App whose loads wait until the test releases them (like slow network)."""
    pending = []
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: page(30))
    window = app_mod.AppWindow("aniverse-app.xml", "", "Default", "1080i")
    a = app_mod.App(window, loader.Loader(spawn=pending.append))
    window.app = a
    window.onInit()
    pending.clear()
    a.pending = pending
    return a


def release(a):
    jobs, a.pending[:] = list(a.pending), []
    for job in jobs:
        job()


def test_results_of_a_left_grid_are_dropped(deferred):
    select_sidebar(deferred, "trending")              # Trending starts loading
    deferred.window.onAction(xbmcgui.Action(92))  # Back to Home before it arrives
    release(deferred)
    assert deferred.view == "home" and not deferred.window.closed
    assert deferred.window.focus_id != ids.GRID
    select_sidebar(deferred, "trending")
    release(deferred)
    assert deferred.window.getControl(ids.GRID).size() == 30  # not 60


def test_failed_load_of_a_left_grid_does_not_close_aniverse(deferred, monkeypatch):
    from resources.lib import errors
    def boom(key, page_no=1):
        raise errors.NetworkError("down")
    monkeypatch.setattr(lists, "load", boom)
    select_sidebar(deferred, "trending")
    deferred.window.onAction(xbmcgui.Action(92))
    release(deferred)
    assert not deferred.window.closed and deferred.view == "home"


def test_sidebar_choice_replaces_the_stack(app):
    select_sidebar(app, "trending")
    select_sidebar(app, "popular")
    assert app.stack == ["popular"]
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home"


def test_reinit_after_show_page_focuses_the_current_view(app):
    select_sidebar(app, "trending")
    app.window.setFocusId(None)
    app.window.onInit()  # Kodi re-inits the window when the show page or video closes
    assert app.window.focus_id == ids.GRID


def test_app_layout_does_not_force_focus_on_reinit():
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "plugin.video.aniverse", "resources", "skins",
                        "Default", "1080i")
    for name in ("aniverse-app.xml", "aniverse-show.xml"):
        assert 'always="true"' not in open(os.path.join(path, name), encoding="utf-8").read()


def test_context_menu_mark_show_watched_is_queued_for_mal(app, monkeypatch):
    from resources.lib.metadata import catalog
    from resources.lib.models import Episode, Show
    mal_login()
    from resources.lib.myanimelist import progress
    monkeypatch.setattr(progress, "show_entry", lambda mal_id, *a, **k: {"list_status": "watching", "watched": 1})
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: Show(anilist_id=i, title=f"S{i}", mal_id=500 + i))
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=s.anilist_id, number=n) for n in (1, 2)])
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(4)
    app.window.setFocusId(ids.GRID)
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(1), w.onClick(ids.MENU_LIST)))
    app.window.onAction(xbmcgui.Action(117))
    assert [(m, k, e) for m, k, e, _ in sync.pending(paths.profile_dir())] == [(504, "show_watched", 2)]


# -- My Anime List status cards ---------------------------------------------------------

@pytest.fixture
def mal_ready(monkeypatch):
    import xbmcaddon
    xbmcaddon.settings["mal_client_id"] = "cid"
    xbmcaddon.settings["mal_username"] = "owner"
    counts = {"watching": (12, False), "plan_to_watch": (34, False), "completed": (50, False),
              "on_hold": (4, False), "dropped": (2, False)}
    monkeypatch.setattr(lists, "mal_count", lambda status: counts[status])


def test_my_anime_list_shows_status_cards_with_counts_and_shares(app, mal_ready):
    select_sidebar(app, "mal")
    w = app.window
    assert app.view == "mal" and app.stack == ["mal"] and w.properties["current"] == "mal"
    assert w.focus_id == ids.MAL_CARDS[0] and w.properties["mal_user"] == "owner"
    assert w.properties["mal_watching_title"] == "Watching" and w.properties["mal_watching_text"] == "Currently watching"
    assert [w.properties[f"mal_{s}_count"] for s in ("watching", "plan_to_watch", "completed", "on_hold", "dropped")]         == ["12", "34", "50", "4", "2"]
    assert [w.getControl(b).getPercent() for b in ids.MAL_BARS] == [12, 33, 49, 4]


def test_my_anime_list_card_opens_status_grid_and_back_returns_to_cards(app, mal_ready):
    select_sidebar(app, "mal")
    app.window.onClick(ids.MAL_CARDS[2])
    assert app.view == "grid" and app.stack == ["mal", "mal:completed"] and ("mal:completed", 1) in app.calls
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "mal" and app.window.focus_id == ids.MAL_CARDS[0]
    app.window.onAction(xbmcgui.Action(92))
    assert app.view == "home"


def test_my_anime_list_counts_above_the_cap_show_a_plus(app, mal_ready, monkeypatch):
    monkeypatch.setattr(lists, "mal_count", lambda status: (1000, True))
    select_sidebar(app, "mal")
    assert app.window.properties["mal_dropped_count"] == "1000+"


def test_my_anime_list_without_setup_offers_settings_and_stays_home(app):
    xbmcgui.yesno_answers.append(False)
    select_sidebar(app, "mal")
    assert "Client ID" in xbmcgui.yesno_calls[-1][1] and app.view == "home"


def test_my_anime_list_error_is_reported_once_and_leaves(app, mal_ready, monkeypatch):
    from resources.lib.metadata import mal
    def private(status):
        raise mal.MalUserUnavailable("private")
    monkeypatch.setattr(lists, "mal_count", private)
    select_sidebar(app, "mal")
    assert app.view == "home"


def test_mal_count_pages_through_the_cached_list(monkeypatch):
    from resources.lib.views import mylists
    import xbmcaddon
    xbmcaddon.settings["mal_client_id"] = "cid"
    xbmcaddon.settings["mal_username"] = "owner"
    pages = {1: ([object()] * 100, True), 2: ([object()] * 30, False)}
    monkeypatch.setattr(mylists, "_mal_page", lambda c, u, status, page: pages[page])
    assert lists.mal_count("completed") == (130, False)
    monkeypatch.setattr(mylists, "_mal_page", lambda c, u, status, page: ([object()] * 100, True))
    assert lists.mal_count("completed") == (1000, True)


def test_grid_checks_availability_of_the_cards_around_the_selection(app, monkeypatch):
    from resources.lib.sources import availability as av
    checked = []
    monkeypatch.setattr(av, "check", lambda i, e: checked.append(i) or av.Availability(av.SUB_ONLY))
    many = [Card(label=f"S{i}", label2="", avail="checking", check=(i, 2), check_play=False, action=("show", i))
            for i in range(40)]
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page("Watching", many, False))
    select_sidebar(app, "trending")
    assert checked == list(range(18))                       # the first three rows
    grid = app.window.getControl(ids.GRID)
    assert grid.getListItem(0).getLabel2() == "Ep 2 · Sub only" and grid.getListItem(0).properties["avail"] == "sub_only"
    assert grid.getListItem(20).properties["avail"] == "checking"
    app.window.setFocusId(ids.GRID)
    grid.selectItem(20)
    app.window.onAction(xbmcgui.Action(4))
    assert checked == list(range(36))                       # rows from the selected one on
    assert many[0].action == ("show", 0)                    # MyAnimeList cards still open the show


# -- MyAnimeList add / remove from the long-press menu ------------------------------------------

@pytest.fixture
def mal_menu(app, monkeypatch):
    """Grid of shows, logged in to MAL; `mal_menu.entry` is the show's MAL entry; records API calls."""
    from resources.lib.metadata import catalog
    from resources.lib.models import Show
    from resources.lib.myanimelist import progress
    from resources.lib.myanimelist.api import MalApi
    mal_login()
    state = {"entry": {"list_status": None, "watched": 0}, "calls": []}
    monkeypatch.setattr(progress, "show_entry", lambda mal_id, *a, **k: state["entry"])
    monkeypatch.setattr(catalog.Catalog, "show",
                        lambda self, i: Show(anilist_id=i, title=f"S{i}", mal_id=500 + i, episodes_total=12))
    monkeypatch.setattr(MalApi, "update", lambda self, m, status, watched: state["calls"].append(("put", m, status, watched)))
    monkeypatch.setattr(MalApi, "remove", lambda self, m: state["calls"].append(("delete", m)))
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(4)
    app.window.setFocusId(ids.GRID)
    return state


def pick(*labels):
    """Answer the next menus by label; records the options shown."""
    shown = []
    def script(label):
        def run(w):
            options = [i.getLabel() for i in w.entries]
            shown.append(options)
            w.getControl(ids.MENU_LIST).selectItem(options.index(label))
            w.onClick(ids.MENU_LIST)
        return run
    xbmcgui.modal_scripts.extend(script(label) for label in labels)
    return shown


def test_long_press_adds_a_show_to_myanimelist_with_the_chosen_status(app, mal_menu):
    from resources.lib.storage.cache import Cache
    cache = Cache(paths.profile_dir())
    cache.set("mal:@me:plan_to_watch:1", {"entries": [], "more": False}, 600)
    cache.close()
    shown = pick("Add to MyAnimeList", "Plan to Watch")
    app.window.onAction(xbmcgui.Action(117))
    assert "Add to MyAnimeList" in shown[0] and "Remove from MyAnimeList" not in shown[0]
    assert shown[1][0] == "Plan to Watch"
    assert mal_menu["calls"] == [("put", 504, "plan_to_watch", 0)]
    assert xbmcgui.notifications[-1][1] == "Added to MyAnimeList: Plan to Watch"
    cache = Cache(paths.profile_dir())
    assert cache.get("mal:@me:plan_to_watch:1") is None  # lists and counts show the change
    cache.close()


def test_adding_as_completed_counts_every_episode_and_watching_keeps_aniverse_progress(app, mal_menu):
    from resources.lib.storage.history import History
    pick("Add to MyAnimeList", "Completed")
    app.window.onAction(xbmcgui.Action(117))
    assert mal_menu["calls"][-1] == ("put", 504, "completed", 12)
    History(paths.profile_dir()).mark_show(4, [1, 2, 3], True)
    pick("Add to MyAnimeList", "Watching")
    app.window.onAction(xbmcgui.Action(117))
    assert mal_menu["calls"][-1] == ("put", 504, "watching", 3)


def test_long_press_removes_a_listed_show_after_confirming(app, mal_menu):
    mal_menu["entry"] = {"list_status": "watching", "watched": 3}
    sync.queue(paths.profile_dir(), 504, "episode_watched", 4)  # would put it back on the list
    shown = pick("Remove from MyAnimeList")
    xbmcgui.yesno_answers.append(True)
    app.window.onAction(xbmcgui.Action(117))
    assert "Remove from MyAnimeList" in shown[0] and "Add to MyAnimeList" not in shown[0]
    assert mal_menu["calls"] == [("delete", 504)] and sync.pending(paths.profile_dir()) == []
    assert xbmcgui.notifications[-1][1] == "Removed from MyAnimeList"


def test_remove_cancelled_changes_nothing(app, mal_menu):
    mal_menu["entry"] = {"list_status": "watching", "watched": 3}
    pick("Remove from MyAnimeList")
    xbmcgui.yesno_answers.append(False)
    app.window.onAction(xbmcgui.Action(117))
    assert mal_menu["calls"] == []


def test_myanimelist_failure_is_reported_not_raised(app, mal_menu, monkeypatch):
    from resources.lib.myanimelist.api import MalApi
    def down(self, m, status, watched):
        raise errors.NetworkError("down")
    monkeypatch.setattr(MalApi, "update", down)
    pick("Add to MyAnimeList", "Watching")
    app.window.onAction(xbmcgui.Action(117))
    assert xbmcgui.notifications[-1][1] == "MyAnimeList could not be updated. Try again later."


def test_not_logged_in_add_explains_the_login(app, monkeypatch):
    from resources.lib.metadata import catalog
    from resources.lib.models import Show
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: Show(anilist_id=i, title=f"S{i}", mal_id=500 + i))
    select_sidebar(app, "trending")
    app.window.getControl(ids.GRID).selectItem(4)
    app.window.setFocusId(ids.GRID)
    pick("Add to MyAnimeList")
    xbmcgui.yesno_answers.append(False)
    app.window.onAction(xbmcgui.Action(117))
    assert "Log in to MyAnimeList first" in xbmcgui.yesno_calls[-1][1]


def test_unreachable_myanimelist_hides_the_option(app, mal_menu):
    mal_menu["entry"] = None
    shown = []
    xbmcgui.modal_scripts.append(lambda w: (shown.append([i.getLabel() for i in w.entries]), w.onAction(xbmcgui.Action(92))))
    app.window.onAction(xbmcgui.Action(117))
    assert not any("MyAnimeList" in o for o in shown[0])


def test_continue_watching_cards_have_the_long_press_menu_too(app, monkeypatch):
    monkeypatch.setattr(app_mod.App, "_mal_state", lambda self, i: None)
    monkeypatch.setattr(lists, "load", lambda key, page_no=1: lists.Page(
        "Continue Watching", [Card(label="S7", action=("play", 7, 3, 0))]))
    select_sidebar(app, "continue")
    app.window.setFocusId(ids.GRID)
    shown = []
    xbmcgui.modal_scripts.append(lambda w: (shown.append([i.getLabel() for i in w.entries]), w.onAction(xbmcgui.Action(92))))
    app.window.onAction(xbmcgui.Action(117))
    assert shown and "Related & sequels" in shown[0]


# -- End episode (playback/monitor.py): back to the show page --------------------------------

def test_end_episode_opens_the_show_page_when_the_video_closes(app, monkeypatch):
    from resources.lib.gui import show as show_mod
    from resources.lib.playback import monitor
    opened = []
    monkeypatch.setattr(show_mod, "open_show", lambda anilist_id: opened.append(anilist_id))
    app.window.onInit()  # video closed, nothing asked
    assert opened == []
    xbmcgui.Window(10000).setProperty(monitor.OPEN_SHOW_PROPERTY, "154587")
    app.window.onInit()
    app.window.onInit()  # read once
    assert opened == [154587] and monitor.OPEN_SHOW_PROPERTY not in xbmcgui.window_properties


def test_app_started_for_a_show_opens_it_over_home(monkeypatch):
    from resources.lib.gui import show as show_mod
    from resources.lib.playback import monitor
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page(key, []))
    opened, flags = [], []
    monkeypatch.setattr(show_mod, "open_show", lambda anilist_id: opened.append(anilist_id))
    monkeypatch.setattr(app_mod, "Loader", lambda: loader.Loader(spawn=loader.inline))
    xbmcgui.modal_scripts.append(lambda w: flags.append(xbmcgui.Window(10000).getProperty(monitor.GUI_PROPERTY)))
    app_mod.run(154587)
    assert opened == [154587] and flags == ["true"]
    assert monitor.GUI_PROPERTY not in xbmcgui.window_properties  # cleared when AniVerse closes


def test_phone_search_opens_the_results_like_the_keyboard(app, monkeypatch):
    monkeypatch.setattr(app_mod.actions, "search_phone", lambda: "frieren")
    app.run(("search_phone",))
    assert app.view == "grid" and app.grid.key == "search:frieren"
    monkeypatch.setattr(app_mod.actions, "search_phone", lambda: None)  # cancelled on the TV
    app.run(("search_phone",))
    assert app.grid.key == "search:frieren" and app.stack == ["search:frieren"]


def test_paired_phone_search_opens_results_unless_a_dialog_is_open(app, monkeypatch):
    sent = ["frieren"]
    monkeypatch.setattr(app_mod.actions, "phone_search", lambda: sent.pop() if sent else None)
    with app.busy():  # e.g. the long-press menu is open: the search waits
        app.tick()
    assert app.view == "home"
    app.tick()
    assert app.view == "grid" and app.grid.key == "search:frieren"


def test_search_tab_offers_unpair_once_a_phone_is_paired(app, monkeypatch):
    from resources.lib.net import phone_keyboard
    monkeypatch.setattr(lists, "load", REAL_LOAD)  # the real Search tab tiles
    app.open_grid("search")
    actions_seen = [c.action for c in app.grid.cards]
    assert ("phone_unpair",) not in actions_seen
    phone_keyboard.start(paths.profile_dir(), "127.0.0.1", pair=True)
    phone_keyboard.stop()
    app.grid.load("search")
    assert ("phone_unpair",) in [c.action for c in app.grid.cards]
    monkeypatch.setattr(app_mod.actions, "unpair_phone", lambda: phone_keyboard.unpair(paths.profile_dir()) or True)
    app.run(("phone_unpair",))
    assert ("phone_unpair",) not in [c.action for c in app.grid.cards]

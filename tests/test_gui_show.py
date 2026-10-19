# tests/test_gui_show.py
"""M12: show page fills from the catalog and keeps the existing behaviour of its actions."""

import pytest
import xbmc
import xbmcgui
from helpers import FakeNet, mal_login

from resources.lib.gui import ids, loader, show as show_view
from resources.lib.kodi import paths
from resources.lib.metadata import catalog
from resources.lib.models import Episode, Show, ShowRef
from resources.lib.myanimelist import sync
from resources.lib.sources import availability as av
from resources.lib.storage.favourites import Favourites
from resources.lib.storage.history import History

SHOW = Show(anilist_id=7, title="Frieren", title_romaji="Sousou no Frieren", mal_id=52991, format="TV",
            status="FINISHED", episodes_total=3, year=2023, genres=["Adventure", "Drama"], description="Elf.",
            poster="https://x/cover/large/7.jpg", banner="b.jpg",
            relations=[ShowRef(anilist_id=8, relation="SEQUEL", format="TV", title="Frieren 2")])


@pytest.fixture
def page(monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: SHOW)
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=7, number=n, title=f"Ep {n}") for n in (1, 2, 3)])
    monkeypatch.setattr(catalog.Catalog, "fanart", lambda self, s: None)
    monkeypatch.setattr(catalog.Catalog, "dub_estimates", lambda self, s, n: {})
    monkeypatch.setattr(catalog.Catalog, "dub_status", lambda self, s: "dubbed")
    monkeypatch.setattr(av, "check", lambda i, n: av.Availability(av.AVAILABLE))
    window = show_view.ShowWindow("novaflix-show.xml", "", "Default", "1080i")
    p = show_view.ShowPage(window, 7, loader.Loader(spawn=loader.inline))
    window.page = p
    return p


def episodes(p):
    return p.window.getControl(ids.SHOW_EPISODES).items


def test_fills_header_buttons_and_episodes(page):
    page.window.onInit()
    props = page.window.properties
    assert (props["title"], props["alt"], props["genres"]) == ("Frieren", "Sousou no Frieren", "Adventure · Drama")
    assert props["play_label"] == "Play Ep 1" and props["favourite_label"] == "Favourite"
    assert props["dub"] == "DUB" and props["has_related"] == "true"
    assert [i.getLabel() for i in episodes(page)] == ["1. Ep 1", "2. Ep 2", "3. Ep 3"]


def test_resume_button_and_play(page):
    History(paths.profile_dir()).save_position(7, 2, 52991, 500, 1440)
    page.window.onInit()
    assert page.window.properties["play_label"] == "Resume Ep 2 · 8:20"
    page.window.onClick(ids.SHOW_PLAY)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=7&ep=2&resume=500)"


def test_favourite_toggle(page):
    page.window.onInit()
    page.window.onClick(ids.SHOW_FAVOURITE)
    favs = Favourites(paths.profile_dir())
    assert 7 in favs.ids()
    favs.close()
    assert page.window.properties["favourite_label"] == "Favourited"
    page.window.onClick(ids.SHOW_FAVOURITE)
    assert page.window.properties["favourite_label"] == "Favourite"


def test_related_returns_to_the_app(page):
    page.window.onInit()
    page.window.onClick(ids.SHOW_RELATED)
    assert page.result == ("related", 7) and page.window.closed


def test_episode_select_plays_and_menu_marks(page):
    page.window.onInit()
    page.window.getControl(ids.SHOW_EPISODES).selectItem(2)
    page.window.onClick(ids.SHOW_EPISODES)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=7&ep=3)"
    page.window.setFocusId(ids.SHOW_EPISODES)
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(0), w.onClick(ids.MENU_LIST)))
    page.window.onAction(xbmcgui.Action(117))
    assert History(paths.profile_dir()).states(7)[3][2] is True
    assert episodes(page)[2].properties["watched"] == "true"


def test_refresh_after_playback(page):
    page.window.onInit()
    xbmc.cond_visibility["Player.HasVideo"] = True
    page.tick()
    History(paths.profile_dir()).save_position(7, 1, 52991, 1400, 1440)
    xbmc.cond_visibility["Player.HasVideo"] = False
    page.tick()
    assert episodes(page)[0].properties["watched"] == "true"


def test_load_failure_reports_and_closes(page, monkeypatch):
    from resources.lib import errors
    def boom(self, i):
        raise errors.NetworkError("offline")
    monkeypatch.setattr(catalog.Catalog, "show", boom)
    page.window.onInit()
    assert "internet" in xbmcgui.notifications[-1][1] and page.window.closed


def test_back_closes(page):
    page.window.onInit()
    page.window.onAction(xbmcgui.Action(92))
    assert page.window.closed and page.result is None


def test_leaving_the_show_page_drops_its_late_results(monkeypatch):
    pending = []
    from resources.lib import errors
    def boom(self, i):
        raise errors.NetworkError("offline")
    monkeypatch.setattr(catalog.Catalog, "show", boom)
    monkeypatch.setattr(show_view, "Loader", lambda: loader.Loader(spawn=pending.append))
    xbmcgui.modal_scripts.append(lambda w: w.onAction(xbmcgui.Action(92)))  # Back at once
    assert show_view.open_show(7, start_ticker=False) is None
    for job in pending:
        job()
    assert xbmcgui.notifications == []


def test_episode_mark_is_queued_for_mal(page):
    mal_login()
    FakeNet().route("anime/52991?", {"id": 52991, "title": "Sousou no Frieren", "num_episodes": 3,
                                      "status": "finished_airing"})  # not on the list yet
    page.window.onInit()
    page.window.getControl(ids.SHOW_EPISODES).selectItem(1)
    page.window.setFocusId(ids.SHOW_EPISODES)
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(0), w.onClick(ids.MENU_LIST)))
    page.window.onAction(xbmcgui.Action(117))
    assert [(m, k, e) for m, k, e, _ in sync.pending(paths.profile_dir())] == [(52991, "watched", 2)]


FRIEREN_ON_MAL = {"id": 52991, "title": "Sousou no Frieren", "num_episodes": 3, "status": "finished_airing",
                  "my_list_status": {"status": "watching", "num_episodes_watched": 2, "score": 0}}


def test_mal_progress_ticks_episodes_and_moves_the_play_button(page):
    mal_login()
    FakeNet().route("anime/52991?", FRIEREN_ON_MAL)
    page.window.onInit()
    assert page.window.properties["play_label"] == "Play Ep 3"
    assert page.window.properties["mal"] == "MAL: Watching · 2/3"
    assert [c.watched for c in page.cards] == [True, True, False]


def test_unmark_lowers_mal_progress_at_once(page):
    mal_login()
    FakeNet().route("anime/52991?", FRIEREN_ON_MAL)
    page.window.onInit()
    page.window.getControl(ids.SHOW_EPISODES).selectItem(1)
    page.window.setFocusId(ids.SHOW_EPISODES)
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(0), w.onClick(ids.MENU_LIST)))
    page.window.onAction(xbmcgui.Action(117))  # ep 2: Mark as unwatched
    assert [c.watched for c in page.cards] == [True, False, False]
    assert page.window.properties["mal"] == "MAL: Watching · 1/3"
    assert page.window.properties["play_label"] == "Play Ep 2"


def test_show_page_fills_before_mal_answers(monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: SHOW)
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=7, number=n, title=f"Ep {n}") for n in (1, 2, 3)])
    monkeypatch.setattr(catalog.Catalog, "fanart", lambda self, s: None)
    monkeypatch.setattr(catalog.Catalog, "dub_estimates", lambda self, s, n: {})
    monkeypatch.setattr(catalog.Catalog, "dub_status", lambda self, s: "dubbed")
    monkeypatch.setattr(av, "check", lambda i, n: av.Availability(av.AVAILABLE))
    mal_login()
    FakeNet().route("anime/52991?", FRIEREN_ON_MAL)
    jobs = []
    window = show_view.ShowWindow("novaflix-show.xml", "", "Default", "1080i")
    p = show_view.ShowPage(window, 7, loader.Loader(spawn=jobs.append))
    window.page = p
    window.onInit()
    jobs.pop(0)()                       # the show and its episodes arrive
    assert len(episodes(p)) == 3 and window.properties["mal"] == ""
    assert window.properties["play_label"] == "Play Ep 1"
    jobs.pop(-1)()                      # MyAnimeList answers later (after the availability check started)
    assert window.properties["mal"] == "MAL: Watching · 2/3"
    assert window.properties["play_label"] == "Play Ep 3"


# -- availability of the Play episode ------------------------------------------------------------

def deferred_page(monkeypatch, check):
    """Show page whose jobs wait in a list, so the checking state can be seen."""
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: SHOW)
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=7, number=n, title=f"Ep {n}") for n in (1, 2, 3)])
    monkeypatch.setattr(catalog.Catalog, "fanart", lambda self, s: None)
    monkeypatch.setattr(catalog.Catalog, "dub_estimates", lambda self, s, n: {})
    monkeypatch.setattr(catalog.Catalog, "dub_status", lambda self, s: "dubbed")
    monkeypatch.setattr(av, "check", check)
    jobs = []
    window = show_view.ShowWindow("novaflix-show.xml", "", "Default", "1080i")
    p = show_view.ShowPage(window, 7, loader.Loader(spawn=jobs.append))
    window.page = p
    window.onInit()
    jobs.pop(0)()  # the show and its episodes arrive
    jobs.pop()     # MyAnimeList progress: not under test here
    return p, jobs


@pytest.mark.parametrize("state,line", [
    (av.AVAILABLE, "Ep 1 · Available"),
    (av.SUB_ONLY, "Ep 1 · Sub only"),
    (av.UNAVAILABLE, "Ep 1 · No streams currently available"),
    (av.UNKNOWN, "Ep 1 · Could not check streams right now (try again later)"),
    (av.UPCOMING, "Ep 1 · Not aired yet"),
])
def test_play_episode_shows_checking_then_its_availability(monkeypatch, state, line):
    calls = []
    p, jobs = deferred_page(monkeypatch, lambda i, n: calls.append((i, n)) or av.Availability(state))
    props = p.window.properties
    assert (props["avail"], props["avail_line"]) == ("checking", "Ep 1 · Checking...")
    jobs.pop(0)()
    assert (props["avail"], props["avail_line"]) == (state, line)
    assert calls == [(7, 1)] and jobs == []  # refresh after the result does not check again
    assert episodes(p)[0].properties["avail"] == state


def test_failed_check_is_never_shown_as_no_streams(monkeypatch):
    def boom(i, n):
        raise RuntimeError("provider exploded")
    p, jobs = deferred_page(monkeypatch, boom)
    jobs.pop(0)()
    assert p.window.properties["avail"] == av.UNKNOWN
    assert "No streams" not in p.window.properties["avail_line"]


def test_saved_results_need_no_search_and_mark_the_episodes(monkeypatch):
    monkeypatch.setattr(av, "cached_episodes", lambda i, numbers: {1: av.Availability(av.UNAVAILABLE),
                                                                    3: av.Availability(av.AVAILABLE)})
    p, jobs = deferred_page(monkeypatch, lambda i, n: pytest.fail("searched"))
    assert jobs == []
    assert p.window.properties["avail_line"] == "Ep 1 · No streams currently available"
    assert [i.properties["avail"] for i in episodes(p)] == ["unavailable", "", "available"]
    p.window.onClick(ids.SHOW_PLAY)  # Play still opens the source list (it searches again)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=7&ep=1)"


def test_next_episode_after_playback_is_checked(monkeypatch):
    calls = []
    p, jobs = deferred_page(monkeypatch, lambda i, n: calls.append(n) or av.Availability(av.AVAILABLE))
    jobs.pop(0)()
    History(paths.profile_dir()).mark(7, 1, True)
    xbmc.cond_visibility["Player.HasVideo"] = True
    p.tick()
    xbmc.cond_visibility["Player.HasVideo"] = False
    p.tick()
    while jobs:
        jobs.pop(0)()
    assert calls == [1, 2] and p.window.properties["avail_line"] == "Ep 2 · Available"


# -- End episode (playback/monitor.py) ----------------------------------------------------------

def test_end_episode_stays_on_this_show_page(page):
    from resources.lib.playback import monitor
    page.window.onInit()
    xbmcgui.Window(10000).setProperty(monitor.OPEN_SHOW_PROPERTY, "7")
    page.window.onInit()  # the video closed
    assert not page.window.closed and page.result is None
    assert monitor.OPEN_SHOW_PROPERTY not in xbmcgui.window_properties


def test_end_episode_of_another_show_switches_to_its_page(page):
    from resources.lib.playback import monitor
    page.window.onInit()
    xbmcgui.Window(10000).setProperty(monitor.OPEN_SHOW_PROPERTY, "8")
    page.window.onInit()
    assert page.window.closed and page.result == ("show", 8)


# -- MyAnimeList button: same add / remove as the long-press menu (actions.mal_edit) --------------

NOT_ON_MAL = {"id": 52991, "title": "Sousou no Frieren", "num_episodes": 3, "status": "finished_airing"}


def pick_menu(choice):
    xbmcgui.modal_scripts.append(lambda w: (w.getControl(ids.MENU_LIST).selectItem(choice), w.onClick(ids.MENU_LIST)))


def test_mal_button_hidden_without_mal_id(page, monkeypatch):
    import dataclasses
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: dataclasses.replace(SHOW, mal_id=None))
    page.window.onInit()
    assert page.window.properties["mal_label"] == ""


def test_mal_button_logged_out_explains_the_login(page):
    page.window.onInit()
    assert page.window.properties["mal_label"] == "Add to MyAnimeList"
    xbmcgui.yesno_answers.append(False)
    page.window.onClick(ids.SHOW_MAL)
    assert "Log in to MyAnimeList first" in xbmcgui.yesno_calls[-1][1]


def test_mal_button_adds_the_show(page, monkeypatch):
    from resources.lib.myanimelist import listedit
    mal_login()
    FakeNet().route("anime/52991?", NOT_ON_MAL)
    added = []
    monkeypatch.setattr(listedit, "add", lambda d, mal_id, anilist_id, status, total=0: added.append(
        (mal_id, anilist_id, status)) or 0)
    page.window.onInit()
    assert page.window.properties["mal_label"] == "Add to MyAnimeList"
    pick_menu(0)  # Plan to Watch
    page.window.onClick(ids.SHOW_MAL)
    assert added == [(52991, 7, "plan_to_watch")]
    assert xbmcgui.notifications[-1][1] == "Added to MyAnimeList: Plan to Watch"
    assert page.window.properties["mal_label"] == "Remove from MyAnimeList"
    assert page.window.properties["mal"].startswith("MAL: Plan to Watch")


def test_mal_button_on_the_list_removes_after_asking(page, monkeypatch):
    from resources.lib.myanimelist import listedit
    mal_login()
    FakeNet().route("anime/52991?", FRIEREN_ON_MAL)
    removed = []
    monkeypatch.setattr(listedit, "remove", lambda d, mal_id: removed.append(mal_id))
    page.window.onInit()
    assert page.window.properties["mal_label"] == "Remove from MyAnimeList"
    xbmcgui.yesno_answers.append(True)
    page.window.onClick(ids.SHOW_MAL)
    assert removed == [52991] and page.window.properties["mal_label"] == "Add to MyAnimeList"
    assert page.window.properties["mal"] == ""


def test_mal_button_failure_keeps_the_page_as_it_was(page, monkeypatch):
    from resources.lib import errors
    from resources.lib.myanimelist import listedit
    mal_login()
    FakeNet().route("anime/52991?", NOT_ON_MAL)
    def down(*args):
        raise errors.NetworkError("offline")
    monkeypatch.setattr(listedit, "add", down)
    page.window.onInit()
    pick_menu(1)
    page.window.onClick(ids.SHOW_MAL)
    assert xbmcgui.notifications[-1][1] == "MyAnimeList could not be updated. Try again later."
    assert page.window.properties["mal_label"] == "Add to MyAnimeList"


def test_paired_phone_search_leaves_the_show_page_for_the_results(page, monkeypatch):
    from resources.lib.gui import actions
    page.window.onInit()
    monkeypatch.setattr(actions, "phone_search", lambda: "bocchi")
    page.tick()
    assert page.window.closed and page.result == ("grid", "search:bocchi")

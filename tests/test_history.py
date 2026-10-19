"""Watch history, manual marks and Continue Watching (DEC-005, DEC-028, DEC-029, DEC-032)."""

import pytest
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import router
from resources.lib.kodi import paths
from resources.lib.models import Episode, Show
from resources.lib.metadata import catalog
from resources.lib.storage import history as history_mod
from resources.lib.storage.history import History

BASE = "plugin://plugin.video.novaflix/"


def dispatch(path, query=""):
    router.dispatch([BASE + path, "1", query])


def items():
    return [item for _, _, item, _ in xbmcplugin.directory_items]


def show(anilist_id=1, total=12, **kw):
    return Show(anilist_id=anilist_id, title=f"Show {anilist_id}", poster=f"p{anilist_id}.jpg",
                mal_id=100 + anilist_id, format="TV", status="FINISHED", episodes_total=total, **kw)


@pytest.fixture
def hist():
    return History(paths.profile_dir())


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(history_mod, "_clock", lambda: now[0])
    return now


# -- storage --------------------------------------------------------------------

def test_below_90_percent_keeps_resume_point(hist):
    assert hist.save_position(1, 3, 101, 600, 1440) is False
    assert hist.states(1) == {3: (600, 1440, False)}


def test_at_90_percent_watched_and_resume_cleared(hist):
    assert hist.save_position(1, 3, 101, 1296, 1440) is True  # exactly 90 %
    assert hist.states(1) == {3: (0, 1440, True)}


def test_rewatch_never_unmarks(hist):
    hist.save_position(1, 3, 101, 1400, 1440)
    hist.save_position(1, 3, 101, 500, 1440)
    assert hist.states(1)[3] == (500, 1440, True)


def test_first_minute_is_not_a_resume_point(hist):
    hist.save_position(1, 3, 101, 45, 1440)
    assert hist.states(1)[3] == (0, 1440, False)


def test_manual_marks(hist):
    hist.save_position(1, 3, 101, 600, 1440)
    hist.mark(1, 3, True)
    assert hist.states(1)[3][0::2] == (0, True)
    hist.mark(1, 3, False)
    assert hist.states(1)[3][0::2] == (0, False)
    hist.mark_show(1, [1, 2], True)
    assert {e for e, s in hist.states(1).items() if s[2]} == {1, 2}
    hist.mark_show(1, [], False)
    assert hist.states(1) == {}


def test_history_survives_clear_cache(hist):
    hist.save_position(1, 3, 101, 600, 1440)
    dispatch("clear_cache")
    assert hist.states(1) == {3: (600, 1440, False)}


def test_continue_watching_newest_first_one_row_per_show(hist, clock):
    for s in (show(1), show(2)):
        hist.remember_show(s)
    hist.save_position(1, 1, 101, 1400, 1440)
    clock[0] += 10
    hist.save_position(2, 5, 102, 600, 1440)
    clock[0] += 10
    hist.save_position(1, 2, 101, 300, 1440)
    rows = hist.continue_watching()
    assert [(r["anilist_id"], r["episode"]) for r in rows] == [(1, 2), (2, 5)]
    assert rows[0]["title"] == "Show 1" and rows[0]["position_s"] == 300


# -- views ----------------------------------------------------------------------

def test_continue_watching_menu(hist, clock):
    for s in (show(1), show(2), show(3, total=2)):
        hist.remember_show(s)
    hist.save_position(3, 2, 103, 1400, 1440)   # finished the last episode: hidden
    clock[0] += 10
    hist.save_position(2, 5, 102, 1400, 1440)   # watched 5 -> next is 6
    clock[0] += 10
    hist.save_position(1, 2, 101, 754, 1440)    # mid-episode
    dispatch("continue")
    labels = [i.getLabel() for i in items()]
    assert labels == ["Show 1 — Episode 2 · resume at 12:34", "Show 2 — Next: Episode 6"]
    resume_item = items()[0]
    assert resume_item.properties["IsPlayable"] == "true"
    assert resume_item.tag.values["ResumePoint"] == 754
    urls = [u for _, u, _, _ in xbmcplugin.directory_items]
    assert urls[0].endswith("play?id=1&ep=2") and urls[1].endswith("show?id=2")


def test_continue_watching_empty_explains():
    dispatch("continue")
    assert xbmcgui.notifications and "Nothing started yet" in xbmcgui.notifications[-1][1]


def test_show_page_shows_watched_and_resume(hist, monkeypatch):
    s = show(1, total=3)
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, _id: s)
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, _s: [Episode(anilist_id=1, number=n) for n in (1, 2, 3)])
    monkeypatch.setattr(catalog.Catalog, "fanart", lambda self, _s: None)
    monkeypatch.setattr(catalog.Catalog, "dub_estimates", lambda self, _s, _n: {})
    hist.save_position(1, 1, 101, 1400, 1440)
    hist.save_position(1, 2, 101, 600, 1440)
    dispatch("show", "?id=1")
    ep1, ep2, ep3 = items()
    assert ep1.tag.values["Playcount"] == 1 and "ResumePoint" not in ep1.tag.values
    assert ep2.tag.values["Playcount"] == 0 and ep2.tag.values["ResumePoint"] == 600
    assert ep3.tag.values["Playcount"] == 0  # no row = unwatched, whatever Kodi remembers
    assert ep1.context_menu[0][0] == "Mark as unwatched"
    assert ep2.context_menu[0][0] == "Mark as watched"
    assert "history/mark?id=1&ep=2&watched=1" in ep2.context_menu[0][1]


def test_mark_route_updates_and_refreshes(hist):
    dispatch("history/mark", "?id=1&ep=4&watched=1")
    assert hist.states(1)[4][2] is True
    assert "Container.Refresh" in xbmc.builtins_executed


def test_mark_show_watched_uses_aired_episodes(hist, monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, _id: show(1))
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, _s: [Episode(anilist_id=1, number=n) for n in (1, 2, 3)])
    dispatch("history/mark_show", "?id=1&watched=1")
    assert sorted(hist.states(1)) == [1, 2, 3]


def test_mark_show_unwatched_asks_first(hist):
    hist.mark(1, 1, True)
    xbmcgui.yesno_answers.append(False)
    dispatch("history/mark_show", "?id=1&watched=0")
    assert hist.states(1)
    dispatch("history/mark_show", "?id=1&watched=0")  # default answer: yes
    assert hist.states(1) == {}


def test_show_lists_offer_show_marks():
    from resources.lib.views import listing
    listing.add_show(1, show(7))
    labels = [label for label, _ in items()[0].context_menu]
    assert "Mark show as watched" in labels and "Mark show as unwatched" in labels


def test_context_menus_cover_dec_036():
    from resources.lib.views import listing
    listing.add_show(1, show(7))
    show_menu = dict(items()[0].context_menu)
    assert show_menu["Related & sequels"] == "Container.Update(plugin://plugin.video.novaflix/related?id=7)"
    assert show_menu["Add to Favourites"].startswith("RunPlugin(")
    from resources.lib.views import history
    assert "Choose a different source" in [entry[0] for entry in history.episode_context(7, 3, None)]


def test_episode_context_builtins(hist, monkeypatch):
    s = show(1, total=1)
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, _id: s)
    monkeypatch.setattr(catalog.Catalog, "episodes", lambda self, _s: [Episode(anilist_id=1, number=1)])
    monkeypatch.setattr(catalog.Catalog, "fanart", lambda self, _s: None)
    monkeypatch.setattr(catalog.Catalog, "dub_estimates", lambda self, _s, _n: {})
    dispatch("show", "?id=1")
    menu = dict(items()[0].context_menu)
    assert menu["Choose a different source"] == "PlayMedia(plugin://plugin.video.novaflix/play?id=1&ep=1&refresh=1)"


def test_related_without_entries_explains():
    from resources.lib.views import show as show_view
    import types
    original = catalog.Catalog.show
    catalog.Catalog.show = lambda self, _id: show(1)
    try:
        show_view.related(types.SimpleNamespace(handle=1, params={"id": "1"}))
    finally:
        catalog.Catalog.show = original
    assert "No related entries" in xbmcgui.notifications[-1][1]



def test_continue_watching_rows_carry_updated_at(hist, clock):
    hist.remember_show(show(1))
    hist.save_position(1, 1, 101, 600, 1440)
    assert hist.continue_watching()[0]["updated_at"] == clock[0]

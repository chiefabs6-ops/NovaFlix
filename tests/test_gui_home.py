# tests/test_gui_home.py
"""Home view (Plan 4): rows, hero from Trending, rotation, offline state, TMDB key missing, refresh after playback."""

import pytest
import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import media
from resources.lib.gui import app as app_mod, ids, lists, loader
from resources.lib.gui.cards import Card


def titles(n):
    return [media.Title(media_type="tv", tmdb_id=i, title=f"Show {i}", overview="Plot.", backdrop=f"b{i}.jpg",
                        poster=f"p{i}.jpg") for i in range(1, n + 1)]


def row(key):
    if key.startswith("continue"):
        return lists.Page("Continue Watching", [Card(label="BB", action=("watch", "tv", 1396, 5, 2, 754))])
    return lists.Page(key, [Card(label=f"{key} 1", action=("title", "tv", 1))], False, "", titles(6))


@pytest.fixture
def make_app(monkeypatch):
    def build(row_fn=row):
        monkeypatch.setattr(lists, "home_row", row_fn)
        window = app_mod.AppWindow("novaflix-app.xml", "", "Default", "1080i")
        a = app_mod.App(window, loader.Loader(spawn=loader.inline))
        window.app = a
        window.onInit()
        return a
    return build


def test_rows_and_hero(make_app):
    w = make_app().window
    assert [w.getControl(c).size() for c in ids.HOME_ROWS] == [1, 1, 1, 1]
    assert [w.properties[f"row{n}_title"] for n in range(4)] == ["Continue Watching", "Trending Now", "Popular shows",
                                                                  "Popular movies"]
    assert w.properties["hero_title"] == "Show 1" and w.properties["hero_art"] == "b1.jpg"
    assert w.properties["hero_count"] == "5"


def test_hero_rotates_unless_a_hero_button_has_focus(make_app):
    a = make_app()
    start = a.home.hero_since
    a.window.setFocusId(ids.HOME_ROWS[1])
    a.tick(start + 10)
    assert a.window.properties["hero_index"] == "1"
    a.window.setFocusId(ids.HERO_PLAY)
    a.tick(start + 30)
    assert a.window.properties["hero_index"] == "1"


def test_play_now_and_more_info(make_app, monkeypatch):
    a = make_app()
    played, opened = [], []
    from resources.lib.gui import actions, title
    monkeypatch.setattr(actions, "play_title", played.append)
    monkeypatch.setattr(title, "open_title", lambda m, i: opened.append((m, i)))
    a.window.onClick(ids.HERO_PLAY)
    a.window.onClick(ids.HERO_INFO)
    assert played[0].tmdb_id == 1 and opened == [("tv", 1)]


def test_continue_card_resumes(make_app):
    make_app().window.onClick(ids.HOME_ROWS[0])
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/watch?type=tv&id=1396&s=5&e=2&resume=754)"


def test_one_failed_row_says_so_and_rest_work(make_app):
    from resources.lib import errors

    def flaky(key):
        if key == "popular_tv":
            raise errors.NetworkError("down")
        return row(key)
    a = make_app(flaky)
    assert a.window.properties["row2_status"] == "Couldn't load"
    assert a.window.getControl(ids.HOME_ROWS[1]).size() == 1 and not a.window.properties.get("offline")


def test_offline_shows_retry(make_app):
    from resources.lib import errors

    def offline(key):
        if key.startswith("continue"):
            return lists.Page("Continue Watching", [])
        raise errors.NetworkError("down")
    a = make_app(offline)
    assert a.window.properties["offline"] and a.window.focus_id == ids.HOME_RETRY


def test_missing_tmdb_key_asks_once_for_settings(make_app):
    def missing(key):
        if key.startswith("continue"):
            return lists.Page("Continue Watching", [])
        raise lists.TmdbKeyMissing()
    a = make_app(missing)
    assert len(xbmcgui.yesno_calls) == 1 and "TMDB key" in xbmcgui.yesno_calls[0][1]
    assert xbmcaddon.opened_settings
    assert a.window.properties["row1_status"] == "Add your TMDB key in Settings to browse."


def test_continue_row_refreshes_after_playback(make_app, monkeypatch):
    a = make_app()
    xbmc.cond_visibility["Player.HasVideo"] = True
    a.tick()
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page("Continue Watching", [
        Card(label="BB", action=("watch", "tv", 1396, 5, 3, 0)), Card(label="Other", action=("title", "tv", 2))]))
    xbmc.cond_visibility["Player.HasVideo"] = False
    a.tick()
    assert a.window.getControl(ids.HOME_ROWS[0]).size() == 2


def test_late_local_continue_row_does_not_replace_the_full_one(make_app):
    a = make_app()
    full = lists.Page("Continue Watching", [Card(label="A", action=("title", "tv", 1)),
                                            Card(label="B", action=("title", "tv", 2))])
    a.home._deliver("continue", full, None)
    a.home._deliver("continue:local", lists.Page("Continue Watching", [Card(label="A", action=("title", "tv", 1))]),
                    None)
    assert a.window.getControl(ids.HOME_ROWS[0]).size() == 2

# tests/test_gui_home.py
"""M12: Home view — rows, hero, rotation, offline state, refresh after playback."""

import pytest
import xbmc
import xbmcgui

from resources.lib.gui import app as app_mod, home, ids, lists, loader
from resources.lib.gui.cards import Card
from resources.lib.models import Show


def shows(n):
    return [Show(anilist_id=i, title=f"Show {i}", description="Plot.", banner=f"b{i}.jpg", poster=f"p{i}.jpg")
            for i in range(1, n + 1)]


def row(key):
    if key == "continue":
        return lists.Page("Continue Watching", [Card(label="Frieren", action=("play", 7, 5, 754))])
    return lists.Page(key, [Card(label=f"{key} 1", action=("show", 1))], False, "", shows(6))


@pytest.fixture
def make_app(monkeypatch):
    def build(row_fn=row):
        monkeypatch.setattr(lists, "home_row", row_fn)
        window = app_mod.AppWindow("aniverse-app.xml", "", "Default", "1080i")
        a = app_mod.App(window, loader.Loader(spawn=loader.inline))
        window.app = a
        window.onInit()
        return a
    return build


def test_rows_and_hero(make_app):
    a = make_app()
    w = a.window
    assert [w.getControl(c).size() for c in ids.HOME_ROWS] == [1, 1, 1, 1]
    assert w.properties["row0_title"] == "Continue Watching" and w.properties["row1_title"] == "Trending Now"
    assert w.properties["hero_title"] == "Show 1" and w.properties["hero_art"] == "b1.jpg"
    assert w.properties["hero_count"] == "5" and w.properties["featured"] == "FEATURED"


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
    from resources.lib.gui import actions, show
    monkeypatch.setattr(actions, "play_next", played.append)
    monkeypatch.setattr(show, "open_show", lambda i: opened.append(i))
    a.window.onClick(ids.HERO_PLAY)
    a.window.onClick(ids.HERO_INFO)
    assert played[0].anilist_id == 1 and opened == [1]


def test_continue_card_resumes(make_app):
    a = make_app()
    a.window.onClick(ids.HOME_ROWS[0])
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.aniverse/play?id=7&ep=5&resume=754)"


def test_one_failed_row_says_so_and_rest_work(make_app):
    from resources.lib import errors
    def flaky(key):
        if key == "airing":
            raise errors.NetworkError("down")
        return row(key)
    a = make_app(flaky)
    assert a.window.properties["row2_status"] == "Couldn't load"
    assert a.window.getControl(ids.HOME_ROWS[1]).size() == 1 and not a.window.properties.get("offline")


def test_offline_shows_retry(make_app):
    from resources.lib import errors
    def offline(key):
        if key == "continue":
            return lists.Page("Continue Watching", [])
        raise errors.NetworkError("down")
    a = make_app(offline)
    assert a.window.properties["offline"] and a.window.focus_id == ids.HOME_RETRY


def test_continue_row_refreshes_after_playback(make_app, monkeypatch):
    a = make_app()
    xbmc.cond_visibility["Player.HasVideo"] = True
    a.tick()
    monkeypatch.setattr(lists, "home_row", lambda key: lists.Page("Continue Watching", [
        Card(label="Frieren", action=("play", 7, 6, 0)), Card(label="Other", action=("show", 2))]))
    xbmc.cond_visibility["Player.HasVideo"] = False
    a.tick()
    assert a.window.getControl(ids.HOME_ROWS[0]).size() == 2


def test_continue_row_shows_local_cards_then_mal_cards(make_app):
    seen = []

    def rows(key):
        seen.append(key)
        if key == "continue:local":
            return lists.Page("Continue Watching", [Card(label="Local", action=("play", 7, 5, 0))])
        if key == "continue":
            return lists.Page("Continue Watching", [Card(label="Local", action=("play", 7, 5, 0)),
                                                    Card(label="From MAL", action=("play", 9, 4, 0))])
        return row(key)

    a = make_app(rows)
    assert seen[:2] == ["continue:local", "continue"]
    assert a.window.getControl(ids.HOME_ROWS[0]).size() == 2


def test_late_local_continue_row_does_not_replace_the_merged_one(make_app):
    a = make_app()
    merged = lists.Page("Continue Watching", [Card(label="A", action=("show", 1)), Card(label="B", action=("show", 2))])
    a.home._deliver("continue", merged, None)
    a.home._deliver("continue:local", lists.Page("Continue Watching", [Card(label="A", action=("show", 1))]), None)
    assert a.window.getControl(ids.HOME_ROWS[0]).size() == 2


# -- Continue Watching availability ------------------------------------------------------------

def checking(anilist_id, episode):
    return Card(label=f"S{anilist_id}", label2=f"Ep {episode} · Checking...", avail="checking",
                check=(anilist_id, episode), action=("play", anilist_id, episode, 0))


def continue_rows(*cards):
    def row_fn(key):
        if key.startswith("continue"):
            return lists.Page("Continue Watching", [Card(**c.__dict__) for c in cards])
        return row(key)
    return row_fn


def test_continue_cards_update_in_place_and_one_failure_stays_on_its_card(make_app, monkeypatch):
    from resources.lib.sources import availability as av
    calls = []
    def check(anilist_id, episode):
        calls.append((anilist_id, episode))
        if anilist_id == 2:
            raise RuntimeError("provider exploded")
        return {1: av.Availability(av.AVAILABLE), 3: av.Availability(av.UPCOMING)}[anilist_id]
    monkeypatch.setattr(av, "check", check)
    a = make_app(continue_rows(checking(1, 6), checking(2, 4), checking(3, 13)))
    control = a.window.getControl(ids.HOME_ROWS[0])
    assert [control.getListItem(i).getLabel2() for i in range(3)] == [
        "Ep 6 · Available", "Ep 4 · Availability unknown", "Ep 13 · Not aired yet"]
    assert [control.getListItem(i).properties["avail"] for i in range(3)] == ["available", "unknown", "upcoming"]
    # "continue:local" and "continue" both fill the row: each episode is still checked only once
    assert sorted(calls) == [(1, 6), (2, 4), (3, 13)]
    played = []
    monkeypatch.setattr(app_mod.actions, "play_episode", lambda *args: played.append(args))
    control.selectItem(0)
    a.window.onClick(ids.HOME_ROWS[0])
    assert played == [(1, 6, 0)]
    searched = []
    monkeypatch.setattr(app_mod.actions, "search_episode", lambda *args: searched.append(args))
    control.selectItem(1)
    a.window.onClick(ids.HOME_ROWS[0])
    assert searched == [(2, 4)]


def test_upcoming_card_opens_the_show_instead_of_playing(make_app, monkeypatch):
    from resources.lib.gui import show as show_mod
    from resources.lib.sources import availability as av
    monkeypatch.setattr(av, "check", lambda i, e: av.Availability(av.UPCOMING))
    opened = []
    monkeypatch.setattr(show_mod, "open_show", lambda anilist_id: opened.append(anilist_id))
    played = []
    monkeypatch.setattr(app_mod.actions, "play_episode", lambda *args: played.append(args))
    a = make_app(continue_rows(checking(3, 13)))
    a.window.getControl(ids.HOME_ROWS[0]).selectItem(0)
    a.window.onClick(ids.HOME_ROWS[0])
    assert opened == [3] and played == []

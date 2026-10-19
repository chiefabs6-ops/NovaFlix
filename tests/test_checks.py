"""Availability checks for cards on screen (availability plan, Task 2)."""

import xbmcgui

from resources.lib.gui import cards, checks, ids, items, loader
from resources.lib.gui.cards import Card
from resources.lib.sources import availability as av


class FakeApp:
    def __init__(self, spawn=loader.inline):
        self.loader = loader.Loader(spawn=spawn)
        self.window = xbmcgui.WindowXML("novaflix-app.xml", "", "Default", "1080i")


def checking(tmdb_id, season=2, episode=4):
    return Card(label=f"T{tmdb_id}", label2="S2 E4 · Checking...", avail="checking",
                check=("tv", tmdb_id, season, episode), action=("watch", "tv", tmdb_id, season, episode, 0))


def show(app, control_id, page_cards):
    app.window.getControl(control_id).addItems(items.to_listitems(page_cards))


def test_cards_update_in_place_and_actions_follow_the_state(monkeypatch):
    states = {1: av.Availability(av.AVAILABLE), 2: av.Availability(av.UNKNOWN),
              3: av.Availability(av.UPCOMING, "2026-10-24"), 4: av.Availability(av.NO_ENGLISH)}
    monkeypatch.setattr(av, "check", lambda m, i, s, e: states[i])
    app = FakeApp()
    page = [checking(i) for i in (1, 2, 3, 4)]
    show(app, ids.HOME_ROWS[0], page)
    checks.AvailabilityChecks(app).watch(ids.HOME_ROWS[0], page)
    control = app.window.getControl(ids.HOME_ROWS[0])
    assert [control.getListItem(i).getLabel2() for i in range(4)] == [
        "S2 E4 · Available", "S2 E4 · Availability unknown", "S2 E4 · Airs Sat 24 Oct", "S2 E4 · No English audio"]
    assert [c.avail for c in page] == ["available", "unknown", "upcoming", "sub_only"]
    assert [c.action for c in page] == [("watch", "tv", 1, 2, 4, 0), ("search", "tv", 2, 2, 4), ("title", "tv", 3),
                                        ("watch", "tv", 4, 2, 4, 0)]


def test_one_failure_stays_on_its_card(monkeypatch):
    def check(m, i, s, e):
        if i == 2:
            raise RuntimeError("provider exploded")
        return av.Availability(av.AVAILABLE)
    monkeypatch.setattr(av, "check", check)
    app = FakeApp()
    page = [checking(1), checking(2)]
    show(app, ids.GRID, page)
    checks.AvailabilityChecks(app).watch(ids.GRID, page)
    assert [c.avail for c in page] == ["available", "unknown"]


def test_each_episode_checked_once(monkeypatch):
    calls = []
    monkeypatch.setattr(av, "check", lambda m, i, s, e: calls.append(i) or av.Availability(av.AVAILABLE))
    app = FakeApp()
    c = checks.AvailabilityChecks(app)
    first, again = [checking(1)], [checking(1)]
    show(app, ids.HOME_ROWS[0], first)
    c.watch(ids.HOME_ROWS[0], first)
    c.watch(ids.HOME_ROWS[0], again)  # the full Continue Watching row replaces the local one
    assert calls == [1] and again[0].avail == "available"


def test_result_after_reset_is_ignored(monkeypatch):
    pending = []
    monkeypatch.setattr(av, "check", lambda m, i, s, e: av.Availability(av.AVAILABLE))
    app = FakeApp(spawn=pending.append)
    c = checks.AvailabilityChecks(app)
    page = [checking(1)]
    show(app, ids.GRID, page)
    c.watch(ids.GRID, page)
    c.reset()
    app.window.getControl(ids.GRID).reset()
    for job in pending:
        job()
    assert page[0].avail == "checking"


def test_grid_checks_rows_around_the_selection(monkeypatch):
    calls = []
    monkeypatch.setattr(av, "check", lambda m, i, s, e: calls.append(i) or av.Availability(av.AVAILABLE))
    app = FakeApp()
    page = [checking(i) for i in range(60)]
    show(app, ids.GRID, page)
    checks.AvailabilityChecks(app).follow_grid(ids.GRID, page, 32)
    assert calls == list(range(30, 48))


def test_availability_text_for_movies_and_the_title_page():
    text = __import__("xbmcaddon").Addon().getLocalizedString
    assert cards.availability_text(av.Availability(av.AVAILABLE), 0, 0, text) == "Available"
    assert cards.availability_text(av.Availability(av.UNKNOWN), 1, 2, text, title_page=True) == \
        "S1 E2 · Could not check streams right now (try again later)"
    assert cards.availability_text(av.Availability(av.UPCOMING), 1, 2, text) == "S1 E2 · Not aired yet"

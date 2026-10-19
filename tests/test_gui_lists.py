# tests/test_gui_lists.py
"""M12: grid/home data comes from the existing catalog, history and favourites."""

import json

import pytest
import xbmc
import xbmcaddon

from helpers import FakeNet, fixture
from resources.lib.gui import actions, lists
from resources.lib.gui.cards import Card
from resources.lib.kodi import paths
from resources.lib.metadata import catalog
from resources.lib.models import Episode, Show
from resources.lib.myanimelist import progress
from resources.lib.storage.favourites import Favourites
from resources.lib.storage.history import History

TRENDING = fixture("anilist_trending.json")


def show(i, **kw):
    return Show(anilist_id=i, title=f"Show {i}", poster=f"https://x/cover/large/{i}.jpg", mal_id=100 + i,
                format="TV", status="FINISHED", episodes_total=12, **kw)


def test_trending_page_cards():
    FakeNet().route("graphql.anilist.co", TRENDING)
    page = lists.load("trending")
    assert page.title == "Trending Now" and page.cards
    first = TRENDING["data"]["Page"]["media"][0]
    assert page.cards[0].action == ("show", first["id"])
    assert "/cover/medium/" in (page.cards[0].poster or "/cover/medium/")
    assert page.more == TRENDING["data"]["Page"]["pageInfo"]["hasNextPage"]
    assert page.shows[0].anilist_id == first["id"]


def test_home_row_caps_at_twenty_with_view_all(monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "trending", lambda self, page=1: ([show(i) for i in range(1, 31)], True))
    row = lists.home_row("trending")
    assert len(row.cards) == 21 and row.cards[-1].kind == "more" and row.cards[-1].action == ("grid", "trending")


def test_last_page_has_no_more(monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "popular", lambda self, page=1: ([show(1)], False))
    page = lists.load("popular", page=3)
    assert page.more is False and len(page.cards) == 1


def test_continue_uses_saved_details_only(monkeypatch):
    hist = History(paths.profile_dir())
    hist.remember_show(show(5))
    hist.save_position(5, 2, 105, 600, 1440)
    monkeypatch.setattr(catalog.Catalog, "cached_show", lambda self, i: None)
    FakeNet()  # any network call would raise
    page = lists.load("continue")
    assert page.cards[0].action == ("play", 5, 2, 600) and page.cards[0].wide is None


def test_continue_empty_explains():
    page = lists.load("continue")
    assert page.cards == [] and page.empty == "Nothing started yet. Episodes you play appear here."


def test_favourites_and_genres(monkeypatch):
    favs = Favourites(paths.profile_dir())
    favs.add(show(9))
    favs.close()
    assert lists.load("favourites").cards[0].action == ("show", 9)
    monkeypatch.setattr(catalog.Catalog, "genres", lambda self: ["Action", "Comedy"])
    genres = lists.load("genres")
    assert [c.action for c in genres.cards] == [("grid", "genre:Action"), ("grid", "genre:Comedy")]


def test_search_tiles_and_results(monkeypatch):
    first = lists.load("search")
    assert [c.action for c in first.cards[:2]] == [("search_new",), ("search_phone",)]
    monkeypatch.setattr(catalog.Catalog, "search", lambda self, text, page=1: ([show(3)], False))
    results = lists.load("search:frieren")
    assert results.title == "Results for frieren" and results.cards[0].action == ("show", 3)
    assert [c.action for c in lists.load("search").cards][2] == ("grid", "search:frieren")  # remembered


def test_mal_needs_setup():
    with pytest.raises(lists.mal.MalSetupMissing):
        lists.load("mal")


def test_mal_status_cards(monkeypatch):
    xbmcaddon.settings.update(mal_client_id="cid", mal_username="me")
    entry = lists.mal.MalEntry(mal_id=105, title="Show 5", picture="p.jpg", watched=3, status="watching")
    other = lists.mal.MalEntry(mal_id=999, title="Unknown", picture="u.jpg", watched=0, status="watching")
    monkeypatch.setattr(lists.mylists, "_mal_page", lambda c, u, s, p: ([entry, other], False))
    monkeypatch.setattr(catalog.Catalog, "by_mal_ids", lambda self, ids: {105: show(5)})
    cards = lists.load("mal:watching").cards
    # The next episode's availability is checked; the card still opens the show page.
    assert cards[0].action == ("show", 5) and cards[0].label2 == "Ep 4 · Checking..."
    assert cards[0].check == (5, 4) and not cards[0].check_play
    assert cards[1].action == ("noop",) and cards[1].label2 == "not found on AniList" and not cards[1].check


def test_mal_completed_and_caught_up_cards_keep_their_count(monkeypatch):
    xbmcaddon.settings.update(mal_client_id="cid", mal_username="me")
    entry = lists.mal.MalEntry(mal_id=105, title="Show 5", picture="p.jpg", watched=12, status="watching")
    monkeypatch.setattr(lists.mylists, "_mal_page", lambda c, u, s, p: ([entry], False))
    monkeypatch.setattr(catalog.Catalog, "by_mal_ids", lambda self, ids: {105: show(5)})
    for status in ("completed", "watching"):  # completed: never checked; watching 12/12: nothing next
        card = lists.load(f"mal:{status}").cards[0]
        assert card.label2 == "12/12" and not card.check


def test_mal_card_result_changes_label_not_action():
    from resources.lib.gui import cards as cards_mod
    from resources.lib.sources.availability import Availability
    card = cards_mod.Card(label="S", action=("show", 5), avail="checking", check=(5, 4), check_play=False)
    for state, label in (("available", "Ep 4 · Available"), ("sub_only", "Ep 4 · Sub only"),
                         ("unavailable", "Ep 4 · Not available"), ("upcoming", "Ep 4 · Not aired yet")):
        cards_mod.apply_availability(card, Availability(state), lists.ui.string)
        assert (card.label2, card.avail, card.action) == (label, state, ("show", 5))


def test_torbox_without_key_raises():
    xbmcaddon.settings.update(playback_service=0, torbox_api_key="")
    with pytest.raises(lists.ServiceMissing):
        lists.load("torbox")


def _franchise(partial=False, **rows):
    from resources.lib.metadata.franchise import ROWS, Franchise
    return Franchise(title="Show 1", rows={name: rows.get(name, []) for name in ROWS}, partial=partial)


def test_related_rows_in_order_with_year_and_format(monkeypatch):
    from resources.lib.models import RelationNode as N
    result = _franchise(movies=[N(3, "Movie", "MOVIE", poster="https://x/cover/large/3.jpg", start=(2020, 10, 16))],
                        sequels=[N(2, "Season 2", "TV", start=(2021, 12, 5)), N(4, "Season 3", "TV")])
    monkeypatch.setattr(catalog.Catalog, "franchise", lambda self, i: result)
    page = lists.related("1")
    assert page.title == "Show 1" and page.notice == "" and page.empty == ""
    assert [title for title, _ in page.rows] == ["Sequels", "Movies"]
    sequels = page.rows[0][1]
    assert [c.label for c in sequels] == ["Season 2", "Season 3"]
    assert sequels[0].label2 == "2021 · TV" and sequels[1].label2 == "TV"
    assert sequels[0].action == ("show", 2)
    assert page.rows[1][1][0].poster == "https://x/cover/medium/3.jpg"


def test_related_empty_and_partial(monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "franchise", lambda self, i: _franchise(partial=True))
    page = lists.related("1")
    assert page.rows == [] and page.empty == "No related entries for this show"
    assert page.notice == "Some related entries could not be loaded"


def test_play_episode_builds_play_url():
    actions.play_episode(7, 3, 754)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.aniverse/play?id=7&ep=3&resume=754)"
    actions.play_episode(7, 4)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.aniverse/play?id=7&ep=4)"


def test_play_next_picks_started_episode(monkeypatch):
    s = show(7)
    monkeypatch.setattr(catalog.Catalog, "episodes", lambda self, x: [Episode(anilist_id=7, number=n) for n in (1, 2, 3)])
    History(paths.profile_dir()).save_position(7, 2, 107, 500, 1440)
    actions.play_next(s)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.aniverse/play?id=7&ep=2&resume=500)"


def test_episode_choice_resume_or_start(monkeypatch):
    History(paths.profile_dir()).save_position(7, 2, 107, 500, 1440)
    monkeypatch.setattr(actions.dialogs, "resume_choice", lambda pos: False)
    actions.episode_choice(7, 2)
    assert xbmc.builtins_executed[-1].endswith("play?id=7&ep=2)")
    monkeypatch.setattr(actions.dialogs, "resume_choice", lambda pos: None)
    before = len(xbmc.builtins_executed)
    actions.episode_choice(7, 2)
    assert len(xbmc.builtins_executed) == before  # cancelled: nothing plays


def test_continue_local_never_asks_mal_for_new_data(monkeypatch):
    calls = []
    monkeypatch.setattr(progress, "continue_rows", lambda network=True: calls.append(network) or [])
    lists.load("continue:local")
    lists.load("continue")
    assert calls == [False, True]


def test_home_continue_more_card_opens_the_full_list(monkeypatch):
    monkeypatch.setattr(lists, "load", lambda key, page=1: lists.Page("Continue Watching",
                                                                      [Card(label=str(i)) for i in range(25)]))
    assert lists.home_row("continue:local").cards[-1].action == ("grid", "continue")

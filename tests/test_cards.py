# tests/test_cards.py
"""M12: pure card models (no Kodi windows involved)."""

import datetime

from resources.lib.gui import cards
from resources.lib.kodi import ui
from resources.lib.models import Episode, Show

T = ui.string


def show(**kw):
    base = dict(anilist_id=7, title="Frieren", title_romaji="Sousou no Frieren", mal_id=52991, format="TV",
                status="FINISHED", episodes_total=28, year=2023, score=91, genres=["Adventure", "Drama"],
                description="An elf mage. " * 40,
                poster="https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-x.jpg",
                banner="https://s4.anilist.co/file/anilistcdn/media/anime/banner/154587-y.jpg")
    base.update(kw)
    return Show(**base)


def test_small_cover_uses_large_not_extralarge():
    assert cards.small_cover(show().poster).endswith("/cover/medium/bx154587-x.jpg")
    assert cards.small_cover("https://example.org/a.jpg") == "https://example.org/a.jpg"
    assert cards.small_cover(None) is None


def test_show_card():
    card = cards.show_card(show(), "partial")
    assert (card.label, card.dub, card.kind, card.action) == ("Frieren", "partial", "show", ("show", 7))
    assert card.poster.endswith("/cover/medium/bx154587-x.jpg") and card.wide == show().banner


def test_continue_card_started_episode():
    row = dict(anilist_id=7, title="Frieren", poster="p.jpg", mal_id=1, episode=5, position_s=754.0,
               duration_s=1440.0, watched=False, episodes_total=28)
    card = cards.continue_card(row, show(), T)
    assert card.label2 == "Ep 5 · 11:26 left"
    assert (card.position, card.duration) == (754.0, 1440.0)
    assert card.action == ("play", 7, 5, 754)
    assert card.wide == show().banner


def test_continue_card_watched_episode_offers_next():
    row = dict(anilist_id=7, title="Frieren", poster="p.jpg", mal_id=1, episode=5, position_s=0.0,
               duration_s=1440.0, watched=True, episodes_total=28)
    card = cards.continue_card(row, show(), T)
    # Not offered as available until checked (Continue Watching availability).
    assert card.label2 == "Ep 6 · Checking..." and card.position == 0
    assert card.avail == "checking" and card.check == (7, 6) and card.action == ("play", 7, 6, 0)


def test_apply_availability_states():
    from resources.lib.sources.availability import Availability
    row = dict(anilist_id=7, title="Frieren", poster="p.jpg", mal_id=1, episode=5, position_s=0.0,
               duration_s=1440.0, watched=True, episodes_total=28)
    def applied(result):
        return cards.apply_availability(cards.continue_card(row, show(), T), result, T)
    card = applied(Availability("available"))
    assert (card.label2, card.avail, card.action) == ("Ep 6 · Available", "available", ("play", 7, 6, 0))
    at = datetime.datetime(2026, 10, 18, 15, 0).timestamp()
    card = applied(Availability("upcoming", int(at)))
    assert card.label2 == "Ep 6 · Upcoming Sun 18 Oct" and card.action == ("show", 7)
    card = applied(Availability("upcoming"))
    assert card.label2 == "Ep 6 · Not aired yet" and card.action == ("show", 7)
    card = applied(Availability("sub_only"))
    assert (card.label2, card.avail, card.action) == ("Ep 6 · Sub only", "sub_only", ("play", 7, 6, 0))
    card = applied(Availability("unavailable"))
    assert card.label2 == "Ep 6 · Not available" and card.action == ("search", 7, 6)
    card = applied(Availability("unknown"))
    assert card.label2 == "Ep 6 · Availability unknown" and card.action == ("search", 7, 6)
    card = applied(Availability("finished"))
    assert card.label2 == "All episodes watched" and card.action == ("show", 7)


def test_part_watched_card_is_available_without_a_check():
    row = dict(anilist_id=7, title="Frieren", poster="p.jpg", mal_id=1, episode=3, position_s=300.0,
               duration_s=1440.0, watched=False, episodes_total=28)
    card = cards.continue_card(row, show(), T)
    assert card.avail == "available" and not card.check and card.action == ("play", 7, 3, 300)


def test_continue_card_without_saved_details():
    row = dict(anilist_id=7, title="Frieren", poster="p.jpg", mal_id=1, episode=2, position_s=0.0,
               duration_s=0.0, watched=False, episodes_total=None)
    card = cards.continue_card(row, None, T)
    assert card.wide is None and card.poster == "p.jpg" and card.label2 == "Ep 2"
    assert card.action == ("play", 7, 2, 0)


def test_recent_card():
    aired = datetime.datetime(2026, 10, 9, 15).timestamp()
    card = cards.recent_card(show(), 4, aired, None, T)
    day = datetime.datetime.fromtimestamp(aired)
    assert card.label2 == f"Ep 4 · aired {day:%a} {day.day} {day:%b}"
    assert card.action == ("show", 7)


def test_episode_card_states():
    ep = Episode(anilist_id=7, number=3, title="Killing Magic", air_date="2023-10-06", runtime_min=24,
                 thumbnail="t.jpg")
    card = cards.episode_card(show(), ep, (600.0, 1440.0, False), None, T)
    assert card.label == "3. Killing Magic" and card.label2 == "2023-10-06 · 24 min"
    assert (card.position, card.watched, card.wide) == (600.0, False, "t.jpg")
    assert card.action == ("episode", 7, 3)
    watched = cards.episode_card(show(), ep, (0, 1440.0, True), None, T)
    assert watched.watched and watched.position == 0


def test_episode_card_dub_note_and_missing_title():
    ep = Episode(anilist_id=7, number=9)
    ts = datetime.datetime(2026, 10, 21, 17).timestamp()
    card = cards.episode_card(show(banner=None), ep, None, ts, T)
    day = datetime.datetime.fromtimestamp(ts)
    assert card.label == "Episode 9" and card.note == f"(Dub expected {day:%a} {day.day} {day:%b})"
    assert card.wide.endswith("/cover/medium/bx154587-x.jpg")  # no thumbnail, no banner -> poster


def test_hero_text_and_meta():
    data = cards.hero(show(), text=T)
    assert data["title"] == "Frieren" and data["alt"] == "Sousou no Frieren"
    assert len(data["plot"]) <= 300 and data["plot"].endswith("…")
    assert data["meta"] == "2023 · TV · 28 episodes · Score 91%"
    assert data["art"] == show().banner and data["dark"] is False


def test_hero_art_fallbacks():
    assert cards.hero(show(banner=None), fanart="f.jpg", text=T)["art"] == "f.jpg"
    poster_only = cards.hero(show(banner=None), fanart=None, text=T)
    assert poster_only["art"] == show().poster and poster_only["dark"] is True
    assert cards.hero(show(title_romaji="Frieren"), text=T)["alt"] == ""  # same as title: not repeated


def test_next_episode_rules():
    assert cards.next_episode([1, 2, 3], {1: (0, 1440, True), 2: (300, 1440, False)}) == (2, 300)
    assert cards.next_episode([1, 2, 3], {1: (0, 1440, True)}) == (2, 0)
    assert cards.next_episode([1, 2], {1: (0, 1, True), 2: (0, 1, True)}) == (1, 0)
    assert cards.next_episode([], {}) == (1, 0)


def test_source_row_status():
    assert cards.source_row("A", "1080p · Ready to play", T).status == "ready"
    assert cards.source_row("A", "1080p · Ready in your TorBox", T).status == "ready"
    assert cards.source_row("A", "1080p · Needs downloading", T).status == "download"
    assert cards.source_row("A", "1080p · Blocked by the service", T).status == "blocked"
    assert cards.source_row("A", "1080p · Not checked yet", T).status == "unchecked"
    assert cards.source_row("Check more sources (4 not checked)", "", T).status == "action"


def test_tiles_and_more():
    tile = cards.tile("Comedy", ("grid", "genre:Comedy"), icon="grid_view")
    assert (tile.kind, tile.wide, tile.action) == ("tile", "icon:grid_view", ("grid", "genre:Comedy"))
    more = cards.more_card("trending", T)
    assert (more.label, more.kind, more.action) == ("View All", "more", ("grid", "trending"))


def test_watched_continue_card_plays_the_next_episode():
    # Spec §4.2: Continue Watching select = resume / play next (same rules as Play Now).
    row = dict(anilist_id=7, title="Frieren", poster="p.jpg", mal_id=1, episode=5, position_s=0.0,
               duration_s=1440.0, watched=True, episodes_total=28)
    assert cards.continue_card(row, show(), T).action == ("play", 7, 6, 0)


# -- TV shows and movies (Plan 4) ------------------------------------------------------------

def _text(string_id):
    import xbmcaddon
    return xbmcaddon.Addon().getLocalizedString(string_id)


def test_title_card():
    from helpers import fixture
    from resources.lib import media
    from resources.lib.gui import cards
    t = media.title_from(fixture("tmdb/tv_1396.json"), media.TV)
    card = cards.title_card(t)
    assert (card.label, card.label2, card.poster, card.wide, card.action) == (
        "Breaking Bad", "2008", t.poster, t.backdrop, ("title", "tv", 1396))


def test_title_episode_cards_and_movie_card():
    from helpers import fixture
    from resources.lib import media
    from resources.lib.gui import cards
    t = media.title_from(fixture("tmdb/tv_1396.json"), media.TV)
    raw = fixture("tmdb/tv_1396_season_2.json")["episodes"][2]
    ep = media.episode_from(raw, 1396)
    card = cards.title_episode_card(t, ep, (600.0, 2800.0, False), _text)
    assert card.label == f"3. {raw['name']}" and card.action == ("t_episode", 1396, 2, 3)
    assert card.position == 600.0 and card.wide == ep.still and raw["air_date"] in card.label2
    movie = media.title_from(fixture("tmdb/movie_438631.json"), media.MOVIE)
    film = cards.title_movie_card(movie, None, _text)
    assert film.label == movie.title and film.action == ("t_episode", 438631, 0, 0) and "min" in film.label2


def test_title_meta_and_hero():
    from helpers import fixture
    from resources.lib import media
    from resources.lib.gui import cards
    t = media.title_from(fixture("tmdb/tv_1396.json"), media.TV)
    meta = cards.title_meta(t, _text)
    assert meta.startswith("2008 · TV series · 5 seasons") and "★" in meta and "English" not in meta
    t.original_language = "ko"
    assert cards.title_meta(t, _text).endswith("Korean")
    hero = cards.title_hero(t, _text)
    assert hero["title"] == "Breaking Bad" and hero["art"] == t.backdrop and hero["dark"] is False

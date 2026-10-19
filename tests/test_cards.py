"""Card models for the NovaFlix screens: pure functions, no Kodi windows."""

from resources.lib.gui import cards
from resources.lib.kodi import ui

T = ui.string


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

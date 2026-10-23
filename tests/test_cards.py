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


# -- Cinematic UI: focused-card details (0.4.0) ---------------------------------------------------

def _title(**fields):
    from resources.lib import media
    return media.Title(media_type=fields.pop("media_type", "movie"), tmdb_id=1, title="Charade", **fields)


def test_card_details_from_title():
    card = cards.title_card(_title(overview="Widowed in Paris.", year=1963, rating=7.94,
                                   genres=["Thriller", "Romance", "Comedy"]), T)
    assert (card.rating, card.genres, card.year) == ("★ 7.9", "Thriller, Romance", "1963")
    assert card.plot == "Widowed in Paris." and card.kind_label == "Movie"


def test_card_details_cut_long_plots():
    card = cards.title_card(_title(overview="word " * 80), T)
    assert len(card.plot) <= cards.PEEK_PLOT_MAX and card.plot.endswith("…")


def test_card_details_leave_missing_fields_empty():
    card = cards.title_card(_title(), T)
    assert (card.plot, card.year, card.rating, card.genres) == ("", "", "", "")
    assert cards.title_card(_title()).kind_label == ""  # without text: nothing worded


def test_hero_fields_are_labelled_values():
    hero = cards.title_hero(_title(year=1963, rating=7.94, genres=["Thriller", "Romance"]), T)
    assert (hero["rating"], hero["year"], hero["genres"], hero["kind"]) == ("★ 7.9", "1963", "Thriller, Romance",
                                                                          "Movie")
    empty = cards.title_hero(_title(), T)
    assert (empty["rating"], empty["year"], empty["genres"]) == ("", "", "")


def test_quality_badge():
    assert cards.quality_badge("Charade 1963 2160p UHD BluRay", "") == "4K"
    assert cards.quality_badge("Charade.1963.UHD.REMUX", "") == "4K"
    assert cards.quality_badge("Charade 1963", "1080p · 12.4 GB") == "1080p"
    assert cards.quality_badge("720p BRRip", "") == "720p"
    assert cards.quality_badge("Charade HDCAM", "") == "CAM"
    assert cards.quality_badge("Charade DVDRip", "") == ""
    assert cards.source_row("Charade 2160p", "Ready to play", T).badge == "4K"


def test_quality_badge_says_cam_before_resolution():
    assert cards.quality_badge("Movie.2024.1080p.HDCAM.x264", "") == "CAM"
    assert cards.quality_badge("Movie.2024.1080p.WEB-DL.ts", "") == "1080p"  # .ts is a file extension


def test_tab_rows_become_chips():
    row = cards.source_row("Quality: All (37) — 4K / UHD 7 · 1080p 19 · 720p 5", "", T)
    assert row.kind == "tabs" and row.label == "Quality"
    assert row.chips == ("All 37", "4K 7", "1080p 19", "720p 5")
    lang = cards.source_row("Language: English (23) — Polish 4", "", T)
    assert lang.label == "Language" and lang.chips == ("English 23", "Polish 4")
    other = cards.source_row("Check more sources (4 not checked)", "", T)
    assert other.kind == "source" and other.status == "action" and other.chips == ()


def test_source_details_drop_the_status_shown_on_the_right():
    row = cards.source_row("A 2160p", "2160p · WEB-DL · 7.2 GB · Ready to play", T)
    assert row.note == "Ready to play" and row.details == "2160p · WEB-DL · 7.2 GB"
    unknown = cards.source_row("A", "1080p · 2 GB", T)
    assert unknown.details == "1080p · 2 GB"


def test_tab_chips_use_short_names():
    row = cards.source_row("Quality: 4K / UHD (7) — 4K / UHD 7 · Other / unknown 2", "", T)
    assert row.chips == ("4K 7", "4K 7", "Other 2")

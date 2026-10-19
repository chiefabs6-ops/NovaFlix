"""TMDB responses -> NovaFlix titles, episodes and collections (Plan 2).

Expected values are read from the recorded fixtures, so re-recording never breaks the tests."""

from helpers import fixture
from resources.lib import media

POSTER = "https://image.tmdb.org/t/p/w342"
BACKDROP = "https://image.tmdb.org/t/p/w1280"
STILL = "https://image.tmdb.org/t/p/w300"


def test_movie_details_parse():
    raw = fixture("tmdb/movie_438631.json")
    t = media.title_from(raw, media.MOVIE)
    assert t.key == "movie:438631" and t.is_movie and t.title == raw["title"]
    assert t.year == int(raw["release_date"][:4]) and t.date == raw["release_date"]
    assert t.imdb_id == raw["external_ids"]["imdb_id"] and t.imdb_id.startswith("tt")
    assert t.poster == POSTER + raw["poster_path"] and t.backdrop == BACKDROP + raw["backdrop_path"]
    assert t.collection == (raw["belongs_to_collection"]["id"], raw["belongs_to_collection"]["name"])
    assert t.runtime_min == raw["runtime"] and t.genres == [g["name"] for g in raw["genres"]]
    assert t.rating == raw["vote_average"] and t.seasons == []


def test_tv_details_parse():
    raw = fixture("tmdb/tv_1396.json")
    t = media.title_from(raw, media.TV)
    assert t.key == "tv:1396" and not t.is_movie and t.title == raw["name"]
    assert t.imdb_id == "tt0903747" and t.status == "Ended" and t.next_air is None
    assert [s.number for s in t.seasons] == [1, 2, 3, 4, 5, 0]  # specials last
    first = t.seasons[0]
    raw_first = next(s for s in raw["seasons"] if s["season_number"] == 1)
    assert (first.name, first.episode_count, first.air_date) == (raw_first["name"], raw_first["episode_count"],
                                                                raw_first["air_date"])
    last = raw["last_episode_to_air"]
    assert t.last_aired == (last["season_number"], last["episode_number"])
    assert t.runtime_min is None  # episode_run_time is [] for this show


def test_running_show_has_next_air():
    raw = fixture("tmdb/tv_456.json")
    t = media.title_from(raw, media.TV)
    nxt = raw["next_episode_to_air"]
    assert t.next_air == (nxt["season_number"], nxt["episode_number"], nxt["air_date"])


def test_search_multi_skips_people_and_keeps_both_types():
    raw = fixture("tmdb/search_multi_dune.json")
    results = raw["results"] + [{"id": 1, "media_type": "person", "name": "Someone"}]
    found = media.titles_from(results)
    assert [t.media_type for t in found] == [r["media_type"] for r in raw["results"]]
    assert {media.MOVIE, media.TV} <= {t.media_type for t in found}


def test_list_items_get_genre_names():
    raw = fixture("tmdb/movie_popular.json")
    names = {g["id"]: g["name"] for g in fixture("tmdb/genre_movie.json")["genres"]}
    found = media.titles_from(raw["results"], genre_names=names, media_type=media.MOVIE)
    first = raw["results"][0]
    assert found[0].genres == [names[i] for i in first["genre_ids"] if i in names]
    assert found[0].key == f"movie:{first['id']}"


def test_sparse_title_parses_with_nones():
    t = media.title_from({"id": 5, "media_type": "tv", "name": "X"})
    assert (t.title, t.year, t.poster, t.imdb_id, t.rating, t.seasons) == ("X", None, None, None, None, [])
    assert media.title_from({"id": 6, "media_type": "movie", "title": "Y", "release_date": ""}).year is None


def test_rating_is_none_without_votes():
    assert media.title_from({"id": 7, "title": "Z", "vote_average": 0, "vote_count": 0}, media.MOVIE).rating is None


def test_title_round_trips_through_dict():
    t = media.title_from(fixture("tmdb/tv_456.json"), media.TV)
    assert media.Title.from_dict(t.to_dict()) == t


def test_season_episodes_parse():
    raw = fixture("tmdb/tv_1396_season_2.json")
    episodes = [media.episode_from(e, 1396) for e in raw["episodes"]]
    assert [e.number for e in episodes] == list(range(1, len(raw["episodes"]) + 1))
    first, raw_first = episodes[0], raw["episodes"][0]
    assert (first.tmdb_id, first.season, first.title, first.air_date) == (1396, 2, raw_first["name"], raw_first["air_date"])
    assert first.still == STILL + raw_first["still_path"] and first.runtime_min == raw_first["runtime"]
    assert media.Episode.from_dict(first.to_dict()) == first


def test_collection_parts_in_release_order():
    raw = fixture("tmdb/collection.json")
    c = media.collection_from(raw)
    assert (c.tmdb_id, c.name) == (raw["id"], raw["name"])
    dated = sorted((p for p in raw["parts"] if p.get("release_date")), key=lambda p: p["release_date"])
    assert [p.tmdb_id for p in c.parts][:len(dated)] == [p["id"] for p in dated]
    assert all(p.is_movie for p in c.parts)


def test_image_without_path_is_none():
    assert media.image(None, "w342") is None and media.image("", "w342") is None


def test_odd_shapes_do_not_break_a_title():
    t = media.title_from({"id": 8, "name": "Odd", "next_episode_to_air": {"season_number": 2, "episode_number": None},
                          "last_episode_to_air": {"air_date": "2020-01-01"}, "seasons": [{"name": "no number"}]},
                         media.TV)
    assert (t.next_air, t.last_aired, t.seasons) == (None, None, [])
    m = media.title_from({"id": 9, "title": "M", "belongs_to_collection": {"name": "no id"}}, media.MOVIE)
    assert m.collection is None


def test_malformed_episode_is_skipped():
    raw = fixture("tmdb/tv_1396_season_1.json")["episodes"]
    broken = [dict(raw[0], episode_number=None)] + raw[1:]
    assert [e.number for e in media.episodes_from(broken, 1396)] == [e["episode_number"] for e in raw[1:]]


def test_original_language_and_names():
    assert media.title_from(fixture("tmdb/tv_1396.json"), media.TV).original_language == "en"
    assert media.language_name("ko") == "Korean" and media.language_name("xx") == "XX"
    assert media.language_name(None) == ""

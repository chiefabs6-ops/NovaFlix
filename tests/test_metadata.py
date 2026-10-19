import copy
import datetime
import os

import pytest

from helpers import FakeNet, fixture
from resources.lib import errors
from resources.lib.metadata import anilist, anizip, catalog, dubs

TRENDING = fixture("anilist_trending.json")
FRIEREN = fixture("anilist_media_154587.json")
AIRING = fixture("anilist_airing.json")
GENRES = fixture("anilist_genres.json")
ANIZIP = fixture("anizip_154587.json")
DUBS = fixture("mal_dubs.json")


# -- AniList parsing ----------------------------------------------------------

def test_display_title_prefers_english_then_romaji():
    assert anilist.display_title({"english": "Frieren", "romaji": "Sousou no Frieren"}) == "Frieren"
    assert anilist.display_title({"english": None, "romaji": "Sousou no Frieren"}) == "Sousou no Frieren"
    assert anilist.display_title({"native": "葬送のフリーレン"}) == "葬送のフリーレン"


def test_to_show_maps_core_fields():
    show = anilist.to_show(FRIEREN["data"]["Media"])
    assert show.anilist_id == 154587
    assert show.mal_id == 52991
    assert show.title.startswith("Frieren")
    assert show.title_romaji == "Sousou no Frieren"
    assert show.format == "TV"
    assert show.poster and show.poster.startswith("https://")
    assert "<br>" not in (show.description or "")


def test_relations_drop_manga_and_music():
    show = anilist.to_show(FRIEREN["data"]["Media"])
    formats = {r.format for r in show.relations}
    assert "MANGA" not in formats and "MUSIC" not in formats
    assert any(r.relation == "SEQUEL" for r in show.relations)
    assert any(r.format == "ONA" and r.relation == "SIDE_STORY" for r in show.relations)


def test_clean_description_strips_markup():
    assert anilist.clean_description("A<br><br>B <i>c</i> <b>d</b>") == "A\n\nB c d"
    assert anilist.clean_description("") is None


def test_media_page_sends_catalog_formats_and_parses_paging():
    net = FakeNet().route("graphql.anilist.co", TRENDING)
    shows, more = anilist.media_page(sort=["TRENDING_DESC"])
    assert len(shows) == len(TRENDING["data"]["Page"]["media"])
    assert more == TRENDING["data"]["Page"]["pageInfo"]["hasNextPage"]
    body = net.calls[0][2]
    assert '"formats": ["TV", "TV_SHORT", "ONA", "MOVIE"]' in body
    assert "isAdult: false" in body


def test_graphql_errors_raise_http_error():
    FakeNet().route("graphql.anilist.co", {"errors": [{"message": "Too Many Requests"}], "data": None})
    with pytest.raises(errors.HttpError):
        anilist.media_page()


def test_recently_aired_filters_adult_and_non_catalog_formats():
    data = copy.deepcopy(AIRING)
    items = data["data"]["Page"]["airingSchedules"]
    items[0]["media"]["isAdult"] = True
    items[1]["media"]["format"] = "OVA"
    FakeNet().route("graphql.anilist.co", data)
    result, _ = anilist.recently_aired(0, 1)
    assert len(result) == len(items) - 2


def test_genres_exclude_adult_genre():
    FakeNet().route("graphql.anilist.co", GENRES)
    names = anilist.genres()
    assert "Hentai" not in names and "Action" in names


# -- ani.zip ------------------------------------------------------------------

def test_anizip_keeps_regular_episodes_only():
    eps = anizip.episodes(ANIZIP, 154587)
    assert sorted(eps) == [1, 2, 3, 28]
    assert eps[1].title == "The Journey`s End"
    assert eps[1].air_date == "2023-09-29"
    assert eps[1].thumbnail.startswith("https://")


def test_anizip_drops_numbers_beyond_episode_count():
    data = copy.deepcopy(ANIZIP)
    data["episodes"]["99"] = data["episodes"]["1"]
    assert 99 not in anizip.episodes(data, 154587)


def test_anizip_mappings_include_kitsu_id():
    assert anizip.mappings(ANIZIP)["kitsu_id"] == 46474


# -- catalog ------------------------------------------------------------------

@pytest.fixture
def cat(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "_clock", lambda: datetime.datetime(2026, 10, 10, 12).timestamp())
    return catalog.Catalog(str(tmp_path))


def test_season_helpers():
    assert catalog.season_for(datetime.date(2026, 10, 10)) == ("FALL", 2026)
    assert catalog.season_for(datetime.date(2026, 1, 1)) == ("WINTER", 2026)
    assert catalog.next_season("FALL", 2026) == ("WINTER", 2027)
    assert catalog.next_season("SPRING", 2026) == ("SUMMER", 2026)


def test_airing_this_season_queries_current_season(cat):
    net = FakeNet().route("graphql.anilist.co", TRENDING)
    cat.airing_this_season()
    assert '"season": "FALL"' in net.calls[0][2] and '"seasonYear": 2026' in net.calls[0][2]


def test_upcoming_queries_next_season(cat):
    net = FakeNet().route("graphql.anilist.co", TRENDING)
    cat.upcoming()
    assert '"season": "WINTER"' in net.calls[0][2] and '"seasonYear": 2027' in net.calls[0][2]


def test_lists_are_cached(cat):
    net = FakeNet().route("graphql.anilist.co", TRENDING)
    first, _ = cat.trending()
    second, _ = cat.trending()
    assert net.count("anilist") == 1
    assert [s.anilist_id for s in first] == [s.anilist_id for s in second]


def test_show_details_cached(cat):
    net = FakeNet().route("graphql.anilist.co", FRIEREN)
    cat.show(154587)
    cat.show(154587)
    assert net.count("anilist") == 1


def test_finished_show_lists_all_episodes_with_anizip_details(cat):
    FakeNet().route("graphql.anilist.co", FRIEREN).route("api.ani.zip", ANIZIP)
    show = cat.show(154587)
    show.status, show.next_episode, show.episodes_total = "FINISHED", None, 28
    eps = cat.episodes(show)
    assert [e.number for e in eps] == list(range(1, 29))
    assert eps[0].title == "The Journey`s End"
    assert eps[4].title is None  # not in trimmed fixture: shown as absent, not invented


def test_airing_show_lists_only_aired_episodes(cat):
    FakeNet().route("graphql.anilist.co", FRIEREN).route("api.ani.zip", ANIZIP)
    show = cat.show(154587)
    show.status, show.next_episode = "RELEASING", 5
    assert [e.number for e in cat.episodes(show)] == [1, 2, 3, 4]


def test_anizip_failure_falls_back_to_numbers(cat):
    FakeNet().route("graphql.anilist.co", FRIEREN).route("api.ani.zip", OSError("down"))
    show = cat.show(154587)
    show.status, show.next_episode, show.episodes_total = "FINISHED", None, 3
    eps = cat.episodes(show)
    assert [e.number for e in eps] == [1, 2, 3]
    assert all(e.title is None for e in eps)


def test_not_yet_released_has_no_episodes(cat):
    FakeNet().route("graphql.anilist.co", FRIEREN).route("api.ani.zip", ANIZIP)
    show = cat.show(154587)
    show.status, show.next_episode = "NOT_YET_RELEASED", None
    assert cat.episodes(show) == []


def test_movie_is_single_entry(cat):
    FakeNet().route("graphql.anilist.co", FRIEREN)
    show = cat.show(154587)
    show.format = "MOVIE"
    eps = cat.episodes(show)
    assert len(eps) == 1 and eps[0].title == show.title


# -- dubs ---------------------------------------------------------------------

def test_dub_refresh_and_lookup(tmp_path):
    FakeNet().route("MAL-Dubs", DUBS)
    assert dubs.refresh(str(tmp_path))
    index = dubs.DubIndex(str(tmp_path))
    assert index.status(52991) == dubs.DUBBED
    assert index.status(DUBS["incomplete"][0]) == dubs.PARTIAL
    assert index.status(999999999) is None
    assert index.status(None) is None


def test_dub_refresh_failure_keeps_last_copy(tmp_path):
    FakeNet().route("MAL-Dubs", DUBS)
    dubs.refresh(str(tmp_path))
    FakeNet().route("MAL-Dubs", OSError("down"))
    assert dubs.refresh(str(tmp_path)) is False
    assert dubs.DubIndex(str(tmp_path)).status(52991) == dubs.DUBBED


def test_missing_dub_file_means_no_badges(tmp_path):
    assert dubs.DubIndex(str(tmp_path)).status(52991) is None


def test_dub_staleness(tmp_path):
    assert dubs.is_stale(str(tmp_path))
    FakeNet().route("MAL-Dubs", DUBS)
    dubs.refresh(str(tmp_path))
    path = os.path.join(str(tmp_path), dubs.FILENAME)
    mtime = os.path.getmtime(path)
    assert not dubs.is_stale(str(tmp_path), now=mtime + 3600)
    assert dubs.is_stale(str(tmp_path), now=mtime + 8 * 24 * 3600)


def test_fresh_lists_use_one_hour_ttl(cat, monkeypatch):
    seen = []
    real_set = cat._cache.set
    monkeypatch.setattr(cat._cache, "set", lambda k, v, ttl: (seen.append((k.split(":")[0], ttl)), real_set(k, v, ttl)))
    FakeNet().route("graphql.anilist.co", TRENDING)
    cat.airing_this_season()
    cat.trending()
    assert ("season", 3600) in seen and ("trending", 24 * 3600) in seen


# -- relation nodes (M14) -------------------------------------------------------

def _rel_media(i, fmt="TV", start=(2020, 4, 1), edges=()):
    return {"id": i, "idMal": 1000 + i, "format": fmt, "title": {"english": f"Show {i}", "romaji": f"Romaji {i}"},
            "coverImage": {"large": f"https://x/cover/large/{i}.jpg"},
            "startDate": {"year": start[0], "month": start[1], "day": start[2]} if start else {"year": None},
            "relations": {"edges": [{"relationType": r, "node": {"id": n, "type": t, "format": f}}
                                    for r, n, t, f in edges]}}


def _rel_page(*media):
    return {"data": {"Page": {"pageInfo": {"hasNextPage": False}, "media": list(media)}}}


def test_relation_nodes_maps_fields_and_filters_edges():
    net = FakeNet().route("graphql.anilist.co", _rel_page(_rel_media(1, edges=[
        ("SEQUEL", 2, "ANIME", "TV"), ("ADAPTATION", 3, "MANGA", "MANGA"),
        ("OTHER", 4, "ANIME", "MUSIC"), ("SIDE_STORY", 5, "ANIME", "OVA")])))
    nodes = anilist.relation_nodes([1])
    node = nodes[1]
    assert node.title == "Show 1" and node.mal_id == 1001 and node.format == "TV"
    assert node.poster == "https://x/cover/large/1.jpg" and node.start == (2020, 4, 1)
    assert node.edges == [("SEQUEL", 2), ("SIDE_STORY", 5)]
    body = net.calls[0][2]
    assert "id_in: $ids" in body and "idMal" in body and "startDate" in body


def test_relation_nodes_partial_dates():
    FakeNet().route("graphql.anilist.co", _rel_page(_rel_media(1, start=(2020, None, None)), _rel_media(2, start=None)))
    nodes = anilist.relation_nodes([1, 2])
    assert nodes[1].start == (2020, 0, 0) and nodes[2].start is None


def test_relation_nodes_batches_fifty_ids_per_call():
    net = FakeNet().route("graphql.anilist.co", _rel_page())
    assert anilist.relation_nodes(range(1, 52)) == {}
    assert len(net.calls) == 2


def test_relation_node_dict_round_trip():
    import json
    from resources.lib.models import RelationNode
    node = RelationNode(anilist_id=1, title="A", format="TV", start=(2020, 1, 2), edges=[("SEQUEL", 2)])
    assert RelationNode.from_dict(json.loads(json.dumps(node.to_dict()))) == node


# -- catalog franchise (M14) -----------------------------------------------------

def _graph_nodes():
    from resources.lib.models import RelationNode as N
    return {1: N(1, "S1", "TV", start=(2019, 1, 1), edges=[("SEQUEL", 2)]),
            2: N(2, "S2", "TV", start=(2020, 1, 1), edges=[("PREQUEL", 1), ("SEQUEL", 3)]),
            3: N(3, "Movie", "MOVIE", start=(2021, 1, 1), edges=[("PREQUEL", 2)])}


def _fake_relation_nodes(monkeypatch, fail_on_call=None):
    calls = []

    def fake(ids):
        calls.append(sorted(ids))
        if fail_on_call == len(calls):
            raise errors.RateLimited("AniList 429", retry_after=60)
        return {i: n for i, n in _graph_nodes().items() if i in ids}
    monkeypatch.setattr(anilist, "relation_nodes", fake)
    return calls


def test_franchise_rows_and_cached_second_open(cat, monkeypatch):
    calls = _fake_relation_nodes(monkeypatch)
    result = cat.franchise(1)
    assert [n.anilist_id for n in result.rows["sequels"]] == [2]
    assert [n.anilist_id for n in result.rows["movies"]] == [3]
    assert len(calls) == 3
    again = cat.franchise(1)
    assert again == result and len(calls) == 3


def test_franchise_reuses_cached_nodes_for_another_show(cat, monkeypatch):
    calls = _fake_relation_nodes(monkeypatch)
    cat.franchise(1)
    result = cat.franchise(2)
    assert [n.anilist_id for n in result.rows["prequels"]] == [1]
    assert len(calls) == 3  # every node came from relnode:


def test_partial_franchise_is_not_cached(cat, monkeypatch):
    _fake_relation_nodes(monkeypatch, fail_on_call=2)
    result = cat.franchise(1)
    assert result.partial and result.rows["sequels"] == []
    assert cat._cache.get("franchise:v1:1") is None
    _fake_relation_nodes(monkeypatch)
    assert not cat.franchise(1).partial

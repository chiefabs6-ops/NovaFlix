"""M14: franchise walk — chain, extras, rows, ordering, cap, failures."""

import pytest

from resources.lib import errors
from resources.lib.metadata import franchise
from resources.lib.models import RelationNode


def node(i, fmt="TV", start=(2020, 1, 1), edges=()):
    return RelationNode(anilist_id=i, title=f"N{i}", format=fmt, start=start, edges=list(edges))


class Graph:
    """Fake fetch: answers from a fixed set of nodes and records each call."""

    def __init__(self, *nodes, fail_on_call=None):
        self.nodes = {n.anilist_id: n for n in nodes}
        self.calls = []
        self.fail_on_call = fail_on_call

    def __call__(self, ids):
        self.calls.append(sorted(ids))
        if self.fail_on_call == len(self.calls):
            raise errors.RateLimited("AniList 429", retry_after=60)
        return {i: self.nodes[i] for i in ids if i in self.nodes}


def demon_slayer():
    # 1 S1 → 2 movie → 3 S2 → 4 S3 → 5 S4; 10 special of S1; 11 side story of S2 (with its own
    # side story 12, never walked); 20 spin-off of S3.
    return Graph(
        node(1, start=(2019, 4, 6), edges=[("SEQUEL", 2), ("SIDE_STORY", 10)]),
        node(2, "MOVIE", (2020, 10, 16), [("PREQUEL", 1), ("SEQUEL", 3)]),
        node(3, start=(2021, 12, 5), edges=[("PREQUEL", 2), ("SEQUEL", 4), ("SIDE_STORY", 11)]),
        node(4, start=(2023, 4, 9), edges=[("PREQUEL", 3), ("SEQUEL", 5), ("SPIN_OFF", 20)]),
        node(5, start=(2024, 5, 12), edges=[("PREQUEL", 4)]),
        node(10, "SPECIAL", (2019, 10, 1), [("PARENT", 1)]),
        node(11, "ONA", (2022, 2, 1), [("PARENT", 3), ("SIDE_STORY", 12)]),
        node(12, "ONA", (2022, 3, 1)),
        node(20, start=(2024, 1, 1), edges=[("SPIN_OFF", 4)]),
    )


def ids(result):
    return {name: [n.anilist_id for n in entries] for name, entries in result.rows.items()}


def test_from_first_season_whole_franchise_by_format():
    graph = demon_slayer()
    result = franchise.walk(1, graph)
    assert result.title == "N1" and not result.partial
    assert ids(result) == {"sequels": [3, 4, 5], "prequels": [], "side_stories": [11], "ovas": [10],
                           "movies": [2], "other": [20]}


def test_one_fetch_per_level_and_extras_not_walked():
    graph = demon_slayer()
    franchise.walk(1, graph)
    assert graph.calls == [[1], [2, 10], [3], [4, 11], [5, 20]]
    assert not any(12 in call for call in graph.calls)


def test_from_middle_season():
    result = franchise.walk(3, demon_slayer())
    assert ids(result) == {"sequels": [4, 5], "prequels": [1], "side_stories": [11], "ovas": [10],
                           "movies": [2], "other": [20]}


def test_opened_from_movie_in_chain():
    result = franchise.walk(2, demon_slayer())
    assert ids(result)["prequels"] == [1] and ids(result)["sequels"] == [3, 4, 5]
    assert ids(result)["movies"] == []


def test_opened_from_special_walks_parent_chain_by_date():
    result = franchise.walk(10, demon_slayer())
    assert ids(result) == {"sequels": [3, 4, 5], "prequels": [1], "side_stories": [11], "ovas": [],
                           "movies": [2], "other": [20]}


def test_rows_sort_oldest_first_missing_dates_last():
    graph = Graph(node(1, edges=[("SEQUEL", 2), ("SEQUEL", 3), ("SEQUEL", 4), ("SEQUEL", 5)]),
                  node(2, start=None), node(3, start=(2021, 5, 1)), node(4, start=(2021, 0, 0)), node(5, start=None))
    assert ids(franchise.walk(1, graph))["sequels"] == [4, 3, 2, 5]


def test_cycle_ends_and_opened_show_never_listed():
    graph = Graph(node(1, edges=[("SEQUEL", 2), ("PREQUEL", 2)]), node(2, edges=[("SEQUEL", 1), ("SIDE_STORY", 1)]))
    result = franchise.walk(1, graph)
    assert ids(result)["sequels"] == [2]
    assert all(1 not in entries for entries in ids(result).values())


def test_unknown_ids_are_skipped():
    graph = Graph(node(1, edges=[("SEQUEL", 2), ("SEQUEL", 99)]), node(2))
    assert ids(franchise.walk(1, graph))["sequels"] == [2]


def test_cap_at_sixty_entries():
    graph = Graph(node(1, edges=[("SIDE_STORY", i) for i in range(100, 170)]),
                  *[node(i, "ONA") for i in range(100, 170)])
    result = franchise.walk(1, graph)
    assert len(result.rows["side_stories"]) == franchise.CAP and result.capped


def test_failure_mid_walk_keeps_found_rows():
    graph = demon_slayer()
    graph.fail_on_call = 3
    result = franchise.walk(1, graph)
    assert result.partial
    assert ids(result)["movies"] == [2] and ids(result)["ovas"] == [10] and ids(result)["sequels"] == []


def test_failure_on_first_fetch_raises():
    graph = demon_slayer()
    graph.fail_on_call = 1
    with pytest.raises(errors.RateLimited):
        franchise.walk(1, graph)


def test_unknown_opened_show_raises():
    with pytest.raises(errors.HttpError):
        franchise.walk(1, Graph())


def test_franchise_dict_round_trip():
    import json
    result = franchise.walk(1, demon_slayer())
    again = franchise.Franchise.from_dict(json.loads(json.dumps(result.to_dict())))
    assert again == result


def test_cap_never_pushes_out_the_sequel_chain():
    graph = Graph(node(1, edges=[("SIDE_STORY", i) for i in range(100, 170)] + [("SEQUEL", 2)]),
                  node(2, start=(2021, 1, 1), edges=[("SEQUEL", 3)]), node(3, start=(2022, 1, 1)),
                  *[node(i, "ONA") for i in range(100, 170)])
    result = franchise.walk(1, graph)
    assert ids(result)["sequels"] == [2, 3]
    assert len(result.rows["side_stories"]) == franchise.CAP and result.capped


def test_older_season_found_from_sequel_side_is_placed_by_date():
    graph = Graph(node(1, start=(2015, 1, 1), edges=[("SEQUEL", 2)]),
                  node(2, start=(2016, 1, 1), edges=[("PREQUEL", 1), ("PREQUEL", 3)]),
                  node(3, start=(2010, 1, 1)))
    result = franchise.walk(1, graph)
    assert ids(result)["prequels"] == [3] and ids(result)["sequels"] == [2]

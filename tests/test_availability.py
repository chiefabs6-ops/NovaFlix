# tests/test_availability.py
"""Continue Watching: which shows count as started, and whether the next episode can be watched."""

import pytest
import xbmcaddon

from resources.lib import errors
from resources.lib.gui import cards, lists
from resources.lib.kodi import paths, ui
from resources.lib.metadata import catalog as catalog_mod
from resources.lib.models import Candidate, Show
from resources.lib.myanimelist import progress
from resources.lib.sources import availability as av
from resources.lib.storage.cache import Cache
from resources.lib.views import sources

NOW = 1_800_000_000


def show(**kw):
    base = dict(anilist_id=7, title="Frieren", mal_id=52991, format="TV", status="RELEASING", episodes_total=24,
                next_episode=13, next_airing_at=NOW + 86400)
    base.update(kw)
    return Show(**base)


def save_show(s):
    cache = Cache(paths.profile_dir())
    cache.set(f"show:v2:{s.anilist_id}", s.to_dict(), 3600)
    cache.close()


@pytest.fixture
def searches(monkeypatch):
    """Fake provider search: answers from `searches.state["result"]`, records calls, fills the source cache like the real one."""
    class Calls(list):
        pass
    calls = Calls()
    state = {"result": ({"torrentio": "ok", "nyaa": "ok"}, [Candidate(origin="nyaa", release_name="x 1080p",
                                                                        info_hash="a" * 40, resolution="1080p")])}

    def discover(wanted, found_settings, cache, cancelled):
        calls.append(wanted.number)
        outcomes, found = state["result"]
        if any(v in ("ok", "empty") for v in outcomes.values()):
            cache.set(sources._cache_key(wanted.show, wanted.number),
                      {"candidates": [c.to_dict() for c in found], "outcomes": outcomes}, 3600)
        return outcomes, found
    monkeypatch.setattr(sources, "_discover", discover)
    monkeypatch.setattr(sources, "_wanted", lambda s, c, n: sources.discovery.Wanted(show=s, number=n))
    monkeypatch.setattr(av, "_clock", lambda: NOW)
    calls.state = state
    return calls


# -- aired: AniList airing data -------------------------------------------------------------

@pytest.mark.parametrize("kw,number,expected", [
    (dict(), 12, True),                                                  # before AniList's next episode
    (dict(), 13, False),                                                 # next episode, scheduled tomorrow
    (dict(next_airing_at=NOW - 60), 13, True),                           # saved schedule has passed
    (dict(), 14, False),                                                 # further ahead, schedule in future
    (dict(next_airing_at=NOW - 60), 15, None),                           # stale details: cannot tell
    (dict(status="FINISHED", next_episode=None, next_airing_at=None), 24, True),
    (dict(status="FINISHED", next_episode=None, next_airing_at=None), 25, av.FINISHED),
    (dict(status="NOT_YET_RELEASED", next_episode=None, next_airing_at=None), 1, False),
    (dict(status="HIATUS", next_episode=None, next_airing_at=None), 5, None),
    (dict(format="MOVIE", status="FINISHED", episodes_total=1, next_episode=None), 2, av.FINISHED),
])
def test_aired(kw, number, expected):
    assert av.aired(show(**kw), number, now=NOW) == expected


# -- check: providers -------------------------------------------------------------------------

def test_aired_episode_found_is_available_and_cached_for_the_source_list(searches):
    save_show(show())
    assert av.check(7, 6).state == av.AVAILABLE
    assert av.check(7, 6).state == av.AVAILABLE and searches == [6]  # second time from the source cache
    assert av.cached(7, 6).state == av.AVAILABLE


def test_not_aired_episode_is_upcoming_with_its_time_and_never_searched(searches):
    save_show(show())
    result = av.check(7, 13)
    assert (result.state, result.airing_at) == (av.UPCOMING, NOW + 86400) and searches == []
    assert av.check(7, 14) == av.Availability(av.UPCOMING, 0)


def test_dub_only_counts_only_dubbed_sources(searches):
    save_show(show())
    xbmcaddon.settings["dub_only"] = True
    searches.state["result"] = ({"nyaa": "ok"}, [Candidate(origin="nyaa", release_name="x", audio=None)])
    assert av.check(7, 6).state == av.SUB_ONLY
    searches.state["result"] = ({"nyaa": "ok"}, [Candidate(origin="nyaa", release_name="x", audio="dual")])
    assert av.check(7, 7).state == av.AVAILABLE
    xbmcaddon.settings["dub_only"] = False
    assert av.check(7, 6).state == av.AVAILABLE  # same saved sources, Dub only off


def test_aired_episode_nobody_has_is_unavailable(searches):
    save_show(show())
    searches.state["result"] = ({"torrentio": "empty", "nyaa": "empty"}, [])
    assert av.check(7, 6).state == av.UNAVAILABLE


def test_only_filtered_out_sources_is_unavailable(searches, monkeypatch):
    save_show(show())
    xbmcaddon.settings["min_resolution"] = 4  # 2160p only
    searches.state["result"] = ({"nyaa": "ok"}, [Candidate(origin="nyaa", release_name="x", resolution="720p")])
    assert av.check(7, 6).state == av.UNAVAILABLE


def test_provider_failure_is_unknown_not_unavailable(searches):
    save_show(show())
    searches.state["result"] = ({"torrentio": "failed", "nyaa": "empty"}, [])
    assert av.check(7, 6).state == av.UNKNOWN


def test_all_providers_failing_is_unknown_and_not_retried_at_once(searches):
    save_show(show())
    searches.state["result"] = ({"torrentio": "failed", "nyaa": "failed"}, [])  # e.g. timeouts
    assert av.check(7, 6).state == av.UNKNOWN
    assert av.check(7, 6).state == av.UNKNOWN and searches == [6]
    assert av.cached(7, 6).state == av.UNKNOWN


def test_cannot_tell_if_aired_and_nothing_found_is_unknown(searches):
    save_show(show(status="HIATUS", next_episode=None, next_airing_at=None))
    searches.state["result"] = ({"torrentio": "empty", "nyaa": "empty"}, [])
    assert av.check(7, 6).state == av.UNKNOWN


def test_past_the_end_of_a_finished_series(searches):
    save_show(show(status="FINISHED", next_episode=None, next_airing_at=None))
    assert av.check(7, 25).state == av.FINISHED and searches == []


def test_missing_details_or_crash_is_unknown(searches, monkeypatch):
    def offline(self, anilist_id):
        raise errors.NetworkError("down")
    monkeypatch.setattr(catalog_mod.Catalog, "show", offline)
    assert av.check(8, 2).state == av.UNKNOWN
    save_show(show())
    monkeypatch.setattr(sources, "_discover", lambda *a: 1 / 0)
    assert av.check(7, 6).state == av.UNKNOWN


def test_cached_without_saved_details_needs_a_check():
    assert av.cached(99, 2) is None


def test_cached_episodes_reads_saved_results_only(searches):
    save_show(show())
    av.check(7, 6)
    searches.state["result"] = ({"torrentio": "failed", "nyaa": "failed"}, [])
    av.check(7, 7)
    found = av.cached_episodes(7, [5, 6, 7, 13])
    assert {n: a.state for n, a in found.items()} == {6: av.AVAILABLE, 7: av.UNKNOWN, 13: av.UPCOMING}
    assert searches == [6, 7]  # no search for 5 (nothing saved) or 13 (not aired)
    assert av.cached_episodes(99, [1]) == {}


# -- eligibility ------------------------------------------------------------------------------

def row(**kw):
    base = dict(anilist_id=7, title="Frieren", poster="p", mal_id=52991, episode=5, position_s=0.0,
                duration_s=1440.0, watched=True, episodes_total=24, updated_at=1.0)
    base.update(kw)
    return base


@pytest.mark.parametrize("kw,expected", [
    (dict(episode=1, watched=True), False),                        # MAL at episode 1: not started
    (dict(episode=0, watched=True), False),
    (dict(episode=2, watched=True), True),
    (dict(episode=5, watched=True), True),
    (dict(episode=1, watched=False, position_s=300.0), True),      # really playing episode 1 in NovaFlix
    (dict(episode=2, watched=False, position_s=0.0), False),       # only episode 1 done
    (dict(episode=3, watched=False, position_s=0.0), True),
])
def test_started(kw, expected):
    assert progress.started(row(**kw)) == expected


@pytest.fixture
def rows(monkeypatch):
    data = []
    monkeypatch.setattr(progress, "continue_rows", lambda network=True: list(data))
    return data


def labels(page):
    return [(c.label, c.label2) for c in page.cards]


def test_continue_lists_only_started_active_shows_once(rows, monkeypatch):
    entries = {111: {"list_status": "completed"}, 222: {"list_status": "watching"}}
    monkeypatch.setattr(progress, "show_entry", lambda mal_id, directory=None, network=True: entries.get(mal_id))
    rows += [row(anilist_id=1, title="One", episode=1),                    # MAL count 1
             row(anilist_id=2, title="Done", mal_id=111),                  # Completed on MAL
             row(anilist_id=3, title="Going", mal_id=222, episode=5),
             row(anilist_id=3, title="Going", mal_id=222, episode=4),      # duplicate
             row(anilist_id=4, title="Ended", episode=24, episodes_total=24),
             row(anilist_id=5, title="Local", mal_id=None, episode=1, watched=False, position_s=200.0)]
    page = lists.load("continue:local")
    assert labels(page) == [("Going", "Ep 6 · Checking..."), ("Local", "Ep 1 · %s left" % cards.clock(1240))]


def test_continue_uses_saved_availability_at_once(rows, searches):
    save_show(show(anilist_id=3))
    rows += [row(anilist_id=3, title="Going", episode=12)]
    page = lists.load("continue:local")
    assert page.cards[0].label2.startswith("Ep 13 · Upcoming ") and page.cards[0].avail == "upcoming"
    assert page.cards[0].action == ("show", 3) and searches == []


def test_continue_drops_a_show_whose_saved_details_say_it_ended(rows):
    save_show(show(anilist_id=3, status="FINISHED", next_episode=None, next_airing_at=None, episodes_total=12))
    rows += [row(anilist_id=3, title="Old", episode=12, episodes_total=None)]
    assert lists.load("continue:local").cards == []


def test_continue_with_unusual_numbers_and_no_metadata_does_not_crash(rows, searches):
    rows += [row(anilist_id=9, title="Special", mal_id=None, episode=3, episodes_total=None)]
    card = lists.load("continue:local").cards[0]
    assert card.check == (9, 4) and card.avail == "checking"
    assert av.check(9, 4).state == av.UNKNOWN  # no details saved and AniList is not reachable in tests


def test_strings_exist():
    for string_id in list(range(30299, 30306)) + [30314, 30315]:
        assert ui.string(string_id)

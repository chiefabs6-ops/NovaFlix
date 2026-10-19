"""Dub release-date hint (DEC-056): AnimeSchedule parsing, estimates, catalog
caching and the show page note."""

import copy
import datetime

import pytest
import xbmcplugin

from helpers import FakeNet, fixture
from resources.lib import router
from resources.lib.metadata import animeschedule, catalog

FRIEREN2 = fixture("animeschedule_59978.json")
ENTRY = FRIEREN2["anime"][0]
UTC = datetime.timezone.utc


def utc(*args):
    return datetime.datetime(*args, tzinfo=UTC)


# -- parsing and estimates ----------------------------------------------------

def test_schedule_reads_premier_time_and_delay():
    sched = animeschedule.dub_schedule(ENTRY)
    assert sched["premier"] == "2026-02-06T15:00:00+00:00"  # date of dubPremier + hour of dubTime
    assert sched["delays"] == [["2026-03-06", "2026-03-13"]]
    assert sched["override"] is None


def test_no_dub_announced_means_no_schedule():
    entry = dict(ENTRY, dubPremier="0001-01-01T00:00:00Z")
    assert animeschedule.dub_schedule(entry) is None


def test_weekly_estimates_shift_after_delay():
    dates = animeschedule.estimates(animeschedule.dub_schedule(ENTRY), range(1, 11))
    assert dates[1] == utc(2026, 2, 6, 15)
    assert dates[4] == utc(2026, 2, 27, 15)
    assert dates[5] == utc(2026, 3, 13, 15)  # 6 March slot skipped
    assert dates[10] == utc(2026, 4, 17, 15)


def test_episode_override_releases_several_at_once():
    entry = dict(ENTRY, dubDelayedFrom="0001-01-01T00:00:00Z", dubDelayedUntil="0001-01-01T00:00:00Z",
                 dubEpisodeOverride={"overrideDate": "2026-03-20T00:00:00Z", "overrideEpisode": 7,
                                     "episodesAired": 2})
    dates = animeschedule.estimates(animeschedule.dub_schedule(entry), range(1, 11))
    assert dates[6] == utc(2026, 3, 13, 15)
    assert dates[7] == dates[8] == dates[9] == utc(2026, 3, 20, 15)
    assert dates[10] == utc(2026, 3, 27, 15)


def test_open_ended_delay_gives_no_estimate_after_it():
    entry = dict(ENTRY, dubDelayedUntil="0001-01-01T00:00:00Z")
    dates = animeschedule.estimates(animeschedule.dub_schedule(entry), range(1, 11))
    assert 4 in dates and 5 not in dates and 10 not in dates


def test_fetch_picks_entry_for_requested_mal_id():
    net = FakeNet().route("animeschedule.net/api/v3/anime", FRIEREN2)
    assert animeschedule.fetch(59978)["route"] == "sousou-no-frieren-2nd-season"
    assert "mal-ids=59978" in net.calls[0][1]
    assert animeschedule.fetch(12345) is None  # answer is for another show


# -- catalog --------------------------------------------------------------------

@pytest.fixture
def cat(tmp_path, monkeypatch):
    # 20 Feb 2026: episodes 1-2 dubbed, 3+ still to come.
    now = utc(2026, 2, 20, 12).timestamp()
    monkeypatch.setattr(catalog, "_clock", lambda: now)
    return catalog.Catalog(str(tmp_path))


def frieren2():
    from resources.lib.models import Show
    return Show(anilist_id=182255, title="Frieren S2", mal_id=59978, format="TV",
                status="RELEASING", start_date="2026-01-16", next_episode=7)


def test_hints_only_for_episodes_not_yet_dubbed(cat):
    FakeNet().route("animeschedule.net", FRIEREN2)
    hints = cat.dub_estimates(frieren2(), range(1, 7))
    assert sorted(hints) == [3, 4, 5, 6]
    assert hints[3] == utc(2026, 2, 20, 15).timestamp()


def test_schedule_cached_per_show(cat):
    net = FakeNet().route("animeschedule.net", FRIEREN2)
    cat.dub_estimates(frieren2(), range(1, 7))
    cat.dub_estimates(frieren2(), range(1, 7))
    assert net.count("animeschedule.net") == 1


def test_failure_means_no_hint_and_is_not_retried_at_once(cat):
    net = FakeNet().route("animeschedule.net", OSError("down"))
    assert cat.dub_estimates(frieren2(), range(1, 7)) == {}
    assert cat.dub_estimates(frieren2(), range(1, 7)) == {}
    assert net.count("animeschedule.net") == 3  # first call's retries only


@pytest.mark.parametrize("change", [
    {"mal_id": None},
    {"format": "MOVIE"},
    {"status": "FINISHED", "start_date": "2023-09-29"},
])
def test_skipped_shows_make_no_request(cat, change):
    net = FakeNet()
    show = frieren2()
    for key, value in change.items():
        setattr(show, key, value)
    assert cat.dub_estimates(show, range(1, 7)) == {}
    assert net.calls == []


def test_long_running_show_still_checked(cat):
    FakeNet().route("animeschedule.net", FRIEREN2)
    show = frieren2()
    show.start_date = "1999-10-20"
    assert cat.dub_estimates(show, range(1, 7))


# -- show page ------------------------------------------------------------------

def test_show_page_marks_episodes_waiting_for_dub(cat, monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, _id: frieren2())
    FakeNet().route("animeschedule.net", FRIEREN2).route("api.ani.zip", {})
    router.dispatch(["plugin://plugin.video.novaflix/show", "1", "?id=182255"])
    items = [item for _, _, item, _ in xbmcplugin.directory_items]  # no relations: episodes only
    assert "Dub expected" not in items[1].getLabel()  # episode 2 already dubbed
    day = datetime.datetime.fromtimestamp(utc(2026, 2, 20, 15).timestamp())  # shown in local time
    expected = f"Dub expected {day:%a} {day.day} {day:%b}"
    assert items[2].getLabel().endswith(f"[COLOR grey]({expected})[/COLOR]")
    assert f"{expected} (estimate from AnimeSchedule.net)" in items[2].tag.values["Plot"]


def test_far_future_estimates_are_dropped(cat):
    # One Piece style: weekly-from-premiere gives dates decades away (past 2038 on the
    # 32-bit Fire TV, where it crashed the show page). Only the next year is shown.
    FakeNet().route("animeschedule.net", FRIEREN2)
    show = frieren2()
    hints = cat.dub_estimates(show, range(1, 3000))
    horizon = utc(2026, 2, 20, 12).timestamp() + catalog.DUB_HINT_MAX_DAYS * 86400
    assert hints and max(hints.values()) <= horizon
    assert 2999 not in hints


def test_no_hints_when_the_dub_started_over_a_year_ago(cat):
    # One Piece style (live 2026-10-11): weekly-from-premiere would mark long-dubbed
    # episodes as "Dub expected". Only dubs that started within a year are estimated.
    old = copy.deepcopy(FRIEREN2)
    old["anime"][0]["dubPremier"] = "2024-12-01T00:00:00Z"
    FakeNet().route("animeschedule.net", old)
    assert cat.dub_estimates(frieren2(), range(1, 7)) == {}

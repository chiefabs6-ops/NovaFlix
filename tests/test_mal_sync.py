"""M13: what AniVerse sends to MyAnimeList, the queue and the service's sender."""

from urllib.parse import parse_qs

import pytest
import xbmcgui
from helpers import FakeNet, mal_login

from resources.lib import errors, router
from resources.lib.kodi import paths
from resources.lib.metadata import catalog
from resources.lib.models import Episode, Show
from resources.lib.myanimelist import api, auth, rules, sync
from resources.lib.storage.cache import Cache
from resources.lib.storage.history import History

BASE = "plugin://plugin.video.aniverse/"
NOW = 1_800_000_000.0
ENTRY = {"id": 52991, "title": "Sousou no Frieren", "num_episodes": 28, "status": "finished_airing",
         "my_list_status": {"status": "watching", "num_episodes_watched": 7, "score": 8}}


def entry(status="watching", watched=7, total=28, airing="finished_airing"):
    return {"title": "Frieren", "num_episodes": total, "airing": airing, "list_status": status,
            "watched": watched, "score": 0}


@pytest.mark.parametrize("kind,episode,current,expected", [
    ("watched", 8, entry(), ("watching", 8)),
    ("watched", 3, entry(), None),                                   # behind MAL: nothing to send
    ("watched", 28, entry(), ("completed", 28)),
    ("watched", 12, entry(total=0, airing="currently_airing"), ("watching", 12)),
    ("watched", 12, entry(watched=11, total=12, airing="currently_airing"), ("watching", 12)),
    ("watched", 1, entry(status=None, watched=0), ("watching", 1)),   # not on the list: added
    ("watched", 2, entry(status="completed", watched=28), None),       # rewatch keeps completed
    ("watched", 5, entry(status="plan_to_watch", watched=0), ("watching", 5)),
    ("unwatched", 5, entry(), ("watching", 4)),
    ("unwatched", 7, entry(), ("watching", 6)),
    ("unwatched", 9, entry(), None),                                 # above MAL's count
    ("unwatched", 3, entry(status=None, watched=0), None),
    ("show_watched", 28, entry(), ("completed", 28)),
    ("show_watched", 10, entry(watched=4, total=0, airing="currently_airing"), ("watching", 10)),
    ("show_unwatched", 0, entry(), ("watching", 0)),
    ("show_unwatched", 0, entry(status=None, watched=0), None),
])
def test_rules(kind, episode, current, expected):
    assert rules.plan(kind, episode, current) == expected


@pytest.fixture
def mal(monkeypatch):
    mal_login()
    monkeypatch.setattr(sync, "_spawn", lambda fn: fn())
    clock = [NOW]
    monkeypatch.setattr(sync, "_clock", lambda: clock[0])
    return clock


def directory():
    return paths.profile_dir()


def pending():
    return [(m, k, e) for m, k, e, _ in sync.pending(directory())]


def form(body):
    return {k: v[0] for k, v in parse_qs(body).items()}


def messages():
    return [n[1] for n in xbmcgui.notifications]


def test_not_logged_in_nothing_is_queued():
    assert sync.queue(directory(), 52991, "watched", 8) is False
    assert pending() == []


def test_missing_mal_id_is_ignored(mal):
    assert sync.queue(directory(), None, "watched", 1) is False and pending() == []


def test_queue_replaces_older_change_and_wakes_the_service(mal):
    sync.queue(directory(), 52991, "watched", 8)
    mal[0] += 1
    sync.queue(directory(), 52991, "unwatched", 3)
    assert pending() == [(52991, "unwatched", 3)]
    assert xbmcgui.window_properties[sync.KICK_PROPERTY] == "1"


def test_queue_updates_a_cached_entry_at_once(mal):
    Cache(directory()).set(sync.entry_key(52991), entry(), 600)
    sync.queue(directory(), 52991, "unwatched", 5)
    assert Cache(directory()).get(sync.entry_key(52991))["watched"] == 4


def test_drain_reads_then_puts_and_announces(mal):
    sync.queue(directory(), 52991, "watched", 8)
    Cache(directory()).set(sync.entry_key(52991), entry(), 600)
    net = FakeNet().route("52991/my_list_status", {}).route("anime/52991?", ENTRY)
    sync.drain(directory())
    assert [c[0] for c in net.calls] == ["GET", "PUT"]
    assert form(net.calls[1][2]) == {"status": "watching", "num_watched_episodes": "8"}
    assert pending() == [] and xbmcgui.notifications[-1][:2] == ("MyAnimeList", "Sousou no Frieren → Ep 8")
    assert Cache(directory()).get(sync.entry_key(52991)) is None


def test_last_episode_completes_the_show(mal):
    sync.queue(directory(), 52991, "watched", 28)
    net = FakeNet().route("52991/my_list_status", {}).route("anime/52991?", ENTRY)
    sync.drain(directory())
    assert form(net.calls[1][2]) == {"status": "completed", "num_watched_episodes": "28"}
    assert messages()[-1] == "Sousou no Frieren → Completed"


def test_no_change_sends_nothing(mal):
    sync.queue(directory(), 52991, "watched", 3)
    net = FakeNet().route("anime/52991?", ENTRY)
    sync.drain(directory())
    assert [c[0] for c in net.calls] == ["GET"] and pending() == [] and messages() == []


def test_outage_keeps_the_queue_and_warns_once_per_outage(mal):
    sync.queue(directory(), 52991, "watched", 8)
    FakeNet().route("anime/52991?", errors.NetworkError("down"))
    sync.drain(directory())
    sync.drain(directory())
    assert pending() == [(52991, "watched", 8)]
    assert messages() == ["MyAnimeList unreachable — updates will be sent later."]
    FakeNet().route("52991/my_list_status", {}).route("anime/52991?", ENTRY)
    sync.drain(directory())
    assert pending() == []
    mal[0] += 1
    sync.queue(directory(), 52991, "watched", 9)
    FakeNet().route("anime/52991?", errors.NetworkError("down"))
    sync.drain(directory())
    assert messages().count("MyAnimeList unreachable — updates will be sent later.") == 2


def test_expired_login_keeps_the_queue_and_warns_once_a_day(mal):
    sync.queue(directory(), 52991, "watched", 8)
    auth.expire(auth.MalStore(directory()))
    assert sync.queue(directory(), 52991, "watched", 9) is True   # still linked: kept for the next login
    FakeNet()
    sync.drain(directory())
    sync.drain(directory())
    assert pending() == [(52991, "watched", 9)]
    assert messages() == ["MyAnimeList login expired — log in again in Settings."]
    mal[0] += 86400
    sync.drain(directory())
    assert len(messages()) == 2


def test_refused_change_is_dropped_not_retried_forever(mal):
    sync.queue(directory(), 52991, "watched", 8)
    FakeNet().route("anime/52991?", {"error": "not_found"}, status=404)
    sync.drain(directory())
    assert pending() == []


def test_change_queued_during_send_is_kept(mal, monkeypatch):
    sync.queue(directory(), 52991, "watched", 8)
    FakeNet().route("anime/52991?", ENTRY)
    sent = []

    def update(self, mal_id, status, watched):
        sent.append(watched)
        if len(sent) == 1:  # the owner finishes the next episode while this change is on its way
            mal[0] += 1
            sync.queue(directory(), 52991, "watched", 9)

    monkeypatch.setattr(api.MalApi, "update", update)
    sync.drain(directory())
    assert sent == [8, 9] and pending() == []


def test_start_drain_only_with_waiting_changes(mal, monkeypatch):
    ran = []
    monkeypatch.setattr(sync, "drain", lambda d: ran.append(d))
    assert sync.start_drain(directory()) is False and ran == []
    sync.queue(directory(), 52991, "watched", 8)
    assert sync.start_drain(directory()) is True and ran == [directory()]


def test_logout_clears_waiting_changes(mal):
    sync.queue(directory(), 52991, "watched", 8)
    xbmcgui.select_answers.append(1)
    router.dispatch([BASE + "mal/account", "-1", ""])
    assert pending() == []


FRIEREN = Show(anilist_id=7, title="Frieren", mal_id=52991, format="TV", status="FINISHED", episodes_total=3)


def test_queue_show_finds_the_mal_id_in_history(mal):
    History(directory()).remember_show(FRIEREN)
    assert sync.queue_show(directory(), 7, "show_watched", 3) is True
    assert pending() == [(52991, "show_watched", 3)]


def test_queue_show_without_any_mal_id_does_nothing(mal, monkeypatch):
    monkeypatch.setattr(catalog.Catalog, "cached_show", lambda self, i: None)
    assert sync.queue_show(directory(), 99, "watched", 1) is False and pending() == []


def test_classic_marks_queue_changes(mal, monkeypatch):
    History(directory()).remember_show(FRIEREN)
    router.dispatch([BASE + "history/mark", "-1", "?id=7&ep=2&watched=1"])
    assert pending() == [(52991, "watched", 2)]
    mal[0] += 1
    router.dispatch([BASE + "history/mark", "-1", "?id=7&ep=2&watched=0"])
    assert pending() == [(52991, "unwatched", 2)]
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: FRIEREN)
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=7, number=n, title=f"Ep {n}") for n in (1, 2, 3)])
    mal[0] += 1
    router.dispatch([BASE + "history/mark_show", "-1", "?id=7&watched=1"])
    assert pending() == [(52991, "show_watched", 3)]
    mal[0] += 1
    router.dispatch([BASE + "history/mark_show", "-1", "?id=7&watched=0"])  # confirm: fake default yes
    assert pending() == [(52991, "show_unwatched", 0)]

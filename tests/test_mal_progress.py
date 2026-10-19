"""M13: MyAnimeList progress shown in NovaFlix — watched marks, next episode, details line."""

import xbmc
import xbmcplugin
from helpers import FakeNet, mal_login

from resources.lib import errors, router
from resources.lib.gui import actions, cards
from resources.lib.kodi import paths, ui
from resources.lib.metadata import catalog
from resources.lib.metadata.mal import MalEntry
from resources.lib.models import Episode, Show
from resources.lib.myanimelist import progress, sync
from resources.lib.storage.cache import Cache
from resources.lib.storage.history import History

BASE = "plugin://plugin.video.novaflix/"
ENTRY = {"title": "Sousou no Frieren", "num_episodes": 28, "airing": "finished_airing",
         "list_status": "watching", "watched": 7, "score": 8}
API_ENTRY = {"id": 52991, "title": "Sousou no Frieren", "num_episodes": 28, "status": "finished_airing",
             "my_list_status": {"status": "watching", "num_episodes_watched": 7, "score": 8}}
SHOW = Show(anilist_id=1, title="Show 1", mal_id=101, format="TV", status="FINISHED", episodes_total=3)


def api_entry(watched, total=3):
    return {"id": 101, "title": "Show 1", "num_episodes": total, "status": "finished_airing",
            "my_list_status": {"status": "watching", "num_episodes_watched": watched}}


def test_merge_states_marks_mal_count_watched_and_keeps_local_progress():
    states = {2: (500.0, 1440.0, False), 9: (300.0, 1440.0, False)}
    merged = progress.merge_states(states, dict(ENTRY, watched=3))
    assert merged[1] == (0.0, 0.0, True) and merged[2] == (0.0, 1440.0, True) and merged[3] == (0.0, 0.0, True)
    assert merged[9] == (300.0, 1440.0, False) and 4 not in merged
    assert states[2] == (500.0, 1440.0, False)  # local history untouched
    assert progress.merge_states(states, None) is states


def test_next_episode_after_mal_progress():
    assert cards.next_episode(list(range(1, 29)), progress.merge_states({}, ENTRY)) == (8, 0)


def test_mal_ahead_of_novaflix_episode_list_starts_over_without_extra_episodes():
    merged = progress.merge_states({}, dict(ENTRY, watched=30))
    assert cards.next_episode([1, 2, 3], merged) == (1, 0)


def test_mal_line():
    assert progress.mal_line(ENTRY, ui.string) == "MAL: Watching · 7/28 · ★ 8"
    assert progress.mal_line(dict(ENTRY, score=0, num_episodes=0), ui.string) == "MAL: Watching · 7/?"
    assert progress.mal_line(dict(ENTRY, list_status=None), ui.string) == ""
    assert progress.mal_line(None, ui.string) == ""


def test_apply_a_local_change():
    assert progress.apply(ENTRY, "unwatched", 5)["watched"] == 4
    assert progress.apply(ENTRY, "watched", 3) == ENTRY
    assert progress.apply(None, "watched", 1) is None


def test_show_entry_is_cached_for_10_minutes():
    mal_login()
    net = FakeNet().route("anime/52991?", API_ENTRY)
    assert progress.show_entry(52991) == ENTRY
    assert progress.show_entry(52991) == ENTRY and net.count("anime/52991") == 1


def test_show_entry_without_login_or_on_failure_is_none():
    FakeNet()
    assert progress.show_entry(52991) is None
    mal_login()
    assert progress.show_entry(None) is None
    FakeNet().route("anime/52991?", errors.NetworkError("down"))
    assert progress.show_entry(52991) is None


def test_classic_show_page_ticks_mal_progress(monkeypatch):
    mal_login()
    monkeypatch.setattr(catalog.Catalog, "show", lambda self, i: SHOW)
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=1, number=n, title=f"Ep {n}") for n in (1, 2, 3)])
    monkeypatch.setattr(catalog.Catalog, "fanart", lambda self, s: None)
    monkeypatch.setattr(catalog.Catalog, "dub_estimates", lambda self, s, n: {})
    FakeNet().route("anime/101?", api_entry(2))
    router.dispatch([BASE + "show", "1", "?id=1"])
    plays = [item.getVideoInfoTag().values["Playcount"] for _, _, item, _ in xbmcplugin.directory_items]
    assert plays == [1, 1, 0]


def test_play_next_uses_saved_mal_progress(monkeypatch):
    mal_login()
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=1, number=n) for n in (1, 2, 3)])
    Cache(paths.profile_dir()).set(sync.entry_key(101), dict(ENTRY, num_episodes=3, watched=2), 600)
    FakeNet()  # Play Now never waits for MAL
    actions.play_next(SHOW)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=1&ep=3)"


LIST = {"data": [{"node": {"id": 52991, "title": "Sousou no Frieren"},
                  "list_status": {"status": "watching", "num_episodes_watched": 4,
                                  "updated_at": "2026-10-10T20:00:00+00:00"}}], "paging": {}}


def local(anilist_id, episode, watched, updated_at, position=0.0, total=12):
    return {"anilist_id": anilist_id, "title": f"Show {anilist_id}", "poster": f"p{anilist_id}.jpg",
            "mal_id": 100 + anilist_id, "episode": episode, "position_s": position,
            "duration_s": 1440.0 if position else 0.0, "watched": watched, "episodes_total": total,
            "updated_at": updated_at}


def mal_entry(mal_id, watched, updated_at):
    return MalEntry(mal_id=mal_id, title=f"MAL {mal_id}", picture=None, watched=watched, status="watching",
                    updated_at=updated_at)


def show(anilist_id, total=12):
    return Show(anilist_id=anilist_id, title=f"Show {anilist_id}", poster=f"p{anilist_id}.jpg",
                mal_id=100 + anilist_id, episodes_total=total)


def test_merge_adds_mal_only_shows_and_orders_by_latest_activity():
    rows = progress.merge_continue([local(1, 3, False, 100.0, position=500.0)],
                                   [mal_entry(102, 4, 200.0)], {102: show(2)})
    assert [(r["anilist_id"], r["episode"], r["watched"]) for r in rows] == [(2, 4, True), (1, 3, False)]
    assert rows[0]["title"] == "Show 2" and rows[0]["position_s"] == 0.0


def test_further_progress_wins_one_card_per_show():
    rows = progress.merge_continue([local(1, 3, False, 300.0, position=500.0)],
                                   [mal_entry(101, 6, 100.0)], {101: show(1)})
    assert len(rows) == 1 and (rows[0]["episode"], rows[0]["watched"], rows[0]["updated_at"]) == (6, True, 300.0)
    rows = progress.merge_continue([local(1, 8, True, 100.0)], [mal_entry(101, 6, 300.0)], {101: show(1)})
    assert len(rows) == 1 and (rows[0]["episode"], rows[0]["watched"], rows[0]["updated_at"]) == (8, True, 300.0)


def test_started_episode_beats_an_equal_mal_count():
    # NovaFlix: ep 3 half-watched (2 done). MAL: 2 watched. Keep the resume card.
    rows = progress.merge_continue([local(1, 3, False, 100.0, position=500.0)],
                                   [mal_entry(101, 2, 200.0)], {101: show(1)})
    assert (rows[0]["episode"], rows[0]["position_s"]) == (3, 500.0)


def test_mal_entries_without_anilist_match_are_skipped():
    assert progress.merge_continue([], [mal_entry(999, 3, 1.0)], {}) == []


def remember_local_show():
    hist = History(paths.profile_dir())
    hist.remember_show(show(5))
    hist.save_position(5, 2, 105, 600, 1440)


def test_continue_rows_local_only_uses_cached_mal_data(monkeypatch):
    mal_login()
    remember_local_show()
    FakeNet()  # any network call fails the test
    assert [r["anilist_id"] for r in progress.continue_rows(network=False)] == [5]
    Cache(paths.profile_dir()).set(sync.WATCHING_KEY, [mal_entry(102, 4, 9e9).__dict__], 1800)
    seen = []
    monkeypatch.setattr(catalog.Catalog, "by_mal_ids",
                        lambda self, ids, network=True: seen.append(network) or {102: show(2)})
    assert [r["anilist_id"] for r in progress.continue_rows(network=False)] == [2, 5]
    assert seen == [False]


def test_continue_rows_fetch_the_watching_list_once_and_survive_mal_failure(monkeypatch):
    mal_login()
    remember_local_show()
    monkeypatch.setattr(catalog.Catalog, "by_mal_ids", lambda self, ids, network=True: {52991: show(2)})
    net = FakeNet().route("users/@me/animelist", LIST)
    assert sorted(r["anilist_id"] for r in progress.continue_rows()) == [2, 5]
    progress.continue_rows()
    assert net.count("users/@me/animelist") == 1
    Cache(paths.profile_dir()).delete(sync.WATCHING_KEY)
    FakeNet().route("users/@me/animelist", errors.NetworkError("down"))
    assert [r["anilist_id"] for r in progress.continue_rows()] == [5]


def test_continue_rows_without_login_never_call_mal():
    remember_local_show()
    FakeNet()
    assert [r["anilist_id"] for r in progress.continue_rows()] == [5]


def test_classic_continue_watching_includes_mal_shows(monkeypatch):
    monkeypatch.setattr(progress, "continue_rows", lambda network=True: [local(2, 4, True, 1.0)])
    router.dispatch([BASE + "continue", "1", ""])
    assert [item.getLabel() for _, _, item, _ in xbmcplugin.directory_items] == ["Show 2 — Next: Episode 5"]


def test_failed_entry_is_not_retried_for_a_minute():
    mal_login()
    net = FakeNet().route("anime/52991?", errors.NetworkError("down"))
    assert progress.show_entry(52991) is None
    assert progress.show_entry(52991) is None
    assert net.count("anime/52991") == 1


def test_cached_only_entry_never_calls_mal():
    mal_login()
    FakeNet()  # any network call fails the test
    assert progress.show_entry(52991, network=False) is None


def test_play_now_never_waits_for_mal(monkeypatch):
    mal_login()
    monkeypatch.setattr(catalog.Catalog, "episodes",
                        lambda self, s: [Episode(anilist_id=1, number=n) for n in (1, 2, 3)])
    FakeNet()  # MAL unreachable: any request fails the test
    actions.play_next(SHOW)
    assert xbmc.builtins_executed[-1] == "PlayMedia(plugin://plugin.video.novaflix/play?id=1&ep=1)"

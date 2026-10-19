"""Watch history for TMDB movies and episodes (Plan 3, Task 5; user.db v5)."""

import os

from helpers import fixture
from resources.lib import media
from resources.lib.kodi import paths
from resources.lib.models import Candidate
from resources.lib.storage import db, migrations, watching
from resources.lib.storage.watching import WatchHistory


def history():
    return WatchHistory(paths.profile_dir())


def test_position_saved_with_resume_point():
    h = history()
    assert h.save_position("tv", 1396, 2, 3, 600, 2800) is False
    assert h.states("tv", 1396) == {(2, 3): (600, 2800, False)}


def test_watched_at_90_percent_clears_resume():
    h = history()
    assert h.save_position("tv", 1396, 2, 3, 2600, 2800) is True
    assert h.states("tv", 1396)[(2, 3)] == (0, 2800, True)


def test_short_position_is_not_a_resume_point():
    h = history()
    h.save_position("movie", 438631, 0, 0, 30, 9000)
    assert h.states("movie", 438631) == {(0, 0): (0, 9000, False)}  # movies live at season 0, episode 0


def test_rewatch_never_unmarks():
    h = history()
    h.save_position("tv", 1396, 2, 3, 2600, 2800)
    h.save_position("tv", 1396, 2, 3, 300, 2800)
    assert h.states("tv", 1396)[(2, 3)][2] is True


def test_manual_mark_clears_resume():
    h = history()
    h.save_position("tv", 1396, 2, 3, 600, 2800)
    h.mark("tv", 1396, 2, 3, True)
    assert h.states("tv", 1396)[(2, 3)] == (0, 2800, True)


def test_continue_watching_latest_row_per_title(monkeypatch):
    clock = iter([100.0, 200.0, 300.0, 400.0, 500.0, 600.0])
    monkeypatch.setattr(watching, "_clock", lambda: next(clock))
    h = history()
    h.remember_title(media.title_from(fixture("tmdb/tv_1396.json"), media.TV))
    h.remember_title(media.title_from(fixture("tmdb/movie_438631.json"), media.MOVIE))
    h.save_position("tv", 1396, 2, 2, 600, 2800)
    h.save_position("movie", 438631, 0, 0, 900, 9000)
    h.save_position("tv", 1396, 2, 3, 700, 2800)
    rows = h.continue_watching()
    assert [(r["media_type"], r["tmdb_id"], r["season"], r["episode"]) for r in rows] == [
        ("tv", 1396, 2, 3), ("movie", 438631, 0, 0)]
    assert rows[0]["title"] == "Breaking Bad" and rows[0]["poster"] and rows[0]["year"] == 2008


def test_untitled_rows_are_left_out():
    h = history()
    h.save_position("tv", 5, 1, 1, 600, 2800)  # no remember_title: nothing to show on a card
    assert h.continue_watching() == []


def test_remember_and_last_choice():
    h = history()
    assert h.last_choice("tv", 1396) == (None, None)
    h.remember_title(media.title_from(fixture("tmdb/tv_1396.json"), media.TV))
    h.remember_choice("tv", 1396, Candidate(origin="torrentio", release_name="x", release_group="NTb",
                                            resolution="1080p"))
    assert h.last_choice("tv", 1396) == ("NTb", "1080p")
    h.remember_title(media.title_from(fixture("tmdb/tv_1396.json"), media.TV))  # refresh keeps the choice
    assert h.last_choice("tv", 1396) == ("NTb", "1080p")


def test_v4_database_upgrades_in_place():
    path = os.path.join(paths.profile_dir(), db.USER_DB)
    conn = db.connect(path)
    db._migrate(conn, migrations.USER_MIGRATIONS[:4])
    conn.execute("INSERT INTO history (anilist_id, episode, position_s, duration_s, watched, updated_at) "
                 "VALUES (154587, 3, 100, 1400, 0, 1)")
    conn.close()
    assert history().states("tv", 1396) == {}
    conn = db.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        assert conn.execute("SELECT anilist_id, episode FROM history").fetchall() == [(154587, 3)]
        assert conn.execute("SELECT COUNT(*) FROM watch_history").fetchone()[0] == 0
    finally:
        conn.close()


def test_mark_many_in_one_go():
    h = history()
    h.save_position("tv", 1396, 1, 2, 600, 2800)
    h.mark_many("tv", 1396, [(1, 1), (1, 2), (2, 1)])
    assert {k: v[2] for k, v in h.states("tv", 1396).items()} == {(1, 1): True, (1, 2): True, (2, 1): True}
    assert h.states("tv", 1396)[(1, 2)][0] == 0

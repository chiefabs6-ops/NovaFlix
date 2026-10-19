import os
import sqlite3

import pytest

from resources.lib import errors
from resources.lib.storage import cache, db, migrations

USER_TABLES = {"history", "show_prefs", "favourites", "search_history", "added_torrents"}


def table_names(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_user_db_is_created_with_all_tables(tmp_path):
    conn = db.open_user_db(str(tmp_path))
    assert USER_TABLES <= table_names(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(migrations.USER_MIGRATIONS)


def test_user_db_uses_wal_and_normal_sync(tmp_path):
    conn = db.open_user_db(str(tmp_path))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL


def test_reopening_keeps_data(tmp_path):
    conn = db.open_user_db(str(tmp_path))
    conn.execute("INSERT INTO favourites (anilist_id, title, poster, added_at) VALUES (1, 'A', '', 0)")
    conn.commit()
    conn.close()
    conn = db.open_user_db(str(tmp_path))
    assert conn.execute("SELECT COUNT(*) FROM favourites").fetchone()[0] == 1


def test_migrations_apply_in_order_from_older_version(tmp_path, monkeypatch):
    path = os.path.join(str(tmp_path), "user.db")
    first = migrations.USER_MIGRATIONS[:1]
    monkeypatch.setattr(migrations, "USER_MIGRATIONS", first)
    db.open_user_db(str(tmp_path)).close()
    monkeypatch.setattr(migrations, "USER_MIGRATIONS", first + ["CREATE TABLE extra (x INTEGER);"])
    conn = db.open_user_db(str(tmp_path))
    assert "extra" in table_names(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert os.path.exists(path)


def test_newer_schema_is_refused_and_left_untouched(tmp_path):
    conn = db.open_user_db(str(tmp_path))
    conn.execute(f"PRAGMA user_version = {len(migrations.USER_MIGRATIONS) + 5}")
    conn.commit()
    conn.close()
    with pytest.raises(errors.SchemaTooNew):
        db.open_user_db(str(tmp_path))
    raw = sqlite3.connect(os.path.join(str(tmp_path), "user.db"))
    assert raw.execute("PRAGMA user_version").fetchone()[0] == len(migrations.USER_MIGRATIONS) + 5


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(migrations, "USER_MIGRATIONS", ["CREATE TABLE a (x INTEGER);", "CREATE TABLE b (; broken"])
    with pytest.raises(sqlite3.Error):
        db.open_user_db(str(tmp_path))
    conn = sqlite3.connect(os.path.join(str(tmp_path), "user.db"))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert "b" not in table_names(conn)


class Clock:
    now = 1000.0


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "_clock", lambda: Clock.now)
    Clock.now = 1000.0
    return cache.Cache(str(tmp_path))


def test_cache_round_trip_json(store):
    store.set("k", {"a": [1, 2]}, ttl=60)
    assert store.get("k") == {"a": [1, 2]}


def test_cache_miss_returns_default(store):
    assert store.get("missing") is None
    assert store.get("missing", default=[]) == []


def test_cache_entry_expires(store):
    store.set("k", 1, ttl=60)
    Clock.now += 61
    assert store.get("k") is None


def test_cache_purge_removes_only_expired(store):
    store.set("old", 1, ttl=10)
    store.set("new", 2, ttl=1000)
    Clock.now += 11
    assert store.purge_expired() == 1
    assert store.get("new") == 2


def test_clear_cache_leaves_user_db(tmp_path, store):
    conn = db.open_user_db(str(tmp_path))
    conn.execute("INSERT INTO history (anilist_id, episode, position_s, duration_s, watched, updated_at) VALUES (1, 1, 10, 100, 0, 0)")
    conn.commit()
    store.set("k", 1, ttl=60)
    store.clear()
    assert store.get("k") is None
    assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1


def test_corrupt_cache_file_is_recreated(tmp_path):
    with open(os.path.join(str(tmp_path), "cache.db"), "wb") as f:
        f.write(b"this is not a database" * 100)
    store = cache.Cache(str(tmp_path))
    store.set("k", 1, ttl=60)
    assert store.get("k") == 1

"""SQLite connections for user.db (never auto-wiped; DEC-005, DEC-034)."""

import os
import sqlite3

from resources.lib import errors
from resources.lib.storage import migrations

USER_DB = "user.db"


def connect(path):
    # The plugin and the service may write at the same time.
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn, steps):
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > len(steps):
        raise errors.SchemaTooNew(f"user.db schema v{current} is newer than this NovaFlix (v{len(steps)})")
    for version in range(current, len(steps)):
        # executescript would auto-commit; run statements one by one in a transaction.
        conn.execute("BEGIN")
        try:
            for statement in steps[version].split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version + 1}")
            conn.execute("COMMIT")
        except sqlite3.Error:
            conn.execute("ROLLBACK")
            raise


def open_user_db(directory):
    conn = connect(os.path.join(directory, USER_DB))
    try:
        _migrate(conn, migrations.USER_MIGRATIONS)
    except Exception:
        conn.close()
        raise
    return conn

"""Forward-only schema migrations for user.db.

Index i holds the SQL that takes the schema from version i to i+1; the
version is stored in PRAGMA user_version. Never edit a released entry —
append a new one.
"""

USER_MIGRATIONS = [
    # v1 — AniVerse 0.2.0
    """
    CREATE TABLE history (
        anilist_id  INTEGER NOT NULL,
        episode     INTEGER NOT NULL,
        mal_id      INTEGER,
        position_s  REAL    NOT NULL DEFAULT 0,
        duration_s  REAL    NOT NULL DEFAULT 0,
        watched     INTEGER NOT NULL DEFAULT 0,
        updated_at  REAL    NOT NULL,
        PRIMARY KEY (anilist_id, episode)
    );
    CREATE INDEX history_updated ON history (updated_at);

    CREATE TABLE show_prefs (
        anilist_id          INTEGER PRIMARY KEY,
        last_release_group  TEXT,
        last_resolution     TEXT,
        last_episode_played INTEGER,
        updated_at          REAL NOT NULL
    );

    CREATE TABLE favourites (
        anilist_id INTEGER PRIMARY KEY,
        title      TEXT NOT NULL,
        poster     TEXT,
        added_at   REAL NOT NULL
    );

    CREATE TABLE search_history (
        query   TEXT PRIMARY KEY,
        used_at REAL NOT NULL
    );

    CREATE TABLE added_torrents (
        rd_torrent_id TEXT PRIMARY KEY,
        info_hash     TEXT,
        added_at      REAL NOT NULL,
        keep          INTEGER NOT NULL DEFAULT 0
    );
    """,
    # v2 — AniVerse 0.4.0: favourites remember the MAL ID for DUB badges
    """
    ALTER TABLE favourites ADD COLUMN mal_id INTEGER;
    """,
    # v3 — AniVerse 0.9.0: Continue Watching lists shows without a network call
    """
    ALTER TABLE show_prefs ADD COLUMN title TEXT;
    ALTER TABLE show_prefs ADD COLUMN poster TEXT;
    ALTER TABLE show_prefs ADD COLUMN mal_id INTEGER;
    ALTER TABLE show_prefs ADD COLUMN episodes_total INTEGER;
    """,
    # v4 — AniVerse 1.2.0: MyAnimeList changes waiting to be sent (M13)
    """
    CREATE TABLE mal_pending (
        mal_id     INTEGER PRIMARY KEY,
        kind       TEXT    NOT NULL,
        episode    INTEGER NOT NULL DEFAULT 0,
        queued_at  REAL    NOT NULL
    );
    """,
]

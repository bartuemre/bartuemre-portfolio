import sqlite3
from contextlib import closing
from pathlib import Path

CURRENT_SCHEMA_VERSION = 10


def initialize(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone():
            version = connection.execute("SELECT max(version) FROM schema_version").fetchone()[0]
            if version is not None and version > CURRENT_SCHEMA_VERSION:
                raise ValueError(
                    "Database schema is newer than this IPRV version; use a compatible release"
                )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_version VALUES (1);
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                ruleset_version TEXT NOT NULL,
                unique_count INTEGER NOT NULL,
                occurrence_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, context TEXT NOT NULL,
                active_version TEXT, last_error TEXT
            );
            CREATE TABLE IF NOT EXISTS feed_versions (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                version TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, checksum TEXT NOT NULL,
                indicator_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS indicators (
                version_id TEXT NOT NULL, indicator TEXT NOT NULL,
                family INTEGER NOT NULL, prefix INTEGER NOT NULL,
                network TEXT NOT NULL,
                PRIMARY KEY(version_id, indicator)
            );
            CREATE INDEX IF NOT EXISTS feed_version_history
                ON feed_versions(source_id, retrieved_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS indicator_prefix_lookup
                ON indicators(version_id, family, prefix, network);
            INSERT OR IGNORE INTO schema_version VALUES (2);
            CREATE TABLE IF NOT EXISTS feed_evidence (
                version_id TEXT NOT NULL, indicator TEXT NOT NULL,
                strength TEXT NOT NULL, last_seen TEXT, reference TEXT,
                lineage TEXT NOT NULL, PRIMARY KEY(version_id, indicator)
            );
            CREATE TABLE IF NOT EXISTS analysis_results (
                id TEXT PRIMARY KEY, indicator TEXT NOT NULL,
                analyzed_at TEXT NOT NULL, ruleset_version TEXT NOT NULL,
                snapshot TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS result_history
                ON analysis_results(indicator, analyzed_at);
            CREATE INDEX IF NOT EXISTS result_history_cursor
                ON analysis_results(indicator, analyzed_at DESC, id DESC);
            INSERT OR IGNORE INTO schema_version VALUES (3);
            CREATE TABLE IF NOT EXISTS job_reports (
                job_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL
            );
            INSERT OR IGNORE INTO schema_version VALUES (4);
            CREATE TABLE IF NOT EXISTS reputation_cache (
                provider TEXT NOT NULL, indicator TEXT NOT NULL,
                retrieved_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(provider, indicator)
            );
            INSERT OR IGNORE INTO schema_version VALUES (5);
            CREATE TABLE IF NOT EXISTS feed_sync_state (
                source_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL,
                next_check_at TEXT NOT NULL, status TEXT NOT NULL, error TEXT
            );
            INSERT OR IGNORE INTO schema_version VALUES (6);
            CREATE TABLE IF NOT EXISTS batch_runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, mode TEXT NOT NULL,
                status TEXT NOT NULL, total INTEGER NOT NULL, completed INTEGER NOT NULL,
                error TEXT, report_id TEXT
            );
            INSERT OR IGNORE INTO schema_version VALUES (7);
            CREATE INDEX IF NOT EXISTS indicator_network_range
                ON indicators(version_id, family, network, prefix);
            INSERT OR IGNORE INTO schema_version VALUES (8);
            CREATE TABLE IF NOT EXISTS source_settings (
                source_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS source_lineage (
                child TEXT PRIMARY KEY, parent TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO schema_version VALUES (9);
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(feed_evidence)")}
        if "first_seen" not in columns:
            connection.execute("ALTER TABLE feed_evidence ADD COLUMN first_seen TEXT")
        connection.execute(
            "INSERT OR IGNORE INTO schema_version VALUES (?)", (CURRENT_SCHEMA_VERSION,)
        )

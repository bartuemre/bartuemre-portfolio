"""Read-only diagnostics and SQLite's online backup API."""

import sqlite3
from contextlib import closing
from pathlib import Path

from iprv.database import CURRENT_SCHEMA_VERSION


def database_check(path: str):
    source = Path(path).resolve()
    if not source.is_file():
        return {
            "database_exists": False,
            "integrity": "NOT_INITIALIZED",
            "schema_version": None,
            "schema_supported": True,
        }
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as connection:
        integrity = connection.execute("PRAGMA quick_check").fetchall()
        schema = connection.execute("SELECT max(version) FROM schema_version").fetchone()[0]
    return {
        "database_exists": True,
        "integrity": "ok" if integrity == [("ok",)] else "FAILED",
        "schema_version": schema,
        "schema_supported": schema is not None and schema <= CURRENT_SCHEMA_VERSION,
    }


def backup_database(path: str, destination: str):
    source, target = Path(path).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Source database does not exist")
    if target == source:
        raise ValueError("Backup destination must differ from the source database")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids overwriting an existing backup or following a symlink.
    try:
        with target.open("xb"):
            pass
    except FileExistsError as exc:
        raise ValueError("Backup destination already exists; choose a new filename") from exc
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as live:
            with closing(sqlite3.connect(target)) as backup:
                live.backup(backup, pages=256)
                if backup.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup integrity check failed")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"backup": str(target), "bytes": target.stat().st_size, "integrity": "ok"}

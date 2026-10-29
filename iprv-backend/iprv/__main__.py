"""Local management commands: python -m iprv --help."""

import argparse
import asyncio
import json
from pathlib import Path

from iprv import __version__
from iprv.database import initialize
from iprv.intelligence import SourceManager
from iprv.maintenance import backup_database, database_check
from iprv.settings import Settings
from iprv.sync import FeedSync


def main():
    parser = argparse.ArgumentParser(description="IPRV local management")
    parser.add_argument("--version", action="version", version=f"IPRV {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start the local API and dashboard")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("init", help="Initialize the SQLite database")
    sub.add_parser(
        "doctor",
        help="Inspect database integrity and runtime readiness without querying external APIs",
    )
    backup = sub.add_parser("backup", help="Create a consistent backup of the live SQLite database")
    backup.add_argument(
        "destination", help="New .sqlite3 file; existing files are never overwritten"
    )
    sync = sub.add_parser("sync", help="Download a trusted catalog feed")
    sync.add_argument("source", choices=["misp-public-dns", "feodo-tracker", "all"])
    sync.add_argument(
        "--allow-download", action="store_true", help="Explicitly permit feed downloads"
    )
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("iprv.main:app", host="127.0.0.1", port=args.port, workers=1)
        return
    settings = Settings.load()
    path = settings.database
    if args.command == "doctor":
        try:
            report = database_check(path)
        except Exception:
            report = {
                "database_exists": True,
                "integrity": "FAILED",
                "schema_version": None,
                "schema_supported": False,
            }
        report.update(
            frontend_built=(Path(__file__).parent / "static" / "index.html").is_file(),
            external_enabled=settings.allow_external,
            feed_downloads_enabled=settings.allow_feed_downloads,
            abuseipdb_configured=bool(settings.abuseipdb_key),
            threatfox_configured=bool(settings.threatfox_key),
        )
        print(json.dumps(report, indent=2))
        if report["integrity"] == "FAILED" or not report["schema_supported"]:
            raise SystemExit(1)
        return
    if args.command == "backup":
        try:
            print(json.dumps(backup_database(path, args.destination), indent=2))
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        return
    initialize(path)
    if args.command == "init":
        print(f"Database initialized: {Path(path).resolve()}")
    else:
        manager = SourceManager(path)
        service = FeedSync(manager, enabled=settings.allow_feed_downloads)

        async def run():
            failed = False
            for source in (
                ["misp-public-dns", "feodo-tracker"] if args.source == "all" else [args.source]
            ):
                result = await service.sync(source, args.allow_download)
                print(json.dumps(result))
                failed = failed or result["status"] == "FAILED"
            return failed

        try:
            if asyncio.run(run()):
                raise SystemExit(1)
        except PermissionError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()

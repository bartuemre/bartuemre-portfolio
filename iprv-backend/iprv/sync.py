"""Bounded downloads from a fixed feed catalog, with optional periodic refresh."""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

import httpx


@dataclass(frozen=True)
class Feed:
    id: str
    name: str
    url: str
    kind: str
    context: str
    format: str
    interval_hours: int


CATALOG = {
    "misp-public-dns": Feed(
        "misp-public-dns",
        "MISP · Public DNS IPv4",
        "https://raw.githubusercontent.com/MISP/misp-warninglists/main/lists/public-dns-v4/list.json",
        "warninglist",
        "PUBLIC_DNS",
        "misp",
        24,
    ),
    "feodo-tracker": Feed(
        "feodo-tracker",
        "Feodo Tracker · Botnet C2",
        "https://feodotracker.abuse.ch/downloads/ipblocklist.txt",
        "ioc",
        "UNCLASSIFIED",
        "lines",
        6,
    ),
}


class FeedSync:
    def __init__(self, manager, enabled=False, transport=None):
        self.manager = manager
        self.enabled = enabled
        self.transport = transport
        self.lock = asyncio.Lock()

    def catalog(self):
        with self.manager.connect() as connection:
            states = {
                row["source_id"]: dict(row)
                for row in connection.execute("SELECT * FROM feed_sync_state")
            }
        return [{**asdict(feed), "sync": states.get(feed.id)} for feed in CATALOG.values()]

    async def sync(self, source_id, allow_download=False):
        if source_id not in CATALOG:
            raise ValueError("Unknown catalog feed")
        if not self.enabled or not allow_download:
            raise PermissionError(
                "Feed downloads require server configuration and explicit request permission"
            )
        feed = CATALOG[source_id]
        async with self.lock:
            now = datetime.now(UTC)
            try:
                async with asyncio.timeout(35):
                    async with httpx.AsyncClient(
                        timeout=30,
                        follow_redirects=False,
                        trust_env=False,
                        transport=self.transport,
                    ) as client:
                        async with client.stream(
                            "GET",
                            feed.url,
                            headers={"Accept": "application/json, text/plain"},
                        ) as response:
                            response.raise_for_status()
                            content = bytearray()
                            async for chunk in response.aiter_bytes():
                                content.extend(chunk)
                                if len(content) > 5 * 1024 * 1024:
                                    raise ValueError("Feed exceeds 5 MiB")
                result = await asyncio.to_thread(
                    self.manager.import_feed,
                    feed.id,
                    feed.kind,
                    feed.context,
                    bytes(content),
                    feed.format,
                    feed.interval_hours,
                )
                status, error, interval = (
                    "UPDATED",
                    None,
                    timedelta(hours=feed.interval_hours),
                )
            except (httpx.HTTPError, TimeoutError, ValueError):
                # Never persist response bodies, credentials or third-party exception text.
                status, error, interval = (
                    "FAILED",
                    "Download or feed validation failed; previous version preserved",
                    timedelta(minutes=15),
                )
                result = {"source_id": source_id}
                with self.manager.connect() as connection:
                    connection.execute(
                        "UPDATE sources SET last_error=? WHERE id=?", (error, source_id)
                    )
            with self.manager.connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO feed_sync_state VALUES (?, ?, ?, ?, ?)",
                    (
                        source_id,
                        now.isoformat(),
                        (now + interval).isoformat(),
                        status,
                        error,
                    ),
                )
            return {**result, "status": status, "error": error}

    async def run(self):
        """One process only. Disabled unless server startup explicitly opts in."""
        while True:
            disabled = {source["id"] for source in self.manager.sources() if not source["enabled"]}
            for item in self.catalog():
                if item["id"] in disabled:
                    continue
                state = item["sync"]
                if state is None or state["next_check_at"] <= datetime.now(UTC).isoformat():
                    try:
                        await self.sync(item["id"], allow_download=True)
                    except Exception:
                        logging.getLogger(__name__).exception("Scheduled feed refresh failed")
            await asyncio.sleep(60)

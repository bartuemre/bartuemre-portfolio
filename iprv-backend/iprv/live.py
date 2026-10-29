"""Explicitly opted-in AbuseIPDB checks with bounded HTTP and SQLite cache."""

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta

import httpx

from iprv.intelligence import has_conflict
from iprv.json_input import strict_json_loads
from iprv.parser import normalize
from iprv.reputation import HYBRID_RULESET_VERSION, resolve, timestamp

PROVIDER = "live:abuseipdb"
ENDPOINT = "https://api.abuseipdb.com/api/v2/check"


class LiveService:
    provider = PROVIDER
    endpoint = ENDPOINT
    requires_api_key = True

    def __init__(self, reputation, api_key="", enabled=False, transport=None):
        self.reputation = reputation
        self.api_key = api_key
        self.enabled = enabled
        self.transport = transport
        self.lock = asyncio.Lock()
        self.next_request = 0.0

    @property
    def configured(self):
        return not self.requires_api_key or bool(self.api_key)

    def cached(self, indicator, now, *, include_expired=False):
        with self.reputation.manager.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reputation_cache WHERE provider=? AND indicator=?",
                (self.provider, indicator),
            ).fetchone()
        if row:
            try:
                retrieved = timestamp(row["retrieved_at"])
                expires = timestamp(row["expires_at"])
                if (
                    retrieved is None
                    or expires is None
                    or retrieved > now
                    or expires <= retrieved
                    or (not include_expired and expires <= now)
                ):
                    return None
                data = strict_json_loads(row["payload"])
                data = self.validate_cached(data, indicator)
            except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
                return None
            return data, retrieved.astimezone(UTC).isoformat(), expires.astimezone(UTC).isoformat()
        return None

    @staticmethod
    def validate_payload(body, indicator):
        data = body["data"]
        if normalize(data["ipAddress"])[0] != indicator:
            raise ValueError("Mismatched response IP")
        reports = data["totalReports"]
        score = data["abuseConfidenceScore"]
        if (
            type(reports) is not int
            or reports < 0
            or type(score) is not int
            or not 0 <= score <= 100
        ):
            raise ValueError("Invalid report counts")
        last_seen = data.get("lastReportedAt")
        if last_seen is not None:
            stamp = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp > datetime.now(UTC):
                raise ValueError("Invalid report timestamp")
            last_seen = stamp.astimezone(UTC).isoformat()
        # Store only fields used by the resolver, never keys or report comments.
        return {
            "totalReports": reports,
            "abuseConfidenceScore": score,
            "lastReportedAt": last_seen,
        }

    def validate_cached(self, data, indicator):
        return self.validate_payload({"data": {**data, "ipAddress": indicator}}, indicator)

    async def fetch(self, indicator, *, wait_for_slot=False):
        async with self.lock:
            now = datetime.now(UTC)
            cached = self.cached(indicator, now)
            if cached:
                return (*cached, "CACHE")
            remaining = self.next_request - time.monotonic()
            if remaining > 0:
                if not wait_for_slot or remaining > 1.1:
                    return None, None, None, "RATE_LIMITED"
                await asyncio.sleep(remaining)
            self.next_request = time.monotonic() + 1
            try:
                async with asyncio.timeout(25):
                    async with httpx.AsyncClient(
                        timeout=10,
                        follow_redirects=False,
                        transport=self.transport,
                        trust_env=False,
                    ) as client:
                        for attempt in range(2):
                            try:
                                method, options = self.request_options(indicator)
                                async with client.stream(
                                    method, self.endpoint, **options
                                ) as response:
                                    if response.status_code == 429:
                                        try:
                                            cooldown = max(
                                                60,
                                                min(
                                                    86400,
                                                    int(response.headers.get("Retry-After", "60")),
                                                ),
                                            )
                                        except ValueError:
                                            cooldown = 60
                                        self.next_request = time.monotonic() + cooldown
                                        return None, None, None, "RATE_LIMITED"
                                    response.raise_for_status()
                                    content = bytearray()
                                    async for chunk in response.aiter_bytes():
                                        content.extend(chunk)
                                        if len(content) > 1024 * 1024:
                                            raise ValueError("Response too large")
                                    data = self.validate_payload(
                                        strict_json_loads(content), indicator
                                    )
                                break
                            except httpx.TransportError:
                                if attempt:
                                    raise
                                await asyncio.sleep(0.5)
                now = datetime.now(UTC)
                expires = now + timedelta(minutes=60 if self.positive(data) else 30)
                with self.reputation.manager.connect() as connection:
                    connection.execute(
                        "INSERT OR REPLACE INTO reputation_cache VALUES (?, ?, ?, ?, ?)",
                        (
                            self.provider,
                            indicator,
                            now.isoformat(),
                            expires.isoformat(),
                            json.dumps(data),
                        ),
                    )
                return data, now.isoformat(), expires.isoformat(), "LIVE"
            except (
                httpx.HTTPError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                RecursionError,
            ):
                return None, None, None, "ERROR"

    def request_options(self, indicator):
        return "GET", {
            "params": {"ipAddress": indicator, "maxAgeInDays": 90},
            "headers": {"Key": self.api_key, "Accept": "application/json"},
        }

    @staticmethod
    def positive(data):
        return data["totalReports"] > 0 or data["abuseConfidenceScore"] > 0

    def evidence(self, data, indicator, retrieved, expires):
        if not self.positive(data):
            return []
        return [
            {
                "source_id": self.provider,
                "kind": "ioc",
                "context": "UNCLASSIFIED",
                "indicator": indicator,
                "match_type": "EXACT_IP",
                "strength": "medium",
                "last_seen": data["lastReportedAt"],
                "reference": "https://www.abuseipdb.com/check/" + indicator,
                "lineage": "abuseipdb",
                "version_id": retrieved,
                "source_version": "api-v2-check-90d",
                "retrieved_at": retrieved,
                "expires_at": expires,
                "stale": False,
                "provider_score": data["abuseConfidenceScore"],
                "report_count": data["totalReports"],
            }
        ]

    async def enrich(self, lookup, mode, allow_external, *, wait_for_slot=False):
        now = datetime.now(UTC)
        indicator = lookup["indicator"]
        global_address = normalize(indicator)[2] and "/" not in indicator
        cached = self.cached(indicator, now) if global_address else None
        previous = (
            self.cached(indicator, now, include_expired=True)
            if global_address and not cached
            else None
        )
        data, retrieved, expires = cached if cached else (None, None, None)
        status = "CACHE" if cached else "UNAVAILABLE"
        if not global_address:
            status = "SKIPPED_NETWORK" if "/" in indicator else "SKIPPED_NON_GLOBAL"
        elif mode != "offline" and not cached:
            if not (allow_external and self.enabled):
                status = "CONSENT_REQUIRED"
            elif not self.configured:
                status = "NOT_CONFIGURED"
            elif mode == "balanced" and resolve(lookup, now)["verdict"] == "THREAT_INDICATED":
                status = "SKIPPED_LOCAL_THREAT"
            else:
                data, retrieved, expires, status = await self.fetch(
                    indicator, wait_for_slot=wait_for_slot
                )
        stale = False
        if data is None and previous and self.positive(previous[0]):
            data, retrieved, expires = previous
            stale = True
            if status == "UNAVAILABLE":
                status = "STALE_CACHE"
        if global_address and (mode != "offline" or cached or stale):
            lookup["source_statuses"].append(
                {
                    "id": self.provider,
                    "kind": "ioc",
                    "stale": data is None or stale,
                    "last_error": None if data is not None and not stale else status,
                    "cache_state": "STALE" if stale else "FRESH" if data is not None else "MISSING",
                    "retrieved_at": retrieved,
                    "expires_at": expires,
                }
            )
        if data is not None:
            lookup["matches"].extend(
                {**item, "stale": stale}
                for item in self.evidence(data, indicator, retrieved, expires)
            )
        return status

    async def analyze(self, indicator, mode="balanced", allow_external=False):
        if mode not in {"offline", "balanced", "deep"}:
            raise ValueError("Mode must be offline, balanced or deep")
        lookup = self.reputation.manager.lookup(indicator)
        status = await self.enrich(lookup, mode, allow_external)
        lookup["conflict"] = has_conflict(lookup["matches"])
        result = resolve(lookup, datetime.now(UTC))
        from uuid import uuid4

        result.update(
            id=str(uuid4()),
            mode=mode,
            live_status=status,
            ruleset_version=HYBRID_RULESET_VERSION,
            coverage_scope="local_and_requested_abuseipdb"
            if any(s["id"].startswith("live:") for s in lookup["source_statuses"])
            else "configured_local_sources",
        )
        with self.reputation.manager.connect() as connection:
            self.reputation.save(connection, result)
        return result

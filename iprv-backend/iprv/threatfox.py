"""ThreatFox IOC normalization and independent multi-provider enrichment."""

import asyncio
import ipaddress
from datetime import UTC, datetime
from uuid import uuid4

from iprv.intelligence import has_conflict
from iprv.live import LiveService
from iprv.reputation import HYBRID_RULESET_VERSION, resolve


def event_time(value):
    if value is None:
        return None
    stamp = datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
    if stamp > datetime.now(UTC):
        raise ValueError("Future IOC event time")
    return stamp.isoformat()


class ThreatFoxService(LiveService):
    provider = "live:threatfox"
    endpoint = "https://threatfox-api.abuse.ch/api/v1/"

    def request_options(self, indicator):
        return "POST", {
            "json": {
                "query": "search_ioc",
                "search_term": indicator,
                "exact_match": True,
            },
            "headers": {"Auth-Key": self.api_key, "Accept": "application/json"},
        }

    @staticmethod
    def validate_payload(body, indicator):
        if body["query_status"] == "no_result":
            if isinstance(body.get("data"), (list, dict)) and body["data"]:
                raise ValueError("Contradictory ThreatFox response")
            return {"records": []}
        if (
            body["query_status"] != "ok"
            or not isinstance(body.get("data"), list)
            or not body["data"]
            or len(body["data"]) > 5000
        ):
            raise ValueError("Unsuccessful or malformed ThreatFox response")
        records = []
        for item in body["data"]:
            if item["ioc_type"] != "ip:port":
                raise ValueError("Unexpected IOC type for IP query")
            host, port = item["ioc"].rsplit(":", 1)
            host = host.removeprefix("[").removesuffix("]")
            if (
                str(ipaddress.ip_address(host)) != indicator
                or not port.isdecimal()
                or not 1 <= int(port) <= 65535
            ):
                raise ValueError("IOC IP or port mismatch")
            score = item["confidence_level"]
            if type(score) is not int or not 0 <= score <= 100:
                raise ValueError("Invalid ThreatFox confidence")
            identifier = str(item["id"])
            if not identifier.isdecimal():
                raise ValueError("Invalid IOC ID")
            first_seen = event_time(item.get("first_seen"))
            last_seen = event_time(item.get("last_seen"))
            if first_seen and last_seen and last_seen < first_seen:
                raise ValueError("Invalid IOC event ordering")
            records.append(
                {
                    "id": identifier,
                    "ioc": item["ioc"],
                    "port": int(port),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "provider_score": score,
                }
            )
        return {"records": records}

    @staticmethod
    def positive(data):
        return bool(data["records"])

    def validate_cached(self, data, indicator):
        if not isinstance(data.get("records"), list) or len(data["records"]) > 5000:
            raise ValueError("Invalid cached IOC records")
        for record in data["records"]:
            required = {"id", "ioc", "port", "first_seen", "last_seen", "provider_score"}
            if not isinstance(record, dict) or not required.issubset(record):
                raise ValueError("Incomplete cached IOC")
            if not isinstance(record["id"], str) or not record["id"].isdecimal():
                raise ValueError("Invalid cached IOC ID")
            host, port = record["ioc"].rsplit(":", 1)
            if (
                str(ipaddress.ip_address(host.strip("[]"))) != indicator
                or int(port) != record["port"]
            ):
                raise ValueError("Mismatched cached IOC")
            if type(record["port"]) is not int or not 1 <= record["port"] <= 65535:
                raise ValueError("Invalid cached IOC port")
            if (
                type(record["provider_score"]) is not int
                or not 0 <= record["provider_score"] <= 100
            ):
                raise ValueError("Invalid cached score")
            for name in ("first_seen", "last_seen"):
                if record[name] is not None:
                    stamp = datetime.fromisoformat(record[name])
                    if stamp.tzinfo is None or stamp > datetime.now(UTC):
                        raise ValueError("Invalid cached event time")
            if (
                record["first_seen"]
                and record["last_seen"]
                and datetime.fromisoformat(record["first_seen"])
                > datetime.fromisoformat(record["last_seen"])
            ):
                raise ValueError("Invalid cached event ordering")
        return data

    def evidence(self, data, indicator, retrieved, expires):
        return [
            {
                "source_id": self.provider,
                "kind": "ioc",
                "context": "UNCLASSIFIED",
                "indicator": indicator,
                "matched_ioc": record["ioc"],
                "port": record["port"],
                "match_type": "EXACT_IP",
                "strength": "medium",
                "first_seen": record["first_seen"],
                "last_seen": record["last_seen"] or record["first_seen"],
                "event_time_basis": "last_seen" if record["last_seen"] else "first_seen",
                "reference": "https://threatfox.abuse.ch/ioc/" + record["id"] + "/",
                "lineage": "threatfox",
                "version_id": retrieved,
                "source_version": "api-v1-search-ioc",
                "retrieved_at": retrieved,
                "expires_at": expires,
                "stale": False,
                "provider_score": record["provider_score"],
            }
            for record in data["records"]
        ]


class HybridService:
    def __init__(self, reputation, providers, network_lookup=None, external_enabled=False):
        self.reputation = reputation
        self.providers = providers
        self.network_lookup = network_lookup
        self.external_enabled = external_enabled

    async def analyze(
        self, indicator, mode="balanced", allow_external=False, *, save=True, wait_for_slot=False
    ):
        if mode not in {"offline", "balanced", "deep"}:
            raise ValueError("Mode must be offline, balanced or deep")
        lookup = self.reputation.manager.lookup(indicator)
        # Each provider receives the same local snapshot, independently of completion order.
        copies = [
            {
                **lookup,
                "matches": list(lookup["matches"]),
                "source_statuses": list(lookup["source_statuses"]),
            }
            for _ in self.providers
        ]
        statuses = await asyncio.gather(
            *[
                provider.enrich(copy, mode, allow_external, wait_for_slot=wait_for_slot)
                for provider, copy in zip(self.providers, copies, strict=True)
            ]
        )
        # Merge only provider additions, preserving the original local evidence once.
        local_matches = len(lookup["matches"])
        local_sources = len(lookup["source_statuses"])
        for copy in copies:
            lookup["matches"].extend(copy["matches"][local_matches:])
            lookup["source_statuses"].extend(copy["source_statuses"][local_sources:])
        lookup["conflict"] = has_conflict(lookup["matches"])
        result = resolve(lookup, datetime.now(UTC))
        result.update(
            id=str(uuid4()),
            mode=mode,
            live_statuses={p.provider: s for p, s in zip(self.providers, statuses, strict=True)},
            ruleset_version=HYBRID_RULESET_VERSION,
            coverage_scope="local_and_requested_providers"
            if any(s["id"].startswith("live:") for s in lookup["source_statuses"])
            else "configured_local_sources",
        )
        if self.network_lookup is not None:
            result["network_lookup"] = await self.network_lookup(
                indicator, mode, allow_external, self.external_enabled
            )
        if save:
            with self.reputation.manager.connect() as connection:
                self.reputation.save(connection, result)
        return result

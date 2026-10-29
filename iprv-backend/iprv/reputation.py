"""Conservative, versioned local reputation rules and immutable result snapshots."""

import ipaddress
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from iprv.intelligence import SourceManager
from iprv.parser import normalize

RULESET_VERSION = "local-1.3"
HYBRID_RULESET_VERSION = "hybrid-1.4"
EVENT_WINDOW = timedelta(days=30)
MAX_HISTORY_BYTES = 16 * 1024 * 1024


def timestamp(value):
    """Reject ambiguous timestamps instead of upgrading uncertain evidence."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def data_stale(record, now):
    expiry = timestamp(record.get("expires_at"))
    retrieved = timestamp(record.get("retrieved_at"))
    return (
        bool(record.get("stale"))
        or expiry is None
        or retrieved is None
        or retrieved > now
        or expiry <= now
    )


def resolve(lookup: dict, now: datetime) -> dict:
    _, _, global_address = normalize(lookup["indicator"])
    sources = []
    for status in lookup["source_statuses"]:
        source = {**status, "stale": data_stale(status, now)}
        if source["stale"] and source.get("cache_state") == "FRESH":
            source["cache_state"] = "STALE"
        sources.append(source)
    available = [s for s in sources if not s["stale"] and not s["last_error"]]
    threat_sources = [s for s in available if s["kind"] == "ioc"]
    coverage = "UNAVAILABLE" if not available else "PARTIAL"
    if threat_sources and len(available) == len(sources):
        coverage = "COMPLETE"
    if lookup.get("matches_truncated") and coverage == "COMPLETE":
        coverage = "PARTIAL"
    evidence = []
    for match in lookup["matches"]:
        event = timestamp(match["last_seen"])
        root = lookup.get("lineage_roots", {}).get(match["lineage"], match["lineage"])
        evidence.append(
            {
                **match,
                "stale": data_stale(match, now),
                "declared_lineage": match["lineage"],
                "lineage": root,
                "event_freshness": "UNKNOWN"
                if event is None or event > now
                else "RECENT"
                if now - event <= EVENT_WINDOW
                else "HISTORICAL",
            }
        )
    threats = [e for e in evidence if e["kind"] == "ioc"]
    current = [e for e in threats if not e["stale"] and e["event_freshness"] == "RECENT"]
    strong = [
        e
        for e in current
        if e["strength"] == "strong"
        and ipaddress.ip_network(e["indicator"], strict=False).num_addresses == 1
    ]
    reasons = []
    if not global_address:
        verdict = "NOT_APPLICABLE"
        reasons.append("Address is not globally routable; matches are retained for inspection.")
    elif strong and lookup.get("query_scope", {}).get("kind") != "NETWORK":
        verdict = "THREAT_INDICATED"
        reasons.append("Recent strong host-specific IOC evidence exists in a fresh source.")
    elif any(e["event_freshness"] != "HISTORICAL" for e in threats):
        verdict = "SUSPICIOUS"
        reasons.append(
            "IOC evidence exists, but strength, event time, data freshness or match precision is insufficient for a strong current finding."
        )
    elif threats:
        verdict = "HISTORICAL_THREAT"
        reasons.append("All matched IOC events are older than the 30-day event window.")
    elif threat_sources and not lookup.get("matches_truncated"):
        verdict = "NO_THREAT_OBSERVED"
        reasons.append(
            "No IOC matched in the available fresh threat sources; this does not establish safety."
        )
    else:
        verdict = "UNKNOWN"
        reasons.append(
            "Evidence was truncated before a no-threat finding could be established."
            if lookup.get("matches_truncated")
            else "No fresh threat source is available."
        )
    contexts = sorted(
        {e["context"] for e in evidence if e["kind"] != "ioc" and e["context"] != "UNCLASSIFIED"}
    )
    if lookup["conflict"]:
        reasons.append(
            "Threat and warninglist/allowlist evidence coexist; contextual matches do not suppress IOC findings."
        )
    if lookup.get("query_scope", {}).get("kind") == "NETWORK":
        reasons.append(
            "Network results describe overlapping indicators, not every address or service in the range."
        )
    if lookup.get("matches_truncated"):
        reasons.append(
            "Evidence match limit reached; the result is incomplete and must not be treated as exhaustive."
        )
    if coverage != "COMPLETE":
        reasons.append("Requested source coverage is incomplete or unavailable.")
    return {
        "indicator": lookup["indicator"],
        "verdict": verdict,
        "context": contexts or ["UNCLASSIFIED"],
        "coverage": coverage,
        "coverage_scope": "configured_local_sources",
        "conflict": lookup["conflict"],
        "reasons": reasons,
        "evidence": evidence,
        "independent_threat_lineages": len({e["lineage"] for e in threats}),
        "lineage_verification": "operator_declared",
        "source_statuses": sources,
        "ruleset_version": RULESET_VERSION,
        "query_scope": lookup.get("query_scope", {"kind": "HOST", "address_count": "1"}),
        "matches_truncated": lookup.get("matches_truncated", False),
        "analyzed_at": now.isoformat(),
    }


class ReputationService:
    def __init__(self, manager: SourceManager):
        self.manager = manager

    def analyze(self, indicator: str):
        result = self.evaluate(indicator)
        with self.manager.connect() as connection:
            self.save(connection, result)
        return result

    def evaluate(self, indicator: str):
        now = datetime.now(UTC)
        result = resolve(self.manager.lookup(indicator, now), now)
        result["id"] = str(uuid4())
        return result

    @staticmethod
    def save(connection, result):
        connection.execute(
            "INSERT INTO analysis_results VALUES (?, ?, ?, ?, ?)",
            (
                result["id"],
                result["indicator"],
                result["analyzed_at"],
                result["ruleset_version"],
                json.dumps(result),
            ),
        )

    def get(self, result_id: str):
        with self.manager.connect() as connection:
            row = connection.execute(
                "SELECT snapshot FROM analysis_results WHERE id=?", (result_id,)
            ).fetchone()
        return json.loads(row["snapshot"]) if row else None

    def history_page(self, indicator, limit=50, before_time=None, before_id=None):
        normalized = normalize(indicator)[0]
        if not 1 <= limit <= 100:
            raise ValueError("History page limit must be between 1 and 100")
        if (before_time is None) != (before_id is None):
            raise ValueError("History cursor requires both time and result ID")
        if before_time is not None and (
            not isinstance(before_time, str)
            or len(before_time) > 64
            or timestamp(before_time) is None
            or not isinstance(before_id, str)
            or not 1 <= len(before_id) <= 128
        ):
            raise ValueError("Invalid history cursor")
        params = [normalized]
        query = "SELECT id,analyzed_at,snapshot FROM analysis_results WHERE indicator=?"
        if before_time is not None:
            query += " AND (analyzed_at, id) < (?, ?)"
            params.extend([before_time, before_id])
        query += " ORDER BY analyzed_at DESC,id DESC LIMIT ?"
        params.append(limit + 1)
        summaries = []
        cursor = None
        has_more = False
        with self.manager.connect() as connection:
            for index, row in enumerate(connection.execute(query, params)):
                if index == limit:
                    has_more = True
                    break
                result = json.loads(row["snapshot"])
                summaries.append(
                    {
                        key: result[key]
                        for key in (
                            "id",
                            "indicator",
                            "analyzed_at",
                            "ruleset_version",
                            "verdict",
                            "coverage",
                            "context",
                            "conflict",
                        )
                    }
                    | {
                        "evidence_count": len(result.get("evidence", [])),
                        "source_count": len(result.get("source_statuses", [])),
                        "matches_truncated": result.get("matches_truncated", False),
                    }
                )
                cursor = {"before_time": row["analyzed_at"], "before_id": row["id"]}
        return {
            "indicator": normalized,
            "results": summaries,
            "has_more": has_more,
            "next_cursor": cursor if has_more else None,
        }

    def history(self, indicator: str, limit: int = 50, offset: int = 0):
        if not 1 <= limit <= 200 or not 0 <= offset <= 1000000:
            raise ValueError("History pagination requires limit 1 to 200 and offset 0 to 1000000")
        normalized = normalize(indicator)[0]
        with self.manager.connect() as connection:
            # Use one read snapshot for the size check and retrieval. Concurrent analyses
            # must not replace the checked page with a larger one between these queries.
            connection.execute("BEGIN")
            query = """SELECT snapshot FROM analysis_results WHERE indicator=?
                ORDER BY analyzed_at DESC, id DESC LIMIT ? OFFSET ?"""
            params = (normalized, limit, offset)
            size = 2
            for row in connection.execute(
                "SELECT length(cast(snapshot AS BLOB)) + 1 FROM (" + query + ")", params
            ):
                size += row[0]
                if size > MAX_HISTORY_BYTES:
                    raise ValueError(
                        "Full history exceeds the 16 MiB response budget; reduce limit or use "
                        "/api/history/page and /api/results/{id} for individual evidence"
                    )
            return [json.loads(row["snapshot"]) for row in connection.execute(query, params)]

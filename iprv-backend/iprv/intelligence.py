"""Versioned local feeds. Imports are validated completely before activation."""

import hashlib
import ipaddress
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from iprv.json_input import strict_json_loads
from iprv.lineage import resolve_roots
from iprv.parser import normalize

CONTEXTS = {
    "UNCLASSIFIED",
    "PUBLIC_DNS",
    "CDN",
    "CLOUD_PROVIDER",
    "KNOWN_SCANNER",
    "INTERNAL_ALLOWLIST",
}


def has_conflict(matches):
    groups = {4: {"ioc": [], "context": []}, 6: {"ioc": [], "context": []}}
    for match in matches:
        if match["kind"] not in {"ioc", "warninglist", "allowlist"}:
            continue
        network = ipaddress.ip_network(match["indicator"], strict=False)
        group = "ioc" if match["kind"] == "ioc" else "context"
        groups[network.version][group].append(
            (int(network.network_address), int(network.broadcast_address))
        )
    for family in groups.values():
        threats, contexts = sorted(family["ioc"]), sorted(family["context"])
        i = j = 0
        while i < len(threats) and j < len(contexts):
            if threats[i][0] <= contexts[j][1] and contexts[j][0] <= threats[i][1]:
                return True
            if threats[i][1] < contexts[j][1]:
                i += 1
            else:
                j += 1
    return False


class SourceManager:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def import_feed(
        self,
        source_id: str,
        kind: str,
        context: str,
        content: bytes,
        format: str = "lines",
        ttl_hours: int = 24,
    ):
        if not isinstance(source_id, str) or not 1 <= len(source_id.strip()) <= 128:
            raise ValueError("Source ID must contain 1 to 128 characters")
        if kind not in {"warninglist", "ioc", "allowlist"} or context not in CONTEXTS:
            raise ValueError("Invalid source kind or context")
        if not 1 <= ttl_hours <= 8760:
            raise ValueError("TTL must be between 1 and 8760 hours")
        try:
            metadata = {}
            if format == "evidence":
                payload = strict_json_loads(content.decode("utf-8-sig"))
                if not isinstance(payload, dict) or not isinstance(payload.get("indicators"), list):
                    raise ValueError("Evidence feed requires an indicators array")
                entries, version = [], str(payload.get("version", "unversioned"))
                for record in payload["indicators"]:
                    if not isinstance(record, dict) or not isinstance(record.get("indicator"), str):
                        raise ValueError("Each evidence record requires an indicator string")
                    value = normalize(record["indicator"])[0]
                    if value in metadata:
                        raise ValueError("Duplicate evidence indicator")
                    strength = record.get("strength", "medium")
                    if strength not in {"strong", "medium", "weak"}:
                        raise ValueError("Invalid evidence strength")
                    times = {}
                    for name in ("first_seen", "last_seen"):
                        value_time = record.get(name)
                        if value_time is not None:
                            if not isinstance(value_time, str):
                                raise ValueError(f"{name} must be a timestamp string")
                            stamp = datetime.fromisoformat(value_time.replace("Z", "+00:00"))
                            if stamp.tzinfo is None or stamp > datetime.now(UTC):
                                raise ValueError(
                                    f"{name} must have timezone and cannot be in the future"
                                )
                            value_time = stamp.astimezone(UTC).isoformat()
                        times[name] = value_time
                    if (
                        times["first_seen"]
                        and times["last_seen"]
                        and times["first_seen"] > times["last_seen"]
                    ):
                        raise ValueError("first_seen cannot be later than last_seen")
                    reference = record.get("reference")
                    lineage = record.get("lineage", source_id)
                    if (
                        (reference is not None and not isinstance(reference, str))
                        or not isinstance(lineage, str)
                        or not lineage
                    ):
                        raise ValueError("Reference and lineage must be strings")
                    if len(lineage) > 128 or (reference is not None and len(reference) > 2048):
                        raise ValueError(
                            "Lineage is limited to 128 characters and references to 2048"
                        )
                    metadata[value] = (
                        strength,
                        times["last_seen"],
                        reference,
                        lineage,
                        times["first_seen"],
                    )
                    entries.append(value)
            else:
                entries, version = self._decode(content, format, kind)
            indicators = list(dict.fromkeys(normalize(value)[0] for value in entries))
            if len(version) > 128:
                raise ValueError("Source version must not exceed 128 characters")
            if not indicators:
                raise ValueError("Empty feed rejected; active version preserved")
        except (ValueError, TypeError, AttributeError, RecursionError) as exc:
            with self.connect() as connection:
                connection.execute(
                    "UPDATE sources SET last_error=? WHERE id=?", (str(exc), source_id)
                )
            raise ValueError(str(exc)) from exc
        now = datetime.now(UTC)
        version_id = str(uuid4())
        records = []
        for value in indicators:
            network = ipaddress.ip_network(value, strict=False)
            records.append(
                (
                    version_id,
                    value,
                    network.version,
                    network.prefixlen,
                    network.network_address.packed.hex(),
                )
            )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO feed_versions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    version_id,
                    source_id,
                    version,
                    now.isoformat(),
                    (now + timedelta(hours=ttl_hours)).isoformat(),
                    hashlib.sha256(content).hexdigest(),
                    len(records),
                ),
            )
            connection.executemany("INSERT INTO indicators VALUES (?, ?, ?, ?, ?)", records)
            connection.executemany(
                """INSERT INTO feed_evidence
                (version_id,indicator,strength,last_seen,reference,lineage,first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        version_id,
                        value,
                        *metadata.get(value, ("medium", None, None, source_id, None)),
                    )
                    for value in indicators
                ],
            )
            connection.execute(
                """INSERT INTO sources VALUES (?, ?, ?, ?, NULL)
                ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, context=excluded.context,
                active_version=excluded.active_version, last_error=NULL""",
                (source_id, kind, context, version_id),
            )
        return {
            "source_id": source_id,
            "version_id": version_id,
            "indicator_count": len(records),
        }

    @staticmethod
    def _decode(content, format, kind):
        text = content.decode("utf-8-sig")
        if format == "lines":
            return [
                line.strip()
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ], "unversioned"
        if format == "misp":
            data = strict_json_loads(text)
            if kind != "warninglist" or not isinstance(data, dict):
                raise ValueError("MISP input requires a warninglist object")
            if data.get("type") not in {"cidr", "string"}:
                raise ValueError("Only IP/CIDR MISP warninglists are supported")
            entries = data.get("list")
            if not isinstance(entries, list) or not all(isinstance(v, str) for v in entries):
                raise ValueError("MISP list must contain strings")
            return entries, str(data.get("version", "unversioned"))
        raise ValueError("Supported feed formats: lines, misp, evidence")

    def sources(self):
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            rows = connection.execute("""SELECT s.*, f.version, f.retrieved_at,
                f.expires_at, f.indicator_count, COALESCE(p.enabled,1) AS enabled FROM sources s
                LEFT JOIN feed_versions f ON f.id=s.active_version
                LEFT JOIN source_settings p ON p.source_id=s.id ORDER BY s.id""").fetchall()
        return [
            {
                **dict(row),
                "enabled": bool(row["enabled"]),
                "stale": row["expires_at"] is None or row["expires_at"] <= now,
            }
            for row in rows
        ]

    def versions(self, source_id, limit=20, offset=0):
        if not 1 <= limit <= 100 or not 0 <= offset <= 1000000:
            raise ValueError("Version pagination requires limit 1 to 100 and offset 0 to 1000000")
        with self.connect() as connection:
            connection.execute("BEGIN")
            source = connection.execute(
                "SELECT active_version FROM sources WHERE id=?", (source_id,)
            ).fetchone()
            if source is None:
                raise KeyError(source_id)
            total = connection.execute(
                "SELECT count(*) FROM feed_versions WHERE source_id=?", (source_id,)
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT * FROM feed_versions WHERE source_id=?
                ORDER BY retrieved_at DESC, id DESC LIMIT ? OFFSET ?""",
                (source_id, limit, offset),
            ).fetchall()
        now = datetime.now(UTC).isoformat()
        return {
            "source_id": source_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "versions": [
                {
                    **dict(row),
                    "active": row["id"] == source["active_version"],
                    "stale": row["expires_at"] <= now,
                }
                for row in rows
            ],
        }

    def set_enabled(self, source_id, enabled):
        with self.connect() as connection:
            if (
                connection.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone()
                is None
            ):
                raise ValueError("Source not found")
            connection.execute(
                "INSERT OR REPLACE INTO source_settings VALUES (?, ?)",
                (source_id, int(enabled)),
            )
        return {"source_id": source_id, "enabled": bool(enabled)}

    def lookup(self, value: str, now: datetime | None = None, *, max_matches: int = 5000):
        now = now or datetime.now(UTC)
        normalized, kind, _ = normalize(value)
        if not 1 <= max_matches <= 10000:
            raise ValueError("Match limit must be between 1 and 10000")
        query = ipaddress.ip_network(normalized, strict=False)
        matches = []
        truncated = False
        with self.connect() as connection:
            connection.execute("BEGIN")
            lineage_roots = resolve_roots(
                dict(connection.execute("SELECT child,parent FROM source_lineage").fetchall())
            )
            sources = connection.execute("""SELECT s.*, f.version, f.retrieved_at, f.expires_at
                FROM sources s JOIN feed_versions f ON f.id=s.active_version
                LEFT JOIN source_settings p ON p.source_id=s.id
                WHERE COALESCE(p.enabled,1)=1 ORDER BY s.id""").fetchall()
            for source in sources:
                for row in self._matching_rows(
                    connection, source, query, kind, max_matches - len(matches) + 1
                ):
                    if len(matches) >= max_matches:
                        truncated = True
                        break
                    matched = ipaddress.ip_network(row["indicator"], strict=False)
                    if kind != "CIDR":
                        match_type = "EXACT_IP" if "/" not in row["indicator"] else "CIDR"
                    else:
                        match_type = (
                            "EXACT_NETWORK"
                            if matched == query
                            else "COVERS_NETWORK"
                            if query.subnet_of(matched)
                            else "WITHIN_NETWORK"
                        )
                    matches.append(
                        {
                            "source_id": source["id"],
                            "kind": source["kind"],
                            "strength": row["strength"] or "medium",
                            "last_seen": row["last_seen"],
                            "first_seen": row["first_seen"],
                            "event_time_basis": "last_seen" if row["last_seen"] else "unknown",
                            "reference": row["reference"],
                            "lineage": row["lineage"] or source["id"],
                            "context": source["context"],
                            "indicator": row["indicator"],
                            "match_type": match_type,
                            "version_id": source["active_version"],
                            "source_version": source["version"],
                            "retrieved_at": source["retrieved_at"],
                            "expires_at": source["expires_at"],
                            "stale": source["expires_at"] <= now.isoformat(),
                        }
                    )
        return {
            "indicator": normalized,
            "matches": matches,
            "sources_checked": len(sources),
            "query_scope": {
                "kind": "NETWORK" if kind == "CIDR" else "HOST",
                "address_count": str(query.num_addresses),
            },
            "matches_truncated": truncated,
            "lineage_roots": lineage_roots,
            "source_statuses": [
                {**dict(s), "stale": s["expires_at"] <= now.isoformat()} for s in sources
            ],
            "conflict": has_conflict(matches),
        }

    @staticmethod
    def _matching_rows(connection, source, query, kind, limit):
        select = """SELECT i.indicator, e.strength, e.first_seen, e.last_seen, e.reference, e.lineage
            FROM indicators i INDEXED BY indicator_prefix_lookup LEFT JOIN feed_evidence e
            ON e.version_id=i.version_id AND e.indicator=i.indicator
            WHERE i.version_id=? AND i.family=? """
        count = 0
        # Probe enclosing prefixes, then range-scan descendants. No address expansion.
        for prefix in range(query.prefixlen, -1, -1):
            network = query.supernet(new_prefix=prefix) if prefix < query.prefixlen else query
            for row in connection.execute(
                select + "AND i.prefix=? AND i.network=? ORDER BY i.indicator",
                (
                    source["active_version"],
                    query.version,
                    prefix,
                    network.network_address.packed.hex(),
                ),
            ):
                yield row
                count += 1
                if count >= limit:
                    return
        if kind == "CIDR":
            yield from connection.execute(
                select.replace(
                    "INDEXED BY indicator_prefix_lookup", "INDEXED BY indicator_network_range"
                )
                + """AND i.prefix>? AND i.network>=? AND i.network<=?
                ORDER BY i.network, i.prefix, i.indicator LIMIT ?""",
                (
                    source["active_version"],
                    query.version,
                    query.prefixlen,
                    query.network_address.packed.hex(),
                    query.broadcast_address.packed.hex(),
                    limit - count,
                ),
            )

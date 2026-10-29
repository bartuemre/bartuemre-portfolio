"""Offline batch analysis and repeatable exports from saved snapshots."""

import csv
import io
import json
from datetime import UTC, datetime
from uuid import uuid4

from iprv.parser import ParsedInput
from iprv.reputation import RULESET_VERSION, ReputationService

MAX_UNIQUE = 1000
MAX_OCCURRENCES = 10000
MAX_BATCH_EVIDENCE = 50000
MAX_DETAILED_CSV_ROWS = 100000


class BatchService:
    def __init__(self, reputation: ReputationService):
        self.reputation = reputation

    def analyze(self, parsed: ParsedInput):
        self.validate(parsed)
        results = {}
        for indicator in parsed.unique_indicators:
            results[indicator] = self.reputation.evaluate(indicator)
            self.validate_evidence_budget(results)
        return self.finalize(parsed, results)

    @staticmethod
    def validate(parsed):
        if len(parsed.unique_indicators) > MAX_UNIQUE or len(parsed.occurrences) > MAX_OCCURRENCES:
            raise ValueError("Batch limit: 1000 unique indicators and 10000 occurrences")
        if not parsed.occurrences:
            raise ValueError("No valid indicators found")

    def finalize(self, parsed, results, mode="offline", ruleset=RULESET_VERSION, job_id=None):
        if set(results) != set(parsed.unique_indicators):
            raise ValueError("Batch results are incomplete; no report was saved")
        self.validate_evidence_budget(results)
        created_at = datetime.now(UTC).isoformat()
        errors = list(parsed.errors)
        occurrences = [
            {
                **item.model_dump(),
                "result_id": results[item.normalized]["id"] if item.normalized in results else None,
                "status": "ANALYZED",
            }
            for item in parsed.occurrences
        ]
        job_id = job_id or str(uuid4())
        report = {
            "job_id": job_id,
            "created_at": created_at,
            "mode": mode,
            "ruleset_version": ruleset,
            "unique_count": len(parsed.unique_indicators),
            "analyzed_count": len(results),
            "occurrence_count": len(occurrences),
            "errors": errors,
            "error_count": max(parsed.error_count, len(errors)),
            "errors_truncated": parsed.errors_truncated,
            "occurrences": occurrences,
            "results": results,
        }
        with self.reputation.manager.connect() as connection:
            run = connection.execute(
                "SELECT status FROM batch_runs WHERE id=?", (job_id,)
            ).fetchone()
            if run is not None and run["status"] != "RUNNING":
                raise ValueError("Batch is no longer running; no report was saved")
            for result in results.values():
                self.reputation.save(connection, result)
            connection.execute(
                "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    created_at,
                    mode,
                    ruleset,
                    len(parsed.unique_indicators),
                    len(occurrences),
                ),
            )
            connection.execute(
                "INSERT INTO job_reports VALUES (?, ?)", (job_id, json.dumps(report))
            )
            # Completion and the complete report must survive or roll back together.
            if run is not None:
                connection.execute(
                    """UPDATE batch_runs SET status='COMPLETED', completed=?,
                    report_id=?, error=NULL WHERE id=?""",
                    (len(results), job_id, job_id),
                )
        return report

    @staticmethod
    def validate_evidence_budget(results):
        if sum(len(result["evidence"]) for result in results.values()) > MAX_BATCH_EVIDENCE:
            raise ValueError(
                "Batch exceeds 50000 evidence records; split the file into smaller batches"
            )

    def get(self, job_id: str):
        with self.reputation.manager.connect() as connection:
            row = connection.execute(
                "SELECT snapshot FROM job_reports WHERE job_id=?", (job_id,)
            ).fetchone()
        return json.loads(row["snapshot"]) if row else None


def safe_cell(value):
    text = str(value) if value is not None else ""
    # Quoting alone does not prevent spreadsheet formula evaluation.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def result_report(result):
    """Adapt one immutable result for the shared CSV writer, without saving a job."""
    indicator = result["indicator"]
    return {
        "job_id": result["id"],
        "created_at": result["analyzed_at"],
        "ruleset_version": result["ruleset_version"],
        "results": {indicator: result},
        "occurrences": [
            {
                "row": 1,
                "field": None,
                "original": indicator,
                "normalized": indicator,
                "result_id": result["id"],
                "status": "ANALYZED",
            }
        ],
    }


def csv_report(report: dict, detailed: bool = False):
    if (
        detailed
        and sum(
            max(1, len(report["results"].get(o["normalized"], {}).get("evidence", [])))
            for o in report["occurrences"]
        )
        > MAX_DETAILED_CSV_ROWS
    ):
        raise ValueError("Detailed CSV exceeds 100000 rows; download JSON or split the input file")
    output = io.StringIO(newline="")
    fields = [
        "row",
        "field",
        "original",
        "indicator",
        "status",
        "verdict",
        "context",
        "coverage",
        "conflict",
        "source_count",
        "freshness",
        "reasons",
        "result_id",
        "ruleset_version",
        "analyzed_at",
        "coverage_scope",
        "query_kind",
        "address_count",
        "matches_truncated",
        "live_statuses",
    ]
    evidence_fields = [
        "source_id",
        "kind",
        "matched_indicator",
        "match_type",
        "strength",
        "last_seen",
        "event_freshness",
        "stale",
        "retrieved_at",
        "expires_at",
        "version_id",
        "source_version",
        "lineage",
        "reference",
        "matched_ioc",
        "port",
        "first_seen",
        "event_time_basis",
        "provider_score",
        "report_count",
        "declared_lineage",
        "provider_criticality",
        "provider_category",
        "provider_source",
        "provider_connection_type",
        "provider_listed_at",
    ]
    if detailed:
        fields += evidence_fields
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for occurrence in report["occurrences"]:
        result = report["results"].get(occurrence["normalized"], {})
        evidence = result.get("evidence", [])
        statuses = result.get("source_statuses", [])
        row = {
            "row": occurrence["row"],
            "field": occurrence["field"],
            "original": occurrence["original"],
            "indicator": occurrence["normalized"],
            "status": occurrence["status"],
            "verdict": result.get("verdict", ""),
            "context": " | ".join(result.get("context", [])),
            "coverage": result.get("coverage", ""),
            "conflict": result.get("conflict", ""),
            "source_count": len(statuses),
            "freshness": "UNAVAILABLE"
            if not statuses
            else "STALE"
            if any(s["stale"] for s in statuses)
            else "FRESH",
            "reasons": " | ".join(result.get("reasons", [])),
            "result_id": occurrence["result_id"],
            "ruleset_version": report["ruleset_version"],
            "analyzed_at": result.get("analyzed_at", ""),
            "coverage_scope": result.get("coverage_scope", ""),
            "query_kind": result.get("query_scope", {}).get("kind", "HOST"),
            "address_count": result.get("query_scope", {}).get("address_count", "1"),
            "matches_truncated": result.get("matches_truncated", False),
            "live_statuses": json.dumps(result.get("live_statuses", {}), sort_keys=True),
        }
        for item in (evidence or [{}]) if detailed else [{}]:
            record = dict(row)
            if detailed:
                record.update({key: item.get(key, "") for key in evidence_fields})
                record["matched_indicator"] = item.get("indicator", "")
            writer.writerow({key: safe_cell(value) for key, value in record.items()})
    return output.getvalue()

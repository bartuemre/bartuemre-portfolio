"""Bounded process-local job queue with durable progress and report snapshots."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from iprv.reputation import HYBRID_RULESET_VERSION


class BatchQueue:
    def __init__(self, batches, hybrid):
        self.batches = batches
        self.hybrid = hybrid
        self.tasks = set()
        self.by_id = {}
        self.semaphore = asyncio.Semaphore(1)

    def recover(self):
        with self.batches.reputation.manager.connect() as connection:
            connection.execute(
                """UPDATE batch_runs SET status='COMPLETED', completed=total,
                report_id=id, error=NULL WHERE status IN ('QUEUED','RUNNING')
                AND EXISTS (SELECT 1 FROM job_reports WHERE job_id=batch_runs.id)"""
            )
            connection.execute(
                "UPDATE batch_runs SET status='INTERRUPTED', error='Server restarted before completion; submit file again' WHERE status IN ('QUEUED', 'RUNNING')"
            )

    def get(self, job_id):
        with self.batches.reputation.manager.connect() as connection:
            row = connection.execute("SELECT * FROM batch_runs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def recent(self, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        with self.batches.reputation.manager.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM batch_runs
                ORDER BY CASE status WHEN 'RUNNING' THEN 0 WHEN 'QUEUED' THEN 1 ELSE 2 END,
                created_at DESC, id DESC
                LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def cancel(self, job_id):
        run = self.get(job_id)
        if run is None:
            raise KeyError(job_id)
        if run["status"] not in {"QUEUED", "RUNNING"}:
            return run
        task = self.by_id.get(job_id)
        if task is None:
            self.update(
                job_id,
                "INTERRUPTED",
                run["completed"],
                "Job is no longer running; submit the file again",
            )
        else:
            self.update(
                job_id,
                "CANCELLED",
                run["completed"],
                "Cancelled by user; no partial report was saved",
            )
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return self.get(job_id)

    def submit(self, parsed, mode, allow_external):
        self.batches.validate(parsed)
        if mode not in {"offline", "balanced", "deep"}:
            raise ValueError("Mode must be offline, balanced or deep")
        if mode != "offline" and len(parsed.unique_indicators) > 100:
            raise ValueError(
                "Live batch limit is 100 unique indicators; use offline for larger files"
            )
        if len(self.tasks) >= 3:
            raise ValueError("Batch queue is full; wait for an active job to complete")
        job_id = str(uuid4())
        total = len(parsed.unique_indicators)
        with self.batches.reputation.manager.connect() as connection:
            connection.execute(
                "INSERT INTO batch_runs VALUES (?, ?, ?, 'QUEUED', ?, 0, NULL, NULL)",
                (job_id, datetime.now(UTC).isoformat(), mode, total),
            )
        task = asyncio.create_task(self.run(job_id, parsed, mode, allow_external))
        self.tasks.add(task)
        self.by_id[job_id] = task
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(lambda _: self.by_id.pop(job_id, None))
        return self.get(job_id)

    def update(self, job_id, status, completed, error=None, report_id=None):
        with self.batches.reputation.manager.connect() as connection:
            connection.execute(
                "UPDATE batch_runs SET status=?, completed=?, error=?, report_id=? WHERE id=?",
                (status, completed, error, report_id, job_id),
            )

    async def run(self, job_id, parsed, mode, allow_external):
        results = {}
        try:
            async with self.semaphore:
                self.update(job_id, "RUNNING", 0)
                for indicator in parsed.unique_indicators:
                    results[indicator] = await self.hybrid.analyze(
                        indicator, mode, allow_external, save=False, wait_for_slot=True
                    )
                    self.batches.validate_evidence_budget(results)
                    self.update(job_id, "RUNNING", len(results))
                    await asyncio.sleep(0)  # Allow polling and cancellation between local lookups.
                self.batches.finalize(parsed, results, mode, HYBRID_RULESET_VERSION, job_id)
        except asyncio.CancelledError:
            if self.get(job_id)["status"] != "CANCELLED":
                self.update(
                    job_id,
                    "INTERRUPTED",
                    len(results),
                    "Server stopped before completion; submit file again",
                )
            raise
        except ValueError as exc:
            self.update(job_id, "FAILED", len(results), str(exc))
        except Exception:
            self.update(
                job_id,
                "FAILED",
                len(results),
                "Batch analysis failed; no partial report was saved",
            )

    async def close(self):
        pending = list(self.tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        with self.batches.reputation.manager.connect() as connection:
            connection.execute(
                "UPDATE batch_runs SET status='INTERRUPTED', error='Server stopped before completion; submit file again' WHERE status IN ('QUEUED','RUNNING')"
            )

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from iprv import __version__
from iprv.batches import BatchQueue
from iprv.database import initialize
from iprv.intelligence import SourceManager
from iprv.lineage import LineageRegistry
from iprv.live import LiveService
from iprv.parser import normalize, parse_input
from iprv.reporting import BatchService, csv_report, result_report
from iprv.reputation import ReputationService
from iprv.security import MAX_FILE_BYTES, ApiAccessGuard, RequestBodyLimit
from iprv.settings import Settings
from iprv.sync import FeedSync
from iprv.threatfox import HybridService, ThreatFoxService
from iprv.usom import UsomService

MAX_UPLOAD = MAX_FILE_BYTES


def create_app(database_path: str | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    path = database_path or settings.database

    @asynccontextmanager
    async def lifespan(app):
        initialize(path)
        queue.recover()
        task = (
            asyncio.create_task(feed_sync.run())
            if feed_sync.enabled and settings.auto_sync
            else None
        )
        try:
            yield
        finally:
            await queue.close()
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    hosted = settings.deployment == "cloud"
    app = FastAPI(
        title="IPRV",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if hosted else "/docs",
        redoc_url=None if hosted else "/redoc",
        openapi_url=None if hosted else "/openapi.json",
    )
    app.add_middleware(RequestBodyLimit)

    @app.middleware("http")
    async def browser_origin_guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            allowed = {str(request.base_url).rstrip("/")}
            if settings.frontend_origin:
                allowed.add(settings.frontend_origin)
            if origin.rstrip("/") not in allowed:
                return JSONResponse(
                    {"detail": "Cross-origin write requests are not allowed"},
                    status_code=403,
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/" or request.url.path.startswith("/assets/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                "object-src 'none'; base-uri 'none'; form-action 'self'"
            )
        return response

    if hosted:
        app.add_middleware(ApiAccessGuard, token=settings.access_token)
    if settings.frontend_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.frontend_origin],
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "testserver"]
        + ([settings.public_host] if settings.public_host else []),
    )

    manager = SourceManager(path)
    lineage = LineageRegistry(manager)
    feed_sync = FeedSync(manager, settings.allow_feed_downloads)
    reputation = ReputationService(manager)
    batches = BatchService(reputation)
    external_enabled = settings.allow_external
    live = HybridService(
        reputation,
        [
            LiveService(reputation, settings.abuseipdb_key, external_enabled),
            ThreatFoxService(reputation, settings.threatfox_key, external_enabled),
            UsomService(reputation, enabled=external_enabled),
        ],
    )
    queue = BatchQueue(batches, live)

    @app.post("/api/batches", status_code=202)
    async def start_batch(
        file: UploadFile = File(...),
        column: str | None = Form(None),
        mode: str = Form("offline"),
        allow_external: bool = Form(False),
    ):
        try:
            content = await file.read(MAX_UPLOAD + 1)
        finally:
            await file.close()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Maximum file size is 5 MiB")
        try:
            parsed = await run_in_threadpool(parse_input, content, file.filename or "", column)
            return queue.submit(parsed, mode, allow_external)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/batches/{job_id}")
    def batch_progress(job_id: str):
        run = queue.get(job_id)
        if run is None:
            raise HTTPException(404, "Batch job not found")
        return run

    @app.get("/api/batches")
    def recent_batches(limit: int = 20):
        try:
            return queue.recent(limit)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/batches/{job_id}/cancel")
    async def cancel_batch(job_id: str):
        try:
            return await queue.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(404, "Batch job not found") from exc

    @app.get("/api/status")
    def status():
        with manager.connect() as connection:
            total = connection.execute("SELECT count(*) FROM analysis_results").fetchone()[0]
            jobs = connection.execute("SELECT count(*) FROM job_reports").fetchone()[0]
        return {
            "version": __version__,
            "analyses": total,
            "jobs": jobs,
            "external_enabled": external_enabled,
            "feed_downloads_enabled": feed_sync.enabled,
            "auto_sync_enabled": feed_sync.enabled and settings.auto_sync,
            "ephemeral_storage": settings.ephemeral_storage,
            "deployment": settings.deployment,
            "providers": [
                {
                    "id": p.provider,
                    "configured": p.configured,
                    "requires_api_key": p.requires_api_key,
                }
                for p in live.providers
            ],
        }

    @app.get("/api/feed-catalog")
    def feed_catalog():
        return feed_sync.catalog()

    @app.post("/api/feeds/{source_id}/sync")
    async def sync_feed(source_id: str, body: SyncRequest):
        try:
            return await feed_sync.sync(source_id, body.allow_download)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/jobs")
    def list_jobs(limit: int = 20, before_time: str | None = None, before_id: str | None = None):
        if not 1 <= limit <= 100:
            raise HTTPException(422, "Limit must be between 1 and 100")
        if (before_time is None) != (before_id is None):
            raise HTTPException(422, "Both cursor fields are required")
        if before_time is not None:
            try:
                stamp = datetime.fromisoformat(before_time.replace("Z", "+00:00"))
                if len(before_time) > 64 or stamp.tzinfo is None or not 1 <= len(before_id) <= 128:
                    raise ValueError
            except ValueError as exc:
                raise HTTPException(422, "Invalid report cursor") from exc
        cursor_sql = "WHERE (a.created_at, a.id) < (?, ?)" if before_time else ""
        parameters = (before_time, before_id, limit) if before_time else (limit,)
        with manager.connect() as connection:
            rows = connection.execute(
                "SELECT a.* FROM analysis_jobs a JOIN job_reports j ON j.job_id=a.id "
                + cursor_sql
                + " ORDER BY a.created_at DESC, a.id DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    @app.post("/api/preview")
    async def preview(file: UploadFile = File(...), column: str | None = Form(None)):
        try:
            content = await file.read(MAX_UPLOAD + 1)
        finally:
            await file.close()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Maximum file size is 5 MiB")
        try:
            parsed = await run_in_threadpool(parse_input, content, file.filename or "", column)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "columns": parsed.columns,
            "unique_count": len(parsed.unique_indicators),
            "occurrence_count": len(parsed.occurrences),
            "errors": parsed.errors,
            "error_count": parsed.error_count,
            "errors_truncated": parsed.errors_truncated,
            "preview": [item.model_dump() for item in parsed.occurrences[:20]],
        }

    @app.post("/api/analyze/file")
    async def analyze_file(file: UploadFile = File(...), column: str | None = Form(None)):
        try:
            content = await file.read(MAX_UPLOAD + 1)
        finally:
            await file.close()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Maximum file size is 5 MiB")

        def process():
            return batches.analyze(parse_input(content, file.filename or "", column))

        try:
            return await run_in_threadpool(process)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        report = batches.get(job_id)
        if report is None:
            raise HTTPException(404, "Batch report not found")
        return report

    @app.get("/api/jobs/{job_id}/export")
    def export_job(job_id: str, format: str = "json", detailed: bool = False):
        if format not in {"json", "csv"}:
            raise HTTPException(422, "Export format must be json or csv")
        report = batches.get(job_id)
        if report is None:
            raise HTTPException(404, "Batch report not found")
        import json

        try:
            content = (
                json.dumps(report, ensure_ascii=False)
                if format == "json"
                else csv_report(report, detailed)
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(
            content,
            media_type="application/json" if format == "json" else "text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="iprv-{report["job_id"]}.{format}"'
            },
        )

    @app.post("/api/analyze")
    async def analyze(body: AnalysisRequest):
        try:
            return await live.analyze(body.indicator, body.mode, body.allow_external)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/history")
    def history(indicator: str, limit: int = 50, offset: int = 0):
        try:
            return reputation.history(indicator, limit, offset)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/results/{result_id}")
    def get_result(result_id: str):
        result = reputation.get(result_id)
        if result is None:
            raise HTTPException(404, "Analysis result not found")
        return result

    @app.get("/api/history/page")
    def history_page(
        indicator: str,
        limit: int = 50,
        before_time: str | None = None,
        before_id: str | None = None,
    ):
        try:
            return reputation.history_page(indicator, limit, before_time, before_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/results/{result_id}/export")
    def export_result(result_id: str, format: str = "json", detailed: bool = False):
        if format not in {"json", "csv"}:
            raise HTTPException(422, "Export format must be json or csv")
        result = reputation.get(result_id)
        if result is None:
            raise HTTPException(404, "Analysis result not found")
        import json

        try:
            content = (
                json.dumps(result, ensure_ascii=False)
                if format == "json"
                else csv_report(result_report(result), detailed)
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(
            content,
            media_type="application/json" if format == "json" else "text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="iprv-result-{result["id"]}.{format}"'
            },
        )

    @app.get("/api/sources")
    def sources():
        return manager.sources()

    @app.patch("/api/sources/{source_id}")
    def configure_source(source_id: str, body: SourceSettingsRequest):
        try:
            return manager.set_enabled(source_id, body.enabled)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/sources/{source_id}/versions")
    def source_versions(source_id: str, limit: int = 20, offset: int = 0):
        try:
            return manager.versions(source_id, limit, offset)
        except KeyError as exc:
            raise HTTPException(404, "Source not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/lineage")
    def list_lineage():
        return lineage.list()

    @app.post("/api/lineage")
    def add_lineage(body: LineageRequest):
        try:
            return lineage.put(body.child, body.parent)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.delete("/api/lineage/{child}")
    def remove_lineage(child: str):
        lineage.remove(child)
        return {"removed": child}

    @app.post("/api/sources/{source_id}/import")
    async def import_source(
        source_id: str,
        file: UploadFile = File(...),
        kind: str = Form(...),
        context: str = Form("UNCLASSIFIED"),
        format: str = Form("lines"),
        ttl_hours: int = Form(24),
    ):
        if not 1 <= len(source_id) <= 128:
            raise HTTPException(422, "Source ID must have 1 to 128 characters")
        try:
            content = await file.read(MAX_UPLOAD + 1)
        finally:
            await file.close()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Maximum file size is 5 MiB")
        try:
            return await run_in_threadpool(
                manager.import_feed, source_id, kind, context, content, format, ttl_hours
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/lookup")
    def lookup(body: ValidationRequest):
        try:
            return manager.lookup(body.indicator)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.post("/api/validate")
    def validate(body: ValidationRequest):
        try:
            normalized, kind, global_address = normalize(body.indicator)
        except ValueError as exc:
            raise HTTPException(422, "Invalid IPv4, IPv6 or CIDR") from exc
        return {
            "normalized": normalized,
            "kind": kind,
            "is_global": global_address,
            "external_lookup_eligible": global_address and kind != "CIDR",
            "verdict": "UNKNOWN" if global_address else "NOT_APPLICABLE",
            "coverage": "UNAVAILABLE",
            "context": "UNCLASSIFIED",
        }

    @app.post("/api/parse")
    async def parse(file: UploadFile = File(...), column: str | None = Form(None)):
        try:
            content = await file.read(MAX_UPLOAD + 1)
        finally:
            await file.close()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Maximum file size is 5 MiB")
        try:
            parsed = await run_in_threadpool(parse_input, content, file.filename or "", column)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        job_id = str(uuid4())
        with manager.connect() as connection:
            connection.execute(
                "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    datetime.now(UTC).isoformat(),
                    "offline",
                    "core-0.1",
                    len(parsed.unique_indicators),
                    len(parsed.occurrences),
                ),
            )
        return {"job_id": job_id, **parsed.model_dump()}

    frontend = Path(__file__).parent / "static"
    if (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        if (frontend / "index.html").is_file():
            return FileResponse(frontend / "index.html")
        return {
            "message": "IPRV API is running. Build the frontend to enable the dashboard.",
            "docs": "/docs",
        }

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        if not (frontend / "favicon.svg").is_file():
            raise HTTPException(404, "Favicon not built")
        return FileResponse(frontend / "favicon.svg", media_type="image/svg+xml")

    return app


class ValidationRequest(BaseModel):
    indicator: str = Field(min_length=1, max_length=128)


class AnalysisRequest(ValidationRequest):
    mode: str = "balanced"
    allow_external: bool = False


class SyncRequest(BaseModel):
    allow_download: bool = False


class SourceSettingsRequest(BaseModel):
    enabled: bool


class LineageRequest(BaseModel):
    child: str = Field(min_length=1, max_length=128)
    parent: str = Field(min_length=1, max_length=128)


app = create_app()

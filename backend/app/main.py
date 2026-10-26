"""FastAPI app for Repu (local-first). Build with create_app(); `app` is the default instance.

Privacy: chat text is held in memory only, never logged, never sent anywhere except the
configured local Ollama URL.
"""
from __future__ import annotations

import logging
import threading
import time as _time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings, load_settings
from .errors import AppError, file_too_large, invalid_file_type, no_messages, session_expired
from .services.brief_service import ai_summary, build_brief
from .services.calendar_exporter import build_ics
from .services.chat_parser import ParseResult, decode_bytes, parse_chat
from .services.extraction_service import ExtractionService
from .services.llm_client import OllamaClient

log = logging.getLogger("repu")
ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample_data" / "synthetic_whatsapp_chat.txt"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Session:
    id: str
    parsed: ParseResult
    created: datetime = field(default_factory=_now)
    tasks: list = field(default_factory=list)


@dataclass
class Job:
    id: str
    session_id: str
    state: str = "running"  # running | done | error
    done: int = 0
    total: int = 0
    result: dict | None = None
    error: dict | None = None
    status: int = 200
    created: datetime = field(default_factory=_now)


class Analyze(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=8, max_length=64)
    display_name: str | None = Field(default=None, max_length=60)
    summary: bool = True


class ExportTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    date: str
    time: str | None = None
    task_confirmed: bool
    owner_confirmed: bool
    deadline_confirmed: bool
    export_approved: bool
    reminder_minutes: int | None = Field(default=None, ge=0, le=10080)


class Export(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tasks: list[ExportTask] = Field(max_length=200)


def _err(code: str, message: str, action: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "action": action,
                                   "request_id": uuid.uuid4().hex[:12]}}, status_code=status)


def create_app(settings: Settings | None = None, llm=None) -> FastAPI:
    S = settings or load_settings()
    client = llm or OllamaClient(S.ollama_base_url, S.ollama_model, S.ollama_timeout)
    infer_lock = threading.Semaphore(1)  # one inference job at a time (small laptops)
    sessions: dict[str, Session] = {}
    jobs: dict[str, Job] = {}
    lock = threading.Lock()

    def purge() -> None:
        cutoff = _now() - timedelta(minutes=S.session_ttl_minutes)
        with lock:
            for k in [k for k, v in sessions.items() if v.created < cutoff]:
                sessions.pop(k, None)
            for k in [k for k, v in jobs.items() if v.created < cutoff or v.session_id not in sessions]:
                jobs.pop(k, None)

    def get_session(sid: str) -> Session:
        purge()
        s = sessions.get(sid)
        if not s:
            raise session_expired()
        return s

    app = FastAPI(title="Repu", version=S.app_version, docs_url=None if S.demo_mode else "/docs", redoc_url=None)
    app.state.sessions = sessions
    app.add_middleware(CORSMiddleware, allow_origins=list(S.allowed_origins),
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.exception_handler(AppError)
    async def _app_error(request: Request, e: AppError):
        return JSONResponse(e.to_dict(uuid.uuid4().hex[:12]), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, e: RequestValidationError):
        fields = ", ".join(".".join(str(x) for x in err.get("loc", ())) + ": " + str(err.get("type", ""))
                           for err in e.errors())  # field names + error types only; never input values
        return _err("INVALID_REQUEST", f"Request validation failed ({fields}).", "Check the inputs and try again.", 422)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, e: Exception):
        rid = uuid.uuid4().hex[:12]
        log.error("unhandled error type=%s request_id=%s", type(e).__name__, rid)  # never log content
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong.",
                                       "action": "Retry. If it persists, restart the app.", "request_id": rid}},
                            status_code=500)

    @app.get("/api/health")
    def health():
        st = client.status()
        return {"status": "ok", "version": S.app_version, "demo_mode": S.demo_mode,
                "ollama_reachable": st.ollama_reachable, "inference_available": st.installed}

    @app.get("/api/model/status")
    def model_status(deep: bool = False):
        st = client.status(deep=deep)
        return {"ollama_reachable": st.ollama_reachable, "model": st.model, "installed": st.installed,
                "inference_ok": st.inference_ok, "next_step": st.next_step}

    @app.get("/api/demo/sample")
    def demo_sample():
        return {"text": SAMPLE.read_text(encoding="utf-8"), "note": "Fictional demo data."}

    @app.post("/api/import/preview")
    async def import_preview(request: Request):
        limit = S.max_upload_mb * 1024 * 1024
        try:
            declared = int(request.headers.get("content-length", "0"))
        except ValueError:
            declared = 0
        if declared > limit + 64 * 1024:  # reject before reading the body
            raise file_too_large(S.max_upload_mb)
        form = await request.form(max_part_size=limit + 1)
        file, text = form.get("file"), form.get("text")
        date_order = str(form.get("date_order") or "auto")
        if S.demo_mode:
            if file is not None and getattr(file, "filename", ""):
                raise _demo_blocked("File upload is disabled in the hosted demo.")
            if not (isinstance(text, str) and text.strip() == SAMPLE.read_text(encoding="utf-8").strip()):
                raise _demo_blocked("The hosted demo only accepts the built-in fictional sample chat.")
        if file is not None and hasattr(file, "read") and getattr(file, "filename", ""):
            if not file.filename.lower().endswith(".txt"):
                raise invalid_file_type()
            data = await file.read(limit + 1)
            if len(data) > limit:
                raise file_too_large(S.max_upload_mb)
            body = decode_bytes(data)
        elif isinstance(text, str) and text.strip():
            if len(text.encode("utf-8")) > limit:
                raise file_too_large(S.max_upload_mb)
            body = text
        else:
            raise no_messages()
        parsed = parse_chat(body, date_order if date_order in ("auto", "dmy", "mdy") else "auto",
                            S.max_messages_per_import)
        sid = uuid.uuid4().hex
        purge()
        with lock:
            sessions[sid] = Session(sid, parsed)
        stamps = [m.timestamp for m in parsed.messages if m.timestamp]
        usable = parsed.usable
        return {"session_id": sid, "date_order": parsed.date_order,
                "message_count": len(parsed.messages), "analysable_messages": len(usable),
                "unique_senders": len({m.sender for m in usable if m.sender}),
                "skipped_system": parsed.skipped_system, "skipped_attachments": parsed.skipped_attachments,
                "date_range": [min(stamps).isoformat(), max(stamps).isoformat()] if stamps else None,
                "warnings": parsed.warnings}

    def run_analysis(s: Session, req: Analyze, progress=None) -> dict:
        svc = ExtractionService(client, S.max_messages_per_batch, S.ollama_model)
        t0 = _time.time()
        with infer_lock:
            res = svc.analyze(s.parsed.messages, req.display_name, progress)
            lines = ai_summary(client, s.parsed.messages) if req.summary else []
        s.tasks = res.tasks
        secs = round(_time.time() - t0, 1)
        log.info("analyze done batches=%d failed=%d tasks=%d secs=%.1f model=%s", res.batches_total, res.batches_failed,
                 len(res.tasks), secs, S.ollama_model)
        return {"session_id": s.id, "model": res.model, "batches_total": res.batches_total,
                "batches_failed": res.batches_failed, "non_actionable_count": res.non_actionable,
                "warnings": res.warnings, "tasks": [t.to_dict() for t in res.tasks], "brief": build_brief(res.tasks, lines),
                "stats": {"messages_read": len(s.parsed.usable), "seconds": secs}}

    @app.post("/api/analyze")
    def analyze(req: Analyze):
        if S.demo_mode:
            raise _demo_blocked("Model inference is disabled in the hosted demo. Run Repu locally to analyse chats.")
        return run_analysis(get_session(req.session_id), req)

    @app.post("/api/analyze/start")
    def analyze_start(req: Analyze):
        """Same as /api/analyze but returns at once; poll /api/analyze/status/{job_id} for REAL batch progress."""
        if S.demo_mode:
            raise _demo_blocked("Model inference is disabled in the hosted demo. Run Repu locally to analyse chats.")
        s = get_session(req.session_id)
        job = Job(uuid.uuid4().hex, s.id)
        with lock:
            jobs[job.id] = job

        def work():
            try:
                def prog(i, n):
                    job.done, job.total = i - 1, n
                job.result = run_analysis(s, req, prog)
                job.done = job.total
                job.state = "done"
            except AppError as e:
                job.error, job.status, job.state = e.to_dict(uuid.uuid4().hex[:12])["error"], e.status, "error"
            except Exception as e:  # never log content
                log.error("job failed type=%s", type(e).__name__)
                job.error = {"code": "INTERNAL_ERROR", "message": "Something went wrong.", "action": "Retry.", "request_id": job.id[:12]}
                job.status, job.state = 500, "error"
        threading.Thread(target=work, daemon=True).start()
        return {"job_id": job.id}

    @app.get("/api/analyze/status/{job_id}")
    def analyze_status(job_id: str):
        purge()
        j = jobs.get(job_id)
        if not j:
            raise session_expired()
        return {"state": j.state, "done": j.done, "total": j.total, "result": j.result, "error": j.error, "http_status": j.status}

    @app.post("/api/export/ics")
    def export_ics(req: Export):
        data, n = build_ics([t.model_dump() for t in req.tasks], S.default_event_minutes)
        name = f"repu-tasks-{datetime.now():%Y%m%d}.ics"
        return Response(data, media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"',
                                 "X-Exported-Count": str(n)})

    @app.delete("/api/session/{session_id}")
    def delete_session(session_id: str):
        with lock:
            existed = sessions.pop(session_id, None) is not None
            for k in [k for k, v in jobs.items() if v.session_id == session_id]:
                jobs.pop(k, None)
        return {"deleted": existed,
                "detail": "Session data released from application memory." if existed
                else "No such session (already expired or cleared).",
                "limitations": "Python/OS may retain freed memory pages until they are reused."}

    static = ROOT / "frontend" / "dist"
    if not static.exists():
        static = ROOT / "frontend"
    if (static / "index.html").exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")
    return app


def _demo_blocked(msg: str) -> AppError:
    return AppError("DEMO_MODE", msg, "Run Repu locally with Ollama (see README).", 403)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = create_app()

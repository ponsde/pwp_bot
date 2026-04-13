"""FastAPI backend serving the taidi_bei web frontend.

Endpoints (all under ``/api``):
- ``POST /api/ask``  — answer a question (SQL / RAG / hybrid routing)
- ``GET  /api/stats`` — basic DB stats for the home dashboard
- ``GET  /api/health`` — liveness probe + engine capability

Static ``web-studio/dist/`` is mounted at ``/`` when the build exists, so a
single Railway service can serve both the SPA and the API.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.query.answer import build_answer_content
from src.query.chart import render_chart, safe_chart_data, select_chart_type
from src.query.conversation import ConversationManager
from src.query.text2sql import Text2SQLEngine

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("SQLITE_DB_PATH", str(ROOT_DIR / "data" / "db" / "finance.db"))
CHART_DIR = ROOT_DIR / "result"
WEB_DIST_DIR = ROOT_DIR / "web-studio" / "dist"
UPLOAD_TMP_DIR = ROOT_DIR / "data" / "tmp_uploads"


@dataclass
class Session:
    conversation: ConversationManager


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class Reference(BaseModel):
    paper_path: str
    text: str
    paper_image: str = ""


class AskResponse(BaseModel):
    session_id: str
    content: str
    route: str = "sql"
    sql: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    chart_url: str | None = None
    chart_type: str | None = None
    references: list[Reference] = Field(default_factory=list)
    needs_clarification: bool = False
    error: str | None = None


class AddResourceRequest(BaseModel):
    temp_file_id: str | None = None
    path: str | None = None
    source_name: str | None = None
    reason: str = ""
    instruction: str = ""
    # Default wait=False so the HTTP request returns once OV has queued
    # the work. Summary generation (L0/L1 via VLM) can take minutes per
    # multi-page report; blocking here makes the upload UI freeze.
    # Users refresh the Resources tab to see indexing progress.
    wait: bool = False
    build_index: bool = True
    summarize: bool = False
    telemetry: bool = False
    # Accept + silently ignore the rest of OV's add-resource surface the
    # frontend may send (strict / ignore_dirs / include / exclude / ...)
    # so the contract with the vendored SPA stays compatible.
    strict: bool | None = None
    directly_upload_media: bool | None = None
    preserve_structure: bool | None = None


class StatsResponse(BaseModel):
    company_count: int
    report_period_count: int
    latest_period: str | None
    db_path: str
    rag_enabled: bool


_engine: Any = None  # Text2SQLEngine | ResearchQAEngine
_sessions: dict[str, Session] = {}


def _build_llm_client() -> Any | None:
    try:
        from src.llm.client import LLMClient

        client = LLMClient.from_env()
        logger.info("LLMClient initialized from env")
        return client
    except Exception as exc:
        logger.warning("LLM disabled, falling back to heuristic: %s", exc)
        return None


def _try_build_research_engine(llm_client: Any | None) -> Any | None:
    """Attempt to build a ResearchQAEngine; return None if OV is unavailable."""
    try:
        from src.knowledge.ov_adapter import init_client
        from src.knowledge.research_qa import ResearchQAEngine

        ov_client = init_client()
        engine = ResearchQAEngine(db_path=DB_PATH, client=ov_client, llm_client=llm_client)
        logger.info("ResearchQAEngine initialized (SQL + RAG routing enabled)")
        return engine
    except Exception as exc:
        logger.warning("OpenViking unavailable, RAG disabled: %s", exc)
        return None


def get_engine() -> Any:
    global _engine
    if _engine is None:
        llm = _build_llm_client()
        _engine = _try_build_research_engine(llm) or Text2SQLEngine(DB_PATH, llm_client=llm)
    return _engine


def _is_research_engine(engine: Any) -> bool:
    return engine.__class__.__name__ == "ResearchQAEngine"


def _get_or_create_session(session_id: str | None) -> tuple[str, Session]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    new_id = session_id or uuid.uuid4().hex
    session = Session(conversation=ConversationManager())
    _sessions[new_id] = session
    return new_id, session


def _render_chart_for(
    question: str,
    rows: list[dict[str, Any]],
    request_id: str,
    chart_type_hint: str | None = None,
) -> tuple[str | None, str | None]:
    chart_data, chart_vf = safe_chart_data(rows)
    if not chart_data:
        return None, None
    chart_type = chart_type_hint or select_chart_type(question, chart_data)
    if not chart_type or chart_type == "none":
        return None, chart_type
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHART_DIR / f"ask_{request_id}.jpg"
    image = render_chart(chart_type, chart_data, str(out_path), question, value_field=chart_vf)
    if not image:
        return None, chart_type
    return f"/charts/{Path(image).name}", chart_type


def _answer_with_text2sql(engine: Text2SQLEngine, req: AskRequest, session_id: str, session: Session) -> AskResponse:
    result = engine.query(req.question, session.conversation)
    if result.needs_clarification:
        content = result.clarification_question or "请补充信息。"
        session.conversation.add_assistant_message(content)
        return AskResponse(
            session_id=session_id, content=content, sql=result.sql, rows=[], needs_clarification=True,
        )
    if result.error:
        session.conversation.add_assistant_message(result.error)
        return AskResponse(
            session_id=session_id, content=result.error, sql=result.sql, rows=[], error=result.error,
        )
    content = build_answer_content(req.question, result.rows, intent=result.intent)
    session.conversation.add_assistant_message(content)
    chart_url, chart_type = _render_chart_for(req.question, result.rows, request_id=session_id[:12])
    return AskResponse(
        session_id=session_id,
        content=content,
        sql=result.sql,
        rows=result.rows,
        chart_url=chart_url,
        chart_type=chart_type,
    )


def _answer_with_research(engine: Any, req: AskRequest, session_id: str, session: Session) -> AskResponse:
    answer = engine.answer_question(req.question, session.conversation)
    session.conversation.add_assistant_message(answer.answer)
    chart_rows = answer.chart_rows or []
    chart_url, chart_type = _render_chart_for(
        req.question, chart_rows, request_id=session_id[:12], chart_type_hint=answer.chart_type,
    )
    references = [
        Reference(paper_path=r.paper_path, text=r.text, paper_image=r.paper_image)
        for r in answer.references
    ]
    return AskResponse(
        session_id=session_id,
        content=answer.answer,
        route=answer.route,
        sql=answer.sql or None,
        rows=chart_rows,
        chart_url=chart_url,
        chart_type=chart_type,
        references=references,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="财报智能问数", version="1.0")

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "rag_enabled": _is_research_engine(get_engine())}

    @app.get("/health")
    def ov_compatible_health() -> dict[str, Any]:
        """Satisfies the web-studio shell's OV connection probe.

        The vendored frontend pings ``$VITE_OV_BASE_URL/health`` at boot to
        decide its 'server mode' badge. Presence of ``user_id`` flips it to
        'dev-implicit' (muted badge, no ConnectionDialog nag). We run OV
        embedded, so there's no real OV server — this endpoint tells the
        frontend it's talking to one."""
        return {"status": "ok", "user_id": "embedded"}

    @app.get("/api/stats", response_model=StatsResponse)
    def stats() -> StatsResponse:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT COUNT(DISTINCT stock_code), COUNT(DISTINCT report_period), MAX(report_period) "
                    "FROM core_performance_indicators_sheet"
                ).fetchone()
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc
        company_count, period_count, latest = rows or (0, 0, None)
        return StatsResponse(
            company_count=company_count or 0,
            report_period_count=period_count or 0,
            latest_period=latest,
            db_path=DB_PATH,
            rag_enabled=_is_research_engine(get_engine()),
        )

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        session_id, session = _get_or_create_session(req.session_id)
        session.conversation.add_user_message(req.question)
        engine = get_engine()
        if _is_research_engine(engine):
            return _answer_with_research(engine, req, session_id, session)
        return _answer_with_text2sql(engine, req, session_id, session)

    @app.post("/api/v1/resources/temp_upload")
    async def resources_temp_upload(
        file: UploadFile = File(...),
        telemetry: bool = Form(False),
    ) -> dict[str, Any]:
        """Drop-in for OV's temp_upload.

        Stores the upload at ``tmp_uploads/<uuid>/<original-filename>`` so
        downstream ETL (which parses stock_code/report_period from the
        filename) sees the real name. The ``temp_file_id`` is just the UUID
        directory — the add_resource call resolves the single file inside."""
        original_name = Path(file.filename or "upload.bin").name
        tmp_id = uuid.uuid4().hex
        tmp_dir = UPLOAD_TMP_DIR / tmp_id
        tmp_dir.mkdir(parents=True, exist_ok=True)
        target = tmp_dir / original_name
        target.write_bytes(await file.read())
        return {"status": "ok", "result": {"temp_file_id": tmp_id}}

    @app.post("/api/v1/resources")
    def resources_add(req: AddResourceRequest) -> dict[str, Any]:
        """Receive a staged file and feed it through BOTH pipelines:
        1. ETL → SQLite (so Text2SQL can query it)
        2. OpenViking add_resource → vector index (so RAG can retrieve it)

        Failures on one side surface as warnings; we only return status=error
        if both pipelines die."""
        if not req.temp_file_id:
            raise HTTPException(status_code=400, detail="temp_file_id required")

        tmp_dir = UPLOAD_TMP_DIR / req.temp_file_id
        if not tmp_dir.is_dir():
            raise HTTPException(status_code=404, detail="temp_file_id not found")
        files = [p for p in tmp_dir.iterdir() if p.is_file()]
        if not files:
            raise HTTPException(status_code=404, detail="staged upload is empty")
        pdf_path = files[0]

        warnings: list[str] = []
        errors: list[str] = []
        etl_status: str | None = None
        ov_uri: str | None = None

        # Pipeline 1: ETL into SQLite (financial-report PDFs only)
        if pdf_path.suffix.lower() == ".pdf":
            try:
                from src.etl.loader import ETLLoader

                loader = ETLLoader(Path(DB_PATH))
                result = loader.load_pdf(pdf_path)
                etl_status = result.get("status", "unknown")
                if etl_status == "skipped":
                    warnings.append(f"ETL skipped: {result.get('reason', '')}")
                elif etl_status not in {"ok", "loaded"}:
                    warnings.append(f"ETL {etl_status}: {result}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("ETL failed for %s", pdf_path)
                warnings.append(f"ETL failed: {exc}")

        # Pipeline 2: OpenViking vector index. Reuse the already-initialized
        # client from ResearchQAEngine so we don't collide on the OV lock.
        engine = get_engine()
        ov_client = getattr(engine, "client", None)
        if ov_client is None:
            errors.append("OpenViking client unavailable — RAG indexing skipped")
        else:
            try:
                from src.knowledge.ov_adapter import store_resource

                ov_uri = store_resource(ov_client, pdf_path, wait=req.wait)
            except Exception as exc:  # noqa: BLE001
                logger.exception("OV add_resource failed for %s", pdf_path)
                errors.append(f"RAG indexing failed: {exc}")

        # Only hard-fail if BOTH pipelines died (or RAG is essential and failed).
        if errors and etl_status not in {"ok", "loaded"}:
            return {
                "status": "error",
                "result": {
                    "errors": errors,
                    "warnings": warnings,
                    "etl_status": etl_status,
                    "root_uri": ov_uri,
                },
            }

        return {
            "status": "ok",
            "result": {
                "warnings": warnings + errors,
                "etl_status": etl_status,
                "root_uri": ov_uri,
                "source_name": req.source_name,
            },
        }

    # ---------------------------------------------------------------- OV fs probes
    # Minimal read-only OV HTTP surface so the vendored SPA's Resources
    # browser and Home dashboard have something to render. All endpoints
    # proxy into the same embedded SyncOpenViking instance held by the
    # engine — no separate OV server is spawned.

    def _require_ov() -> Any:
        client = getattr(get_engine(), "client", None)
        if client is None:
            raise HTTPException(status_code=503, detail="OpenViking client unavailable")
        return client

    def _ov_ok(result: Any) -> dict[str, Any]:
        return {"status": "ok", "result": result}

    def _ov_error(code: str, message: str, status_code: int = 500) -> dict[str, Any]:
        return {
            "status": "error",
            "error": {"code": code, "message": message},
        }, status_code

    @app.get("/api/v1/fs/ls")
    def fs_ls(
        uri: str,
        output: str = "original",
        show_all_hidden: bool = False,
        node_limit: int | None = None,
        limit: int | None = None,
        abs_limit: int = 256,
        recursive: bool = False,
        simple: bool = False,
    ) -> dict[str, Any]:
        client = _require_ov()
        kwargs = {
            "output": output,
            "show_all_hidden": show_all_hidden,
            "abs_limit": abs_limit,
            "recursive": recursive,
            "simple": simple,
        }
        if node_limit is not None:
            kwargs["node_limit"] = node_limit
        if limit is not None:
            kwargs["limit"] = limit
        try:
            result = client.ls(uri, **kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("fs.ls failed for uri=%s", uri)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return _ov_ok(result)

    @app.get("/api/v1/fs/tree")
    def fs_tree(
        uri: str,
        output: str = "original",
        show_all_hidden: bool = False,
        node_limit: int = 1000,
        abs_limit: int = 128,
        level_limit: int | None = None,
    ) -> dict[str, Any]:
        client = _require_ov()
        kwargs = {
            "output": output,
            "show_all_hidden": show_all_hidden,
            "node_limit": node_limit,
            "abs_limit": abs_limit,
        }
        if level_limit is not None:
            kwargs["level_limit"] = level_limit
        try:
            result = client.tree(uri, **kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("fs.tree failed for uri=%s", uri)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return _ov_ok(result)

    @app.get("/api/v1/fs/stat")
    def fs_stat(uri: str) -> dict[str, Any]:
        client = _require_ov()
        try:
            result = client.stat(uri)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return _ov_ok(result)

    @app.get("/api/v1/content/read")
    def content_read(uri: str, offset: int = 0, limit: int = -1) -> dict[str, Any]:
        client = _require_ov()
        try:
            content = client.read(uri, offset=offset, limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return _ov_ok({"content": content, "offset": offset, "limit": limit})

    @app.get("/api/v1/system/status")
    def system_status() -> dict[str, Any]:
        """Satisfies the vendored Home dashboard's /api/v1/system/status call.

        Returns whatever OV's ``get_status`` emits, plus our own fields
        (db stats + rag_enabled) so the Home page can show something
        taidi-specific."""
        client = _require_ov()
        try:
            ov_status = client.get_status()
            if hasattr(ov_status, "model_dump"):
                ov_status = ov_status.model_dump()
            elif hasattr(ov_status, "__dict__"):
                ov_status = dict(ov_status.__dict__)
        except Exception as exc:  # noqa: BLE001
            logger.exception("system.status failed")
            ov_status = {"error": str(exc)}

        try:
            with sqlite3.connect(DB_PATH) as conn:
                db_stats = conn.execute(
                    "SELECT COUNT(DISTINCT stock_code), COUNT(DISTINCT report_period), MAX(report_period) "
                    "FROM core_performance_indicators_sheet"
                ).fetchone()
            companies, periods, latest = db_stats or (0, 0, None)
        except Exception:  # noqa: BLE001
            companies, periods, latest = 0, 0, None

        return _ov_ok({
            "ov": ov_status,
            "taidi": {
                "company_count": companies or 0,
                "report_period_count": periods or 0,
                "latest_period": latest,
                "db_path": DB_PATH,
                "rag_enabled": True,
            },
            "user_id": "embedded",
        })

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/charts", StaticFiles(directory=str(CHART_DIR)), name="charts")

    if WEB_DIST_DIR.is_dir():
        assets = WEB_DIST_DIR / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str) -> FileResponse:
            candidate = WEB_DIST_DIR / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST_DIR / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

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

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Load .env up-front so /api/settings' mask readout and get_engine() both
# see the same environment. No-op on Railway where env vars already live
# in the OS environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend import chat_store
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


class _ChatSessionCreate(BaseModel):
    title: str = "新会话"
    id: str | None = None


class _ChatSessionPatch(BaseModel):
    title: str


class _ChatMessageAppend(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    sql: str | None = None
    chart_url: str | None = None
    chart_type: str | None = None
    needs_clarification: bool = False


def _mask_key(value: str) -> str:
    """Mask all but the last 4 chars of a secret."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


class _LLMSettings(BaseModel):
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None


class _VLMSettings(BaseModel):
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None


class SettingsUpdate(BaseModel):
    llm: _LLMSettings | None = None
    ov_vlm: _VLMSettings | None = None


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
    research_resource_count: int = 0
    financial_record_count: int = 0


def _count_ov_resources() -> int:
    """Cheap filesystem count of indexed research resources.

    OV stores each ingested PDF as a directory under
    ``.openviking/viking/default/resources/{sanitized_name}/``. Counting the
    top-level dirs gives an accurate indexed count without opening the OV
    client (which conflicts with vikingbot holding the LevelDB lock)."""
    from pathlib import Path
    resources_dir = Path(__file__).resolve().parent.parent / ".openviking" / "viking" / "default" / "resources"
    if not resources_dir.exists():
        return 0
    return sum(1 for p in resources_dir.iterdir() if p.is_dir())


def _resource_breakdown() -> dict[str, Any]:
    """Breakdown of indexed resources by 研报 category (个股 vs 行业).

    Reads a pre-built manifest at ``.openviking/resources_manifest.json``
    produced by ``scripts/build_resource_manifest.py``. Using a manifest
    (instead of re-deriving from 附件5 PDFs) means the deployed repo
    doesn't need the source PDFs present — Railway and any fresh clone
    get the breakdown straight from the committed JSON.

    Falls back to a filesystem cross-reference against the source PDF tree
    if the manifest is missing (dev workflow before the manifest is built).
    """
    from pathlib import Path
    import json
    import re
    root = Path(__file__).resolve().parent.parent
    resources_dir = root / ".openviking" / "viking" / "default" / "resources"
    manifest_path = root / ".openviking" / "resources_manifest.json"

    # Preferred path: use the committed manifest.
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            counts = {k: len(data.get(k, [])) for k in ("stock", "industry", "other")}
            return {"total": sum(counts.values()), "by_category": counts}
        except (OSError, ValueError):
            pass  # fall through to filesystem derivation

    # Fallback: derive from source PDFs if present.
    research_root = root / "data" / "sample" / "示例数据" / "附件5：研报数据"
    if not resources_dir.exists() or not research_root.exists():
        return {"total": _count_ov_resources(), "by_category": {"stock": 0, "industry": 0, "other": 0}}
    sanitize = re.compile(r"[^\w\u4e00-\u9fff]")
    cat_map: dict[str, str] = {}
    for sub_zh, label in (("个股研报", "stock"), ("行业研报", "industry")):
        for pdf in (research_root / sub_zh).glob("*.pdf"):
            key = sanitize.sub("", pdf.stem)
            cat_map[key] = label
    counts = {"stock": 0, "industry": 0, "other": 0}
    for rsrc_dir in resources_dir.iterdir():
        if not rsrc_dir.is_dir():
            continue
        name = rsrc_dir.name
        base = re.sub(r"_\d+$", "", name)
        cat = cat_map.get(base) or cat_map.get(name) or "other"
        counts[cat] += 1
    total = sum(counts.values())
    return {"total": total, "by_category": counts}


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

    @app.get("/api/stats/resources")
    def stats_resources() -> dict[str, Any]:
        """Breakdown of indexed 研报 resources for the home dashboard."""
        return _ov_ok(_resource_breakdown())

    @app.get("/api/stats", response_model=StatsResponse)
    def stats() -> StatsResponse:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT COUNT(DISTINCT stock_code), COUNT(DISTINCT report_period), MAX(report_period) "
                    "FROM core_performance_indicators_sheet"
                ).fetchone()
                # A "financial record" = one company's one period in the core table.
                # All 4 statement tables share this dimension so a single count is
                # representative; multiply by 4 if you want a per-cell total.
                record_rows = conn.execute(
                    "SELECT COUNT(*) FROM core_performance_indicators_sheet"
                ).fetchone()
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc
        company_count, period_count, latest = rows or (0, 0, None)
        record_count = (record_rows[0] if record_rows else 0) or 0
        return StatsResponse(
            company_count=company_count or 0,
            report_period_count=period_count or 0,
            latest_period=latest,
            db_path=DB_PATH,
            rag_enabled=_is_research_engine(get_engine()),
            research_resource_count=_count_ov_resources(),
            financial_record_count=record_count,
        )

    def _persist_exchange(session_id: str, question: str, response: AskResponse) -> None:
        """Persist user question + assistant answer into the chat store.

        Auto-creates the chat_sessions row on first turn, and titles it
        with the first 20 chars of the question."""
        try:
            if chat_store.get_session(session_id) is None:
                title = question.strip()[:20] or "新会话"
                chat_store.create_session(title=title, session_id=session_id)
            chat_store.append_message(session_id, role="user", content=question)
            chat_store.append_message(
                session_id,
                role="assistant",
                content=response.content or "",
                sql=response.sql,
                chart_url=response.chart_url,
                chart_type=response.chart_type,
                needs_clarification=response.needs_clarification,
            )
        except Exception:  # noqa: BLE001
            logger.exception("chat_store persist failed for session %s", session_id)

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        session_id, session = _get_or_create_session(req.session_id)
        session.conversation.add_user_message(req.question)
        engine = get_engine()
        if _is_research_engine(engine):
            response = _answer_with_research(engine, req, session_id, session)
        else:
            response = _answer_with_text2sql(engine, req, session_id, session)
        _persist_exchange(session_id, req.question, response)
        return response

    @app.post("/api/ask/stream")
    def ask_stream(req: AskRequest) -> StreamingResponse:
        """SSE variant of /api/ask — emits status events at each stage so
        the frontend can show 'analyzing → querying → rendering chart'
        progress, plus the final full response in a ``done`` event."""
        import json as _json

        def _event(event_type: str, data: dict[str, Any]) -> str:
            return f"event: {event_type}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        session_id, session = _get_or_create_session(req.session_id)

        def generate():
            try:
                session.conversation.add_user_message(req.question)
                yield _event("status", {"stage": "analyzing", "message": "正在理解问题…"})

                engine = get_engine()
                if _is_research_engine(engine):
                    route = engine.classify_intent(req.question)
                    yield _event("status", {"stage": "routed", "route": route, "message": f"路由：{route}"})

                    yield _event("status", {"stage": "querying", "message": "执行查询…"})
                    response = _answer_with_research(engine, req, session_id, session)
                else:
                    yield _event("status", {"stage": "querying", "message": "生成 SQL 并查询数据库…"})
                    response = _answer_with_text2sql(engine, req, session_id, session)

                if response.sql:
                    yield _event("sql", {"sql": response.sql})
                if response.chart_url:
                    yield _event("status", {"stage": "rendering", "message": "渲染图表…"})

                _persist_exchange(session_id, req.question, response)
                yield _event("done", response.model_dump())
            except Exception as exc:  # noqa: BLE001
                logger.exception("ask_stream failed")
                yield _event("error", {"message": str(exc)})

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable nginx/proxy buffering
            },
        )

    # ------------------------------------------------------------------
    # Persistent chat sessions (web UI session list)
    # ------------------------------------------------------------------
    chat_store.init_db()

    @app.get("/api/chat/sessions")
    def list_chat_sessions() -> dict[str, Any]:
        return {"sessions": [chat_store.session_to_dict(s) for s in chat_store.list_sessions()]}

    @app.post("/api/chat/sessions")
    def create_chat_session(
        req: _ChatSessionCreate = Body(default_factory=_ChatSessionCreate),
    ) -> dict[str, Any]:
        s = chat_store.create_session(title=req.title, session_id=req.id)
        return chat_store.session_to_dict(s)

    @app.patch("/api/chat/sessions/{session_id}")
    def rename_chat_session(session_id: str, req: _ChatSessionPatch = Body(...)) -> dict[str, Any]:
        s = chat_store.rename_session(session_id, req.title)
        if s is None:
            raise HTTPException(status_code=404, detail="session not found")
        return chat_store.session_to_dict(s)

    @app.delete("/api/chat/sessions/{session_id}")
    def delete_chat_session(session_id: str) -> dict[str, bool]:
        ok = chat_store.delete_session(session_id)
        _sessions.pop(session_id, None)
        return {"ok": ok}

    @app.get("/api/chat/sessions/{session_id}/messages")
    def list_chat_messages(session_id: str) -> dict[str, Any]:
        if chat_store.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="session not found")
        messages = chat_store.list_messages(session_id)
        return {"messages": [chat_store.message_to_dict(m) for m in messages]}

    @app.post("/api/chat/sessions/{session_id}/messages")
    def append_chat_message(
        session_id: str, req: _ChatMessageAppend = Body(...),
    ) -> dict[str, Any]:
        if chat_store.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="session not found")
        msg = chat_store.append_message(
            session_id,
            role=req.role,
            content=req.content,
            sql=req.sql,
            chart_url=req.chart_url,
            chart_type=req.chart_type,
            needs_clarification=req.needs_clarification,
        )
        return chat_store.message_to_dict(msg)

    @app.put("/api/chat/sessions/{session_id}/messages")
    def replace_chat_messages(
        session_id: str, messages: list[dict[str, Any]] = Body(...),
    ) -> dict[str, bool]:
        """Replace all messages for a session (used by frontend after edit/delete)."""
        session = chat_store.get_session(session_id)
        if session is None:
            # Auto-title from the first user message
            title = "新会话"
            for m in messages:
                if m.get("role") == "user" and m.get("content"):
                    text = str(m["content"]).strip()
                    title = text[:20] + ("…" if len(text) > 20 else "")
                    break
            chat_store.create_session(session_id=session_id, title=title)
        elif session.title == "新会话":
            # Rename if still default
            for m in messages:
                if m.get("role") == "user" and m.get("content"):
                    text = str(m["content"]).strip()
                    chat_store.rename_session(session_id, text[:20] + ("…" if len(text) > 20 else ""))
                    break
        chat_store.replace_messages(session_id, messages)
        return {"ok": True}

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

    _OV_HTTP_URL = os.environ.get("OV_HTTP_URL", "http://127.0.0.1:18792")
    _ov_http_client: Any = None

    class _OVProxyClient:
        """Thin wrapper that translates SyncOpenViking-style method calls
        (client.ls(uri, **kwargs) / client.find(query, ...)) into HTTP calls
        against a running openviking-server on :18792.

        Lets the existing fs_ls / content_read / search routes keep using
        client.<method>(...) without each caller having to know about HTTP.
        """

        def __init__(self, base_url: str) -> None:
            import httpx
            self._c = httpx.Client(base_url=base_url, timeout=30.0)

        def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
            r = self._c.get(path, params=params or {})
            r.raise_for_status()
            data = r.json()
            return data.get("result", data)

        def _post(self, path: str, json: dict[str, Any]) -> Any:
            r = self._c.post(path, json=json)
            r.raise_for_status()
            data = r.json()
            return data.get("result", data)

        # Methods the routes call:
        def ls(self, uri: str, **kwargs: Any) -> Any:
            params = {"uri": uri, **{k: v for k, v in kwargs.items() if v is not None and not isinstance(v, bool)}}
            for k, v in kwargs.items():
                if isinstance(v, bool):
                    params[k] = "true" if v else "false"
            return self._get("/api/v1/fs/ls", params=params)

        def tree(self, uri: str, **kwargs: Any) -> Any:
            params = {"uri": uri, **{k: v for k, v in kwargs.items() if v is not None and not isinstance(v, bool)}}
            for k, v in kwargs.items():
                if isinstance(v, bool):
                    params[k] = "true" if v else "false"
            return self._get("/api/v1/fs/tree", params=params)

        def stat(self, uri: str) -> Any:
            return self._get("/api/v1/fs/stat", params={"uri": uri})

        def read_content(self, uri: str, offset: int = 0, limit: int = -1) -> Any:
            return self._get("/api/v1/content/read", params={"uri": uri, "offset": offset, "limit": limit})

        def find(self, query: str, **kwargs: Any) -> Any:
            payload = {"query": query, **{k: v for k, v in kwargs.items() if v is not None}}
            return self._post("/api/v1/search/find", json=payload)

        def search(self, query: str, **kwargs: Any) -> Any:
            payload = {"query": query, **{k: v for k, v in kwargs.items() if v is not None}}
            return self._post("/api/v1/search/search", json=payload)

    def _require_ov() -> Any:
        """Prefer the locally-running openviking-server over the engine's
        embedded client — vikingbot holds the LevelDB lock in-process, so
        FastAPI can't open a second embedded client on the same data dir.
        Falls back to engine.client if the HTTP server is down.
        """
        nonlocal _ov_http_client
        if _ov_http_client is None:
            try:
                import httpx
                with httpx.Client(base_url=_OV_HTTP_URL, timeout=3.0) as c:
                    resp = c.get("/health")
                    if resp.status_code == 200:
                        _ov_http_client = _OVProxyClient(_OV_HTTP_URL)
            except Exception:  # noqa: BLE001
                pass
        if _ov_http_client is not None:
            return _ov_http_client
        # Fallback: engine-embedded client (works only if vikingbot not holding
        # the lock — e.g. in headless CI).
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

    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        """Snapshot of live-editable settings with secrets masked."""
        return {
            "llm": {
                "api_base": os.environ.get("LLM_API_BASE", ""),
                "api_key_masked": _mask_key(os.environ.get("LLM_API_KEY", "")),
                "model": os.environ.get("LLM_MODEL", ""),
            },
            "ov_vlm": {
                "api_base": os.environ.get("OV_VLM_API_BASE", ""),
                "api_key_masked": _mask_key(os.environ.get("OV_VLM_API_KEY", "")),
                "model": os.environ.get("OV_VLM_MODEL", ""),
            },
            "ov_embedding": {
                "api_base": os.environ.get("OV_EMBEDDING_API_BASE", ""),
                "api_key_masked": _mask_key(os.environ.get("OV_EMBEDDING_API_KEY", "")),
                "model": os.environ.get("OV_EMBEDDING_MODEL", ""),
                "dimension": int(os.environ.get("OV_EMBEDDING_DIMENSION", "0") or "0"),
            },
        }

    @app.post("/api/settings")
    def update_settings(req: SettingsUpdate) -> dict[str, Any]:
        """Apply LLM / OV_VLM edits to the process env and reset the
        singleton engine so the next /api/ask rebuilds it with the new
        values. Embedding is intentionally not editable — changing it
        invalidates the existing vector index."""
        changed: list[str] = []

        if req.llm:
            if req.llm.api_base is not None:
                os.environ["LLM_API_BASE"] = req.llm.api_base
                changed.append("LLM_API_BASE")
            if req.llm.api_key:
                os.environ["LLM_API_KEY"] = req.llm.api_key
                changed.append("LLM_API_KEY")
            if req.llm.model is not None:
                os.environ["LLM_MODEL"] = req.llm.model
                changed.append("LLM_MODEL")

        if req.ov_vlm:
            if req.ov_vlm.api_base is not None:
                os.environ["OV_VLM_API_BASE"] = req.ov_vlm.api_base
                changed.append("OV_VLM_API_BASE")
            if req.ov_vlm.api_key:
                os.environ["OV_VLM_API_KEY"] = req.ov_vlm.api_key
                changed.append("OV_VLM_API_KEY")
            if req.ov_vlm.model is not None:
                os.environ["OV_VLM_MODEL"] = req.ov_vlm.model
                changed.append("OV_VLM_MODEL")

        # Force next get_engine() to rebuild with the new env.
        global _engine
        _engine = None

        return {"status": "ok", "changed": changed}

    # ------------------------------------------------------------------
    # OV dashboard stubs — so the Home page renders instead of skeleton
    # ------------------------------------------------------------------

    @app.get("/api/v1/observer/system")
    def observer_system() -> dict[str, Any]:
        """Real health checks for each component in our architecture."""
        components: dict[str, dict[str, Any]] = {}

        # 数据库 — SQLite finance.db
        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT COUNT(DISTINCT stock_code) FROM core_performance_indicators_sheet"
                ).fetchone()
            components["database"] = {"is_healthy": True, "companies": row[0] if row else 0}
        except Exception as exc:
            components["database"] = {"is_healthy": False, "error": str(exc)}

        # LLM — API 可用
        try:
            from src.llm.client import LLMClient
            llm = LLMClient.from_env()
            components["llm"] = {"is_healthy": True, "model": llm.model}
        except Exception as exc:
            components["llm"] = {"is_healthy": False, "error": str(exc)}

        # VikingBot — 聊天 Agent 网关
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:18790/bot/v1/health", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                components["vikingbot"] = {"is_healthy": resp.status == 200}
        except Exception as exc:
            components["vikingbot"] = {"is_healthy": False, "error": str(exc)}

        # OpenViking — 上下文数据库（由 vikingbot 内部管理，
        # 我们不另开客户端避免 LevelDB 锁冲突。vikingbot 在就说明 OV 在）
        components["openviking"] = components.get("vikingbot", {"is_healthy": False})

        # MCP — 财报工具（vikingbot 启动时注册，vikingbot 在就在）
        components["mcp"] = components.get("vikingbot", {"is_healthy": False})

        all_healthy = all(c.get("is_healthy") for c in components.values())
        return _ov_ok({"is_healthy": all_healthy, "components": components})

    @app.get("/api/v1/stats/memories")
    def stats_memories() -> dict[str, Any]:
        # OV memory stats not accessible from this process (vikingbot holds the lock).
        # TODO: proxy via vikingbot API when it exposes this.
        return _ov_ok({"total_memories": 0, "by_type": {}})

    @app.get("/api/v1/debug/vector/count")
    def debug_vector_count() -> dict[str, Any]:
        # Same — vector count lives in vikingbot's OV instance.
        return _ov_ok({"count": 0})

    @app.get("/api/v1/tasks")
    def list_tasks() -> dict[str, Any]:
        return _ov_ok([])

    @app.get("/api/v1/sessions")
    def list_ov_sessions() -> dict[str, Any]:
        # Return our chat sessions so the dashboard shows them
        sessions_list = chat_store.list_sessions()
        return _ov_ok([
            {"session_id": s.id, "uri": f"/sessions/{s.id}", "is_dir": False}
            for s in sessions_list
        ])

    @app.get("/api/v1/stats/tokens")
    def stats_tokens() -> dict[str, Any]:
        return {
            "total_tokens": 0,
            "llm": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            "embedding": {"total_tokens": 0},
        }

    @app.get("/api/v1/system/status")
    def system_status() -> dict[str, Any]:
        """Satisfies the vendored Home dashboard's /api/v1/system/status call.

        Returns whatever OV's ``get_status`` emits, plus our own fields
        (db stats + rag_enabled) so the Home page can show something
        taidi-specific."""
        # Don't open OV client here (vikingbot holds the LevelDB lock).
        # Just check what we CAN check from this process.
        try:
            with sqlite3.connect(DB_PATH) as conn:
                db_stats = conn.execute(
                    "SELECT COUNT(DISTINCT stock_code), COUNT(DISTINCT report_period), MAX(report_period) "
                    "FROM core_performance_indicators_sheet"
                ).fetchone()
                record_rows = conn.execute(
                    "SELECT COUNT(*) FROM core_performance_indicators_sheet"
                ).fetchone()
            companies, periods, latest = db_stats or (0, 0, None)
            records = (record_rows[0] if record_rows else 0) or 0
            db_ok = True
        except Exception:  # noqa: BLE001
            companies, periods, latest = 0, 0, None
            records = 0
            db_ok = False

        # Check vikingbot alive → implies OV is initialized
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:18790/bot/v1/health", timeout=2) as r:
                vb_ok = r.status == 200
        except Exception:
            vb_ok = False

        research_count = _count_ov_resources()
        return _ov_ok({
            "initialized": db_ok and vb_ok,
            "taidi": {
                "company_count": companies or 0,
                "report_period_count": periods or 0,
                "latest_period": latest,
                "db_path": DB_PATH,
                "rag_enabled": vb_ok,
                "research_resource_count": research_count,
                "financial_record_count": records,
            },
            "user_id": "embedded",
        })

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/charts", StaticFiles(directory=str(CHART_DIR)), name="charts")

    # Serve research PDFs under /papers so the chat UI can link references
    # directly to the source file. paper_path values in xlsx are stored as
    # "./附件5：研报数据/..." per submission spec, and the actual bytes live
    # under data/sample/示例数据/. Mount the parent so the relative path
    # "附件5：研报数据/xxx.pdf" resolves.
    PAPERS_DIR = ROOT_DIR / "data" / "sample" / "示例数据"
    if PAPERS_DIR.is_dir():
        app.mount("/papers", StaticFiles(directory=str(PAPERS_DIR)), name="papers")

    # ------------------------------------------------------------------
    # Reverse proxy: /bot/v1/* → vikingbot gateway (like OV server does)
    # ------------------------------------------------------------------
    import httpx

    VIKINGBOT_URL = os.getenv("VIKINGBOT_URL", "http://localhost:18790")
    _proxy_client = httpx.AsyncClient(base_url=VIKINGBOT_URL, timeout=300.0)

    INTERNAL_BOT_KEY = os.getenv("INTERNAL_BOT_KEY", "taidi-bot-key-2026")

    @app.api_route("/bot/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def bot_proxy(path: str, request: Request) -> StreamingResponse:
        """Reverse-proxy /bot/v1/* to vikingbot gateway.
        Injects the internal api key so the browser doesn't need to know it."""
        url = f"/bot/v1/{path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        # Always override with our internal key — same-origin means no user auth
        headers["x-api-key"] = INTERNAL_BOT_KEY
        body = await request.body()

        req = _proxy_client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        )
        resp = await _proxy_client.send(req, stream=True)

        async def stream_body():
            async for chunk in resp.aiter_bytes():
                yield chunk
            await resp.aclose()

        return StreamingResponse(
            stream_body(),
            status_code=resp.status_code,
            headers={
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("transfer-encoding", "content-encoding", "content-length")
            },
            media_type=resp.headers.get("content-type"),
        )

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

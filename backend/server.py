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

from fastapi import FastAPI, HTTPException
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

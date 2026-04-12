"""FastAPI backend serving the taidi_bei web frontend.

Endpoints (all under ``/api``):
- ``POST /api/ask``  — answer a question via Text2SQL + optional chart
- ``GET  /api/stats`` — basic DB stats for the home dashboard
- ``GET  /api/health`` — liveness probe

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
from typing import Any

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


class AskResponse(BaseModel):
    session_id: str
    content: str
    sql: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    chart_url: str | None = None
    chart_type: str | None = None
    needs_clarification: bool = False
    error: str | None = None


class StatsResponse(BaseModel):
    company_count: int
    report_period_count: int
    latest_period: str | None
    db_path: str


_engine: Text2SQLEngine | None = None
_sessions: dict[str, Session] = {}


def get_engine() -> Text2SQLEngine:
    global _engine
    if _engine is None:
        llm_client = None
        try:
            from src.llm.client import LLMClient

            llm_client = LLMClient.from_env()
            logger.info("LLMClient enabled for Text2SQLEngine")
        except Exception as exc:
            logger.warning("LLM disabled, falling back to heuristic: %s", exc)
        _engine = Text2SQLEngine(DB_PATH, llm_client=llm_client)
    return _engine


def _get_or_create_session(session_id: str | None) -> tuple[str, Session]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    new_id = session_id or uuid.uuid4().hex
    session = Session(conversation=ConversationManager())
    _sessions[new_id] = session
    return new_id, session


def _render_chart_for(question: str, rows: list[dict[str, Any]], request_id: str) -> tuple[str | None, str | None]:
    chart_data, chart_vf = safe_chart_data(rows)
    if not chart_data:
        return None, None
    chart_type = select_chart_type(question, chart_data)
    if chart_type == "none":
        return None, chart_type
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHART_DIR / f"ask_{request_id}.jpg"
    image = render_chart(chart_type, chart_data, str(out_path), question, value_field=chart_vf)
    if not image:
        return None, chart_type
    # Expose via /charts/* mount below.
    return f"/charts/{Path(image).name}", chart_type


def create_app() -> FastAPI:
    app = FastAPI(title="财报智能问数", version="1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
        )

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        session_id, session = _get_or_create_session(req.session_id)
        session.conversation.add_user_message(req.question)

        engine = get_engine()
        result = engine.query(req.question, session.conversation)

        if result.needs_clarification:
            content = result.clarification_question or "请补充信息。"
            session.conversation.add_assistant_message(content)
            return AskResponse(
                session_id=session_id,
                content=content,
                sql=result.sql,
                rows=[],
                needs_clarification=True,
            )

        if result.error:
            session.conversation.add_assistant_message(result.error)
            return AskResponse(
                session_id=session_id,
                content=result.error,
                sql=result.sql,
                rows=[],
                error=result.error,
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

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/charts", StaticFiles(directory=str(CHART_DIR)), name="charts")

    if WEB_DIST_DIR.is_dir():
        assets = WEB_DIST_DIR / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str) -> FileResponse:
            # Serve asset files directly, else fall back to index.html (SPA history).
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

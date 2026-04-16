"""SQLite-backed persistent storage for chat sessions and messages.

The existing ``_sessions`` dict in ``server.py`` holds in-memory
``ConversationManager`` slot state for the current process. This module
adds *persistent* metadata + message history so the web UI's session
list survives server restarts and can list past conversations.

Two tables in a dedicated DB file (``data/db/chat.db``):

- ``chat_sessions(id, title, created_at, updated_at)``
- ``chat_messages(id, session_id, role, content, sql, chart_url,
   chart_type, needs_clarification, created_at)``
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CHAT_DB = ROOT_DIR / "data" / "db" / "chat.db"
CHAT_DB_PATH = Path(os.getenv("CHAT_DB_PATH", str(DEFAULT_CHAT_DB)))

_lock = threading.Lock()


@dataclass
class ChatSession:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass
class ChatMessage:
    id: str
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    sql: str | None = None
    chart_url: str | None = None
    chart_type: str | None = None
    needs_clarification: bool = False
    created_at: str = field(default_factory=lambda: _now())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    CHAT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHAT_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if missing. Safe to call repeatedly."""
    with _lock, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id                   TEXT PRIMARY KEY,
                session_id           TEXT NOT NULL,
                role                 TEXT NOT NULL,
                content              TEXT NOT NULL,
                sql                  TEXT,
                chart_url            TEXT,
                chart_type           TEXT,
                needs_clarification  INTEGER NOT NULL DEFAULT 0,
                created_at           TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at)"
        )


def list_sessions() -> list[ChatSession]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [ChatSession(**dict(r)) for r in rows]


def create_session(title: str = "新会话", session_id: str | None = None) -> ChatSession:
    sid = session_id or _new_id("s")
    now = _now()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO chat_sessions(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, title, now, now),
        )
    return ChatSession(id=sid, title=title, created_at=now, updated_at=now)


def get_session(session_id: str) -> ChatSession | None:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return ChatSession(**dict(row)) if row else None


def rename_session(session_id: str, title: str) -> ChatSession | None:
    now = _now()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id),
        )
        if cur.rowcount == 0:
            return None
    return get_session(session_id)


def touch_session(session_id: str) -> None:
    now = _now()
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )


def delete_session(session_id: str) -> bool:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cur = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0


def list_messages(session_id: str) -> list[ChatMessage]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, role, content, sql, chart_url, chart_type,
                   needs_clarification, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    out: list[ChatMessage] = []
    for r in rows:
        d = dict(r)
        d["needs_clarification"] = bool(d["needs_clarification"])
        out.append(ChatMessage(**d))
    return out


def append_message(
    session_id: str,
    role: str,
    content: str,
    *,
    sql: str | None = None,
    chart_url: str | None = None,
    chart_type: str | None = None,
    needs_clarification: bool = False,
) -> ChatMessage:
    msg = ChatMessage(
        id=_new_id("m"),
        session_id=session_id,
        role=role,
        content=content,
        sql=sql,
        chart_url=chart_url,
        chart_type=chart_type,
        needs_clarification=needs_clarification,
    )
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages
                (id, session_id, role, content, sql, chart_url, chart_type,
                 needs_clarification, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.session_id,
                msg.role,
                msg.content,
                msg.sql,
                msg.chart_url,
                msg.chart_type,
                1 if msg.needs_clarification else 0,
                msg.created_at,
            ),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (msg.created_at, session_id),
        )
    return msg


def replace_messages(session_id: str, messages: list[dict]) -> None:
    """Replace all messages for a session with the given list."""
    now = _now()
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        for m in messages:
            mid = m.get("id") or _new_id("m")
            conn.execute(
                """
                INSERT INTO chat_messages
                    (id, session_id, role, content, sql, chart_url, chart_type,
                     needs_clarification, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    session_id,
                    m.get("role", "user"),
                    m.get("content", ""),
                    m.get("sql"),
                    m.get("chart_url") or m.get("chartUrl"),
                    m.get("chart_type") or m.get("chartType"),
                    1 if m.get("needs_clarification") or m.get("needsClarification") else 0,
                    m.get("created_at") or m.get("createdAt") or now,
                ),
            )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )


def session_to_dict(s: ChatSession) -> dict:
    return asdict(s)


def message_to_dict(m: ChatMessage) -> dict:
    return asdict(m)


__all__ = [
    "ChatSession",
    "ChatMessage",
    "init_db",
    "list_sessions",
    "create_session",
    "get_session",
    "rename_session",
    "touch_session",
    "delete_session",
    "list_messages",
    "append_message",
    "session_to_dict",
    "message_to_dict",
]

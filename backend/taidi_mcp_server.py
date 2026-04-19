#!/usr/bin/env python3
"""Taidi Finance MCP Server — exposes the financial-report QA engine as
MCP tools so VikingBot (or any MCP client) can call them.

Tools:
  query_finance(question)  — NL → SQL → answer + optional chart
  list_tables()            — show the 4 official DB tables and key fields
  execute_sql(sql)         — run raw SQL against the finance DB

Run:
  python -m backend.taidi_mcp_server          # stdio transport (for vikingbot)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports resolve.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("taidi_mcp")

DB_PATH = os.getenv("SQLITE_DB_PATH", str(ROOT_DIR / "data" / "db" / "finance.db"))
CHART_DIR = ROOT_DIR / "result"

# ---------------------------------------------------------------------------
# Lazy engine singleton
# ---------------------------------------------------------------------------

_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine

    from src.llm.client import LLMClient
    from src.query.text2sql import Text2SQLEngine

    try:
        llm = LLMClient.from_env()
    except Exception:
        llm = None
        logger.warning("LLM unavailable — engine will use heuristic fallback")

    # Try research engine first (SQL + RAG)
    try:
        from src.knowledge.ov_adapter import init_client
        from src.knowledge.research_qa import ResearchQAEngine

        ov_client = init_client()
        _engine = ResearchQAEngine(db_path=DB_PATH, client=ov_client, llm_client=llm)
        logger.info("ResearchQAEngine ready (SQL + RAG)")
    except Exception:
        _engine = Text2SQLEngine(DB_PATH, llm_client=llm)
        logger.info("Text2SQLEngine ready (SQL only)")

    return _engine


# ---------------------------------------------------------------------------
# Chart + answer helpers (reused from server.py logic)
# ---------------------------------------------------------------------------


def _render_chart(question: str, rows: list[dict]) -> tuple[str | None, str | None]:
    """Try to render a chart; return (chart_url, chart_type)."""
    from src.query.chart import render_chart, safe_chart_data, select_chart_type

    chart_data, _ = safe_chart_data(rows)
    if not chart_data:
        return None, None
    chart_type = select_chart_type(question, chart_data)
    if not chart_type or chart_type == "none":
        return None, chart_type
    import uuid as _uuid

    request_id = _uuid.uuid4().hex[:8]
    output_path = f"result/mcp_{request_id}.jpg"
    chart_url = render_chart(chart_type, chart_data, output_path, title=question)
    if chart_url:
        chart_url = f"/charts/{Path(chart_url).name}"
    return chart_url, chart_type


def _answer_question(question: str) -> dict:
    """Run the full QA pipeline and return a JSON-serializable dict."""
    from src.query.answer import build_answer_content

    engine = _get_engine()

    if engine.__class__.__name__ == "ResearchQAEngine":
        result = engine.answer_question(question)
        rows = result.chart_rows or []
        chart_url, chart_type = _render_chart(question, rows)
        # Build source info
        sources = []
        if result.sql:
            sources.append(f"SQL查询: {result.sql}")
        for r in getattr(result, "references", []):
            sources.append(f"来源文档: {r.paper_path}" + (f" — {r.text[:80]}" if r.text else ""))
        return {
            "route": result.route,
            "content": result.answer,
            "sql": result.sql or None,
            "rows": rows[:20],
            "chart_url": chart_url,
            "chart_type": chart_type or result.chart_type,
            "sources": sources,
        }

    # Text2SQLEngine path
    result = engine.query(question)
    rows = result.rows
    content = build_answer_content(question, rows, intent=result.intent)
    chart_url, chart_type = _render_chart(question, rows)

    # Build source info from SQL
    sources = []
    if result.sql:
        # Extract table names from SQL
        import re
        tables_used = re.findall(r'FROM\s+(\w+)', result.sql, re.IGNORECASE)
        tables_used += re.findall(r'JOIN\s+(\w+)', result.sql, re.IGNORECASE)
        if tables_used:
            sources.append(f"数据来源: {', '.join(set(tables_used))}")
        sources.append(f"SQL: {result.sql}")
    if rows:
        sources.append(f"查询到 {len(rows)} 条记录")

    return {
        "route": "sql",
        "content": content,
        "sql": result.sql,
        "rows": rows[:20],
        "chart_url": chart_url,
        "chart_type": chart_type,
        "sources": sources,
    }


def _list_tables() -> str:
    """Return human-readable schema description of the 4 finance tables."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in cursor.fetchall()]

    lines = ["财报数据库包含以下表：\n"]
    with sqlite3.connect(DB_PATH) as conn:
        for table in tables:
            cursor = conn.execute(f"PRAGMA table_info([{table}])")
            cols = [(r[1], r[2]) for r in cursor.fetchall()]
            lines.append(f"## {table}")
            lines.append(f"字段数: {len(cols)}")
            col_strs = [f"  - {name} ({typ})" for name, typ in cols[:15]]
            if len(cols) > 15:
                col_strs.append(f"  ...及其他 {len(cols) - 15} 个字段")
            lines.append("\n".join(col_strs))
            lines.append("")
    return "\n".join(lines)


def _execute_sql(sql_text: str) -> str:
    """Execute a raw SQL query and return results with source info."""
    import re
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql_text)
        rows = [dict(r) for r in cursor.fetchall()[:50]]

    tables_used = re.findall(r'FROM\s+(\w+)', sql_text, re.IGNORECASE)
    tables_used += re.findall(r'JOIN\s+(\w+)', sql_text, re.IGNORECASE)

    result = {
        "rows": rows,
        "row_count": len(rows),
        "sources": [
            f"数据来源: {', '.join(set(tables_used))}" if tables_used else "直接SQL查询",
            f"SQL: {sql_text}",
            f"返回 {len(rows)} 条记录",
        ],
    }
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------


def main():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.error(
            "mcp package not installed. Run: pip install 'mcp[cli]'"
        )
        sys.exit(1)

    mcp = FastMCP(
        "taidi-finance",
        instructions=(
            "中药上市公司财报智能问数助手。可以查询财报数据库（四张表：核心指标表、"
            "资产负债表、利润表、现金流量表），支持自然语言转 SQL 查询、图表渲染、"
            "以及研报 RAG 检索。回答问题时请使用 query_finance 工具。"
        ),
    )

    @mcp.tool()
    def query(question: str) -> str:
        """用自然语言查询中药上市公司的财报数据。

        输入一个关于财报数据的自然语言问题（如"华润三九 2024 年净利润同比是多少"），
        系统会自动生成 SQL、查询数据库并返回结构化回答，可能包含图表。

        Args:
            question: 自然语言财报问题
        """
        try:
            result = _answer_question(question)
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    @mcp.tool()
    def tables() -> str:
        """列出财报数据库的所有表和字段信息。

        在不确定数据库结构时使用，了解可以查询哪些数据。"""
        try:
            return _list_tables()
        except Exception as exc:
            return f"Error: {exc}"

    @mcp.tool()
    def sql(sql: str) -> str:
        """直接执行 SQL 查询并返回结果。

        当 query_finance 工具不够灵活时，可以手写 SQL 查询。
        数据库是 SQLite，四张表的字段信息可用 list_tables 查看。

        Args:
            sql: 要执行的 SQL 查询语句（只读，SELECT 语句）
        """
        if not sql.strip().upper().startswith("SELECT"):
            return "Error: 只允许 SELECT 查询"
        try:
            return _execute_sql(sql)
        except Exception as exc:
            return f"SQL Error: {exc}"

    @mcp.tool()
    def import_pdf(temp_file_id: str) -> str:
        """将上传的 PDF 财报导入数据库。

        用户通过聊天上传 PDF 后，系统返回 temp_file_id。调用此工具将 PDF
        中的财报数据提取并导入 SQLite 数据库，之后可用 query 或 sql 工具查询。
        同时会将 PDF 存入 OpenViking 向量库供 RAG 检索。

        Args:
            temp_file_id: 文件上传后返回的临时文件 ID
        """
        from pathlib import Path as _Path

        tmp_dir = ROOT_DIR / "data" / "tmp_uploads" / temp_file_id
        if not tmp_dir.is_dir():
            return json.dumps({"error": f"temp_file_id '{temp_file_id}' 不存在"}, ensure_ascii=False)

        files = [p for p in tmp_dir.iterdir() if p.is_file()]
        if not files:
            return json.dumps({"error": "上传目录为空"}, ensure_ascii=False)

        pdf_path = files[0]
        results = {"file": pdf_path.name, "etl": None, "ov": None}

        # ETL: PDF → SQLite
        if pdf_path.suffix.lower() == ".pdf":
            try:
                from src.etl.loader import ETLLoader
                loader = ETLLoader(_Path(DB_PATH))
                etl_result = loader.load_pdf(pdf_path)
                results["etl"] = etl_result.get("status", "unknown")
                if etl_result.get("status") in ("ok", "loaded"):
                    results["etl_detail"] = "财报数据已导入数据库，可以用 query 或 sql 工具查询"
                else:
                    results["etl_detail"] = f"ETL 状态: {etl_result}"
            except Exception as exc:
                results["etl"] = "error"
                results["etl_detail"] = str(exc)
        else:
            results["etl"] = "skipped"
            results["etl_detail"] = f"非 PDF 文件 ({pdf_path.suffix})，跳过 ETL"

        # OV: 向量入库
        try:
            engine = _get_engine()
            ov_client = getattr(engine, "client", None)
            if ov_client:
                from src.knowledge.ov_adapter import store_resource
                ov_uri = store_resource(ov_client, pdf_path)
                results["ov"] = "ok"
                results["ov_uri"] = ov_uri
            else:
                results["ov"] = "skipped"
                results["ov_detail"] = "OpenViking 客户端不可用"
        except Exception as exc:
            results["ov"] = "error"
            results["ov_detail"] = str(exc)

        return json.dumps(results, ensure_ascii=False, indent=2, default=str)

    logger.info("Taidi Finance MCP server starting (stdio transport)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

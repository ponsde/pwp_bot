"""Two-step Text2SQL engine for financial QA."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.prompts.loader import load_prompt
from src.query.conversation import ConversationManager

CREATE_TABLE_SQL = """
CREATE TABLE core_performance_indicators_sheet (
    serial_number INTEGER,
    stock_code TEXT,
    stock_abbr TEXT,
    report_period TEXT,
    report_year INTEGER,
    revenue REAL,
    net_profit REAL
);
CREATE TABLE balance_sheet (
    serial_number INTEGER,
    stock_code TEXT,
    stock_abbr TEXT,
    report_period TEXT,
    report_year INTEGER,
    total_assets REAL,
    total_liabilities REAL,
    total_equity REAL
);
CREATE TABLE income_sheet (
    serial_number INTEGER,
    stock_code TEXT,
    stock_abbr TEXT,
    report_period TEXT,
    report_year INTEGER,
    operating_revenue REAL,
    total_profit REAL,
    net_profit REAL
);
CREATE TABLE cash_flow_sheet (
    serial_number INTEGER,
    stock_code TEXT,
    stock_abbr TEXT,
    report_period TEXT,
    report_year INTEGER,
    net_cash_flow REAL
);
""".strip()

FIELD_CATALOG = {
    "core_performance_indicators_sheet": ["revenue", "net_profit"],
    "balance_sheet": ["total_assets", "total_liabilities", "total_equity"],
    "income_sheet": ["operating_revenue", "total_profit", "net_profit"],
    "cash_flow_sheet": ["net_cash_flow"],
}


class UserFacingError(Exception):
    pass


@dataclass
class QueryResult:
    sql: str | None
    rows: list[dict[str, Any]]
    intent: dict[str, Any]
    error: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


class Text2SQLEngine:
    def __init__(self, db_path: str, llm_client: Any | None = None):
        self.db_path = db_path
        self.llm_client = llm_client

    def analyze(self, question: str, conversation: ConversationManager | None = None) -> dict[str, Any]:
        conversation_text = conversation.render() if conversation else ""
        if self.llm_client:
            prompt = load_prompt(
                "seek_table.md",
                field_catalog=json.dumps(FIELD_CATALOG, ensure_ascii=False),
                conversation=conversation_text,
                question=question,
            )
            raw = self.llm_client.complete(prompt)
            intent = self._parse_json(raw)
        else:
            intent = self._heuristic_intent(question, conversation_text)
        self._validate_intent(intent)
        return intent

    def generate_sql(self, question: str, intent: dict[str, Any]) -> str:
        if self.llm_client:
            prompt = load_prompt(
                "generate_sql.md",
                schema_sql=CREATE_TABLE_SQL,
                intent_json=json.dumps(intent, ensure_ascii=False),
                question=question,
            )
            raw = self.llm_client.complete(prompt)
            sql = self._extract_sql(raw)
        else:
            sql = self._heuristic_sql(intent)
        self._ensure_standard_report_period(sql)
        return sql

    def query(self, question: str, conversation: ConversationManager | None = None) -> QueryResult:
        intent = self.analyze(question, conversation)
        manager = conversation or ConversationManager()
        missing = manager.missing_slots(intent)
        if missing:
            clarification = self._clarify(question, missing, manager)
            return QueryResult(
                sql=None,
                rows=[],
                intent=intent,
                needs_clarification=True,
                clarification_question=clarification,
            )
        try:
            sql = self.generate_sql(question, intent)
            rows = self._execute_with_retry(sql, question, intent)
            if not rows:
                return QueryResult(sql=sql, rows=[], intent=intent, error="未查询到符合条件的数据。")
            return QueryResult(sql=sql, rows=rows, intent=intent)
        except UserFacingError as exc:
            return QueryResult(sql=None, rows=[], intent=intent, error=str(exc))

    def _execute_with_retry(self, sql: str, question: str, intent: dict[str, Any]) -> list[dict[str, Any]]:
        errors: list[str] = []
        current_sql = sql
        for _ in range(3):
            try:
                return self._execute_sql(current_sql)
            except sqlite3.DatabaseError as exc:
                errors.append(str(exc))
                if self.llm_client:
                    current_sql = self.generate_sql(f"{question}\n上次SQL报错：{exc}", intent)
                else:
                    current_sql = self._repair_sql(current_sql, str(exc))
        raise UserFacingError(f"SQL 执行失败：{'; '.join(errors)}")

    def _execute_sql(self, sql: str) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _validate_intent(self, intent: dict[str, Any]) -> None:
        if not isinstance(intent, dict):
            raise UserFacingError("无法识别查询意图。")
        for key in ["tables", "fields", "companies", "periods"]:
            intent.setdefault(key, [])
        for period in intent["periods"]:
            if not re.fullmatch(r"\d{4}(FY|Q1|HY|Q3)", period):
                raise UserFacingError(f"报告期格式不正确：{period}")

    def _heuristic_intent(self, question: str, conversation: str) -> dict[str, Any]:
        text = f"{conversation}\n{question}"
        companies = [name for name in ["金花股份", "华润三九"] if name in text]
        periods = re.findall(r"(20\d{2}(?:FY|Q1|HY|Q3))", text)
        if not periods:
            year_match = re.search(r"(20\d{2})年", text)
            if year_match:
                year = year_match.group(1)
                if "第三季度" in text:
                    periods = [f"{year}Q3"]
                elif "半年度" in text or "半年" in text:
                    periods = [f"{year}HY"]
                elif "第一季度" in text or "一季度" in text:
                    periods = [f"{year}Q1"]
                elif "年度" in text or "年报" in text:
                    periods = [f"{year}FY"]
        field_map = {
            "利润总额": ("income_sheet", "total_profit"),
            "净利润": ("income_sheet", "net_profit"),
            "营业收入": ("income_sheet", "operating_revenue"),
            "总资产": ("balance_sheet", "total_assets"),
            "负债": ("balance_sheet", "total_liabilities"),
            "净现金流": ("cash_flow_sheet", "net_cash_flow"),
        }
        tables, fields = [], []
        for cn, (table, field) in field_map.items():
            if cn in text:
                tables.append(table)
                fields.append(field)
        return {
            "tables": list(dict.fromkeys(tables)),
            "fields": list(dict.fromkeys(fields)),
            "companies": companies,
            "periods": periods,
        }

    def _heuristic_sql(self, intent: dict[str, Any]) -> str:
        if not intent["tables"]:
            raise UserFacingError("未识别到可查询的数据表。")
        table = intent["tables"][0]
        fields = intent["fields"] or ["*"]
        where = []
        if intent["companies"]:
            where.append(f"stock_abbr = '{intent['companies'][0]}'")
        if intent["periods"]:
            where.append(f"report_period = '{intent['periods'][0]}'")
        sql = f"SELECT {', '.join(fields)} FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return sql

    def _repair_sql(self, sql: str, error: str) -> str:
        if "no such column" in error:
            raise UserFacingError("查询字段不存在，请换一个指标名称。")
        if "no such table" in error:
            raise UserFacingError("查询数据表不存在。")
        return sql

    def _parse_json(self, raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.S)
            if match:
                return json.loads(match.group(0))
            raise UserFacingError("LLM 未返回有效 JSON。")

    def _extract_sql(self, raw: str) -> str:
        match = re.search(r"```sql\s*(.*?)```", raw, re.S | re.I)
        if match:
            return match.group(1).strip()
        return raw.strip()

    def _ensure_standard_report_period(self, sql: str) -> None:
        invalid = re.search(r"report_period\s*=\s*'?(FY|Q1|HY|Q3)'?", sql)
        if invalid:
            raise UserFacingError("SQL 中 report_period 必须使用完整格式，如 2025Q3。")

    def _clarify(self, question: str, missing: list[str], conversation: ConversationManager) -> str:
        if self.llm_client:
            prompt = load_prompt(
                "clarify.md",
                question=question,
                missing_info=", ".join(missing),
                conversation=conversation.render(),
            )
            return self.llm_client.complete(prompt).strip()
        return f"请补充{ '、'.join(missing) }。"

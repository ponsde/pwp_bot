"""Two-step Text2SQL engine for financial QA."""
from __future__ import annotations

import copy
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from src.etl.schema import load_schema_metadata
from src.prompts.loader import load_prompt
from src.query.conversation import ConversationManager


def _build_create_table_sql() -> str:
    metadata = load_schema_metadata()
    statements: list[str] = []
    for table_name, fields in metadata.items():
        columns = []
        for field in fields:
            columns.append(f'    "{field.name}" {field.sqlite_type}')
        statements.append(f'CREATE TABLE "{table_name}" (\n' + ",\n".join(columns) + "\n);")
    return "\n\n".join(statements)


CREATE_TABLE_SQL = _build_create_table_sql()
FIELD_CATALOG = {
    table_name: [field.name for field in fields if field.name not in {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}]
    for table_name, fields in load_schema_metadata().items()
}
SAFE_SELECT_RE = re.compile(r"^\s*select\s+", re.I)
FORBIDDEN_SQL_RE = re.compile(r"\b(insert|update|delete|drop|attach|pragma|alter|create|replace)\b", re.I)
MAX_PROMPT_ROWS = 50


class UserFacingError(Exception):
    pass


@dataclass
class QueryResult:
    sql: str | None
    rows: list[dict[str, Any]]
    intent: dict[str, Any]
    error: str | None = None
    warning: str | None = None
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
            raw = self.llm_client.complete(prompt, json_mode=True)
            intent = self._ensure_json_dict(raw)
        else:
            intent = self._heuristic_intent(question)
        if conversation:
            intent = conversation.merge_intent(intent)
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
            sql = self._heuristic_sql(question, intent)
        self._ensure_standard_report_period(sql)
        self._ensure_safe_sql(sql)
        return sql

    def query(self, question: str, conversation: ConversationManager | None = None) -> QueryResult:
        manager = conversation or ConversationManager()
        intent = self.analyze(question, manager)
        if intent.get("companies"):
            available = self.list_companies()
            unknown = [c for c in intent["companies"] if c not in available]
            if unknown:
                avail_str = "、".join(available) if available else "（数据库为空）"
                return QueryResult(
                    sql=None, rows=[], intent=intent,
                    error=f"未找到公司「{'、'.join(unknown)}」。可查询的公司：{avail_str}",
                )
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
            sql, rows, final_intent, warning = self._query_with_recovery(question, intent, manager)
            if not rows:
                return QueryResult(sql=sql, rows=[], intent=final_intent, error="未查询到符合条件的数据。")
            return QueryResult(sql=sql, rows=rows, intent=final_intent, warning=warning)
        except UserFacingError as exc:
            return QueryResult(sql=None, rows=[], intent=intent, error=str(exc))

    def list_companies(self) -> list[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT stock_abbr FROM ("
                "SELECT stock_abbr FROM core_performance_indicators_sheet "
                "UNION ALL SELECT stock_abbr FROM balance_sheet "
                "UNION ALL SELECT stock_abbr FROM income_sheet "
                "UNION ALL SELECT stock_abbr FROM cash_flow_sheet"
                ") WHERE stock_abbr IS NOT NULL AND stock_abbr <> '' ORDER BY stock_abbr"
            ).fetchall()
            return [row[0] for row in rows]
        finally:
            conn.close()

    def _query_with_recovery(
        self,
        question: str,
        intent: dict[str, Any],
        conversation: ConversationManager | None = None,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any], str | None]:
        current_intent = copy.deepcopy(intent)
        warning: str | None = None
        current_sql = self.generate_sql(question, current_intent)
        current_rows = self._execute_with_retry(current_sql, question, current_intent)

        validation = self._validate_result(question, current_intent, current_sql, current_rows)
        if not validation["accepted"]:
            current_sql = self.generate_sql(
                self._augment_question(question, validation["reason"]),
                current_intent,
            )
            current_rows = self._execute_with_retry(current_sql, question, current_intent)
            validation = self._validate_result(question, current_intent, current_sql, current_rows)
            if not validation["accepted"]:
                warning = validation["reason"] or "查询结果无法支撑回答原问题。"
                if not current_rows:
                    raise UserFacingError(warning)
                return current_sql, current_rows, current_intent, warning

        reflection = self._reflect_task(question, current_intent, current_sql, current_rows)
        if not reflection["accepted"]:
            reflected_question = reflection["question"] or self._augment_question(question, reflection["reason"])
            current_intent = self.analyze(reflected_question, conversation)
            self._validate_intent(current_intent)
            current_sql = self.generate_sql(reflected_question, current_intent)
            current_rows = self._execute_with_retry(current_sql, reflected_question, current_intent)
            reflection = self._reflect_task(reflected_question, current_intent, current_sql, current_rows)
            if not reflection["accepted"]:
                warning = reflection["reason"] or "查询结果仍未满足原始任务。"
                if not current_rows:
                    raise UserFacingError(warning)

        return current_sql, current_rows, current_intent, warning

    def _execute_with_retry(self, sql: str, question: str, intent: dict[str, Any]) -> list[dict[str, Any]]:
        errors: list[str] = []
        current_sql = sql
        for _ in range(3):
            try:
                return self._execute_sql(current_sql, intent)
            except sqlite3.DatabaseError as exc:
                errors.append(str(exc))
                if self.llm_client:
                    current_sql = self.generate_sql(f"{question}\n上次SQL报错：{exc}", intent)
                else:
                    current_sql = self._repair_sql(current_sql, str(exc))
        raise UserFacingError(f"SQL 执行失败：{'; '.join(errors)}")

    def _execute_sql(self, sql: str, intent: dict[str, Any]) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _validate_result(self, question: str, intent: dict[str, Any], sql: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if self.llm_client:
            prompt = load_prompt(
                "validate_result.md",
                question=question,
                intent_json=json.dumps(intent, ensure_ascii=False),
                sql=sql,
                rows_json=self._serialize_rows_for_prompt(rows),
                rows_hint=self._build_rows_hint(rows),
            )
            raw = self.llm_client.complete(prompt, json_mode=True)
            data = self._ensure_json_dict(raw)
            accepted = bool(data.get("accepted", False))
            return {
                "accepted": accepted,
                "reason": str(data.get("reason", "")).strip(),
            }
        if not rows:
            return {"accepted": False, "reason": "查询结果为空，不足以回答问题。"}
        if intent.get("fields"):
            expected = set(intent["fields"])
            present = set(rows[0].keys())
            if not expected.issubset(present):
                return {"accepted": False, "reason": "结果缺少预期指标字段。"}
        if intent.get("companies"):
            expected_companies = set(intent["companies"])
            actual_companies = {str(row.get("stock_abbr")) for row in rows if row.get("stock_abbr") is not None}
            if actual_companies and not actual_companies.issubset(expected_companies):
                return {"accepted": False, "reason": "结果包含非目标公司数据。"}
        if intent.get("periods") and not intent.get("is_trend"):
            expected_periods = set(intent["periods"])
            actual_periods = {str(row.get("report_period")) for row in rows if row.get("report_period") is not None}
            if actual_periods and not actual_periods.issubset(expected_periods):
                return {"accepted": False, "reason": "结果包含非目标报告期数据。"}
        return {"accepted": True, "reason": ""}

    def _reflect_task(self, question: str, intent: dict[str, Any], sql: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if self.llm_client:
            prompt = load_prompt(
                "reflect.md",
                question=question,
                intent_json=json.dumps(intent, ensure_ascii=False),
                sql=sql,
                rows_json=self._serialize_rows_for_prompt(rows),
                rows_hint=self._build_rows_hint(rows),
            )
            raw = self.llm_client.complete(prompt, json_mode=True)
            data = self._ensure_json_dict(raw)
            accepted = bool(data.get("accepted", False))
            rewritten_question = str(data.get("rewritten_question", "")).strip()
            return {
                "accepted": accepted,
                "reason": str(data.get("reason", "")).strip(),
                "question": rewritten_question,
            }
        return {"accepted": True, "reason": "", "question": ""}

    def _augment_question(self, question: str, reason: str | None) -> str:
        reason_text = (reason or "").strip()
        if not reason_text:
            return question
        return f"{question}\n补充约束：{reason_text}"

    def _validate_intent(self, intent: dict[str, Any]) -> None:
        if not isinstance(intent, dict):
            raise UserFacingError("无法识别查询意图。")
        for key in ["tables", "fields", "companies", "periods"]:
            intent.setdefault(key, [])
        intent.setdefault("is_trend", False)
        for period in intent["periods"]:
            if not re.fullmatch(r"\d{4}(FY|Q1|HY|Q3)", period):
                raise UserFacingError(f"报告期格式不正确：{period}")

    def _heuristic_intent(self, question: str) -> dict[str, Any]:
        text = question.strip()
        companies = [name for name in self.list_companies() if name and name in text]
        periods = re.findall(r"(20\d{2}(?:FY|Q1|HY|Q3))", text)
        if not periods:
            year_match = re.search(r"(20\d{2})年", text)
            if year_match:
                year = year_match.group(1)
                if "第三季度" in text or "三季度" in text:
                    periods = [f"{year}Q3"]
                elif "半年度" in text or "半年" in text:
                    periods = [f"{year}HY"]
                elif "第一季度" in text or "一季度" in text:
                    periods = [f"{year}Q1"]
                else:
                    periods = [f"{year}FY"]
        field_map = {
            "利润总额": ("income_sheet", "total_profit"),
            "净利润": ("income_sheet", "net_profit"),
            "营业收入": ("income_sheet", "total_operating_revenue"),
            "营业总收入": ("income_sheet", "total_operating_revenue"),
            "总资产": ("balance_sheet", "asset_total_assets"),
            "总负债": ("balance_sheet", "liability_total_liabilities"),
            "负债": ("balance_sheet", "liability_total_liabilities"),
            "净现金流": ("cash_flow_sheet", "net_cash_flow"),
            "经营现金流": ("cash_flow_sheet", "operating_cf_net_amount"),
            "每股收益": ("core_performance_indicators_sheet", "eps"),
            "净资产收益率": ("core_performance_indicators_sheet", "roe"),
        }
        tables, fields = [], []
        for cn, (table, field) in field_map.items():
            if cn in text:
                tables.append(table)
                fields.append(field)
        if not fields and any(token in text for token in ["变化趋势", "趋势", "走势"]):
            tables.append("income_sheet")
            fields.append("total_profit")
        is_trend = any(token in text for token in ["变化趋势", "趋势", "走势", "近几年", "历年"])
        return {
            "tables": list(dict.fromkeys(tables)),
            "fields": list(dict.fromkeys(fields)),
            "companies": companies,
            "periods": periods,
            "is_trend": is_trend,
        }

    def _heuristic_sql(self, question: str, intent: dict[str, Any]) -> str:
        if not intent["tables"]:
            raise UserFacingError("未识别到可查询的数据表。")
        table = intent["tables"][0]
        fields = intent["fields"] or ["*"]
        if intent.get("is_trend") or any(token in question for token in ["趋势", "变化", "历年", "走势", "近几年", "近几年的"]):
            select_fields = ["report_period", *fields]
        else:
            select_fields = fields
        where = []
        if intent["companies"]:
            where.append(f"stock_abbr = '{intent['companies'][0]}'")
        if intent["periods"]:
            where.append(f"report_period = '{intent['periods'][0]}'")
        sql = f"SELECT {', '.join(dict.fromkeys(select_fields))} FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if intent.get("is_trend") or any(token in question for token in ["趋势", "变化", "历年", "走势", "近几年", "近几年的"]):
            sql += " ORDER BY report_year, report_period"
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

    def _ensure_json_dict(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return self._parse_json(raw)
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

    def _ensure_safe_sql(self, sql: str) -> None:
        if not SAFE_SELECT_RE.search(sql):
            raise UserFacingError("只允许执行 SELECT 查询。")
        if FORBIDDEN_SQL_RE.search(sql):
            raise UserFacingError("SQL 包含不允许的关键字。")
        if ";" in sql.strip().rstrip(";"):
            raise UserFacingError("不允许执行多条 SQL。")

    def _clarify(self, question: str, missing: list[str], conversation: ConversationManager) -> str:
        if self.llm_client:
            prompt = load_prompt(
                "clarify.md",
                question=question,
                missing_info=", ".join(missing),
                conversation=conversation.render(),
            )
            return str(self.llm_client.complete(prompt)).strip()
        return f"请补充{ '、'.join(missing) }。"

    def _serialize_rows_for_prompt(self, rows: list[dict[str, Any]]) -> str:
        prompt_rows = rows[:MAX_PROMPT_ROWS]
        return json.dumps(prompt_rows, ensure_ascii=False)

    def _build_rows_hint(self, rows: list[dict[str, Any]]) -> str:
        total = len(rows)
        if total > MAX_PROMPT_ROWS:
            return f"结果已截断，共 {total} 行，仅展示前 {MAX_PROMPT_ROWS} 行。"
        return f"结果共 {total} 行，已完整展示。"

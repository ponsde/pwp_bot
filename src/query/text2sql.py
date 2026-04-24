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
SAFE_SELECT_RE = re.compile(r"^\s*(select|with)\s+", re.I)
FORBIDDEN_SQL_RE = re.compile(r"\b(insert|update|delete|drop|attach|pragma|alter|create|replace)\b", re.I)
MAX_PROMPT_ROWS = 50
YOY_KEYWORDS = ("同比", "同比增长", "同比下降", "增长率", "增减")


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
            intent = self._fix_recent_n_years_periods(question, intent)
            intent = self._fix_top_n_intent(question, intent)
            intent = self._fix_yoy_intent(question, intent)
        else:
            intent = self._heuristic_intent(question)
        if conversation:
            intent = conversation.merge_intent(intent)
        self._validate_intent(intent)
        return intent

    def _fix_recent_n_years_periods(self, question: str, intent: dict[str, Any]) -> dict[str, Any]:
        """Post-LLM correction: if question says '近N年', fix periods from DB."""
        recent_n, recent_periods = self._parse_recent_n_years(question)
        if not recent_n or not recent_periods:
            return intent
        current_periods = intent.get("periods") or []
        max_year = self._get_max_report_year()
        needs_fix = (
            not current_periods
            or any(int(p[:4]) > (max_year or 9999) for p in current_periods if re.match(r"\d{4}", p))
        )
        if needs_fix:
            updated = {**intent, "periods": recent_periods, "is_trend": True}
            return updated
        return intent

    def _fix_top_n_intent(self, question: str, intent: dict[str, Any]) -> dict[str, Any]:
        """Post-LLM correction: inject top_n/order_direction from question text."""
        if intent.get("top_n"):
            return intent
        top_n, order_direction = self._parse_top_n(question)
        if not top_n:
            return intent
        return {**intent, "top_n": top_n, "order_direction": order_direction, "companies": []}

    def _fix_yoy_intent(self, question: str, intent: dict[str, Any]) -> dict[str, Any]:
        if intent.get("yoy"):
            return intent
        # Don't flip yoy on trend queries — they should read the precomputed
        # *_yoy_growth columns directly (matches seek_table.md rules 7/8).
        if intent.get("is_trend"):
            return intent
        fields = [str(f) for f in (intent.get("fields") or [])]
        if any(f.endswith("_yoy_growth") or f.endswith("_yoy") for f in fields):
            return intent
        # "环比" is QoQ, not YoY — don't let the "增减" prefix match trigger yoy.
        if "环比" in question:
            return intent
        if self._contains_yoy_keyword(question):
            return {**intent, "yoy": True}
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
                if warning:
                    return QueryResult(sql=sql, rows=[], intent=final_intent, error=warning, warning=warning)
                return QueryResult(sql=sql, rows=[], intent=final_intent, error="未查询到符合条件的数据。")
            return QueryResult(sql=sql, rows=rows, intent=final_intent, warning=warning)
        except UserFacingError as exc:
            return QueryResult(sql=None, rows=[], intent=intent, error=str(exc))

    def list_companies(self) -> list[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            try:
                rows = conn.execute(
                    "SELECT DISTINCT stock_abbr FROM ("
                    "SELECT stock_abbr FROM core_performance_indicators_sheet "
                    "UNION ALL SELECT stock_abbr FROM balance_sheet "
                    "UNION ALL SELECT stock_abbr FROM income_sheet "
                    "UNION ALL SELECT stock_abbr FROM cash_flow_sheet"
                    ") WHERE stock_abbr IS NOT NULL AND stock_abbr <> '' ORDER BY stock_abbr"
                ).fetchall()
            except sqlite3.OperationalError:
                return []
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

        if current_intent.get("yoy") and not current_rows:
            fallback_sql = self._build_single_period_sql(
                current_intent["tables"][0],
                current_intent.get("fields") or ["*"],
                current_intent,
                include_company=True,
            )
            fallback_rows = self._execute_with_retry(fallback_sql, question, current_intent)
            if fallback_rows:
                current_intent["yoy_fallback"] = True
                return fallback_sql, fallback_rows, current_intent, "上年同期数据不存在，无法计算同比"

        if current_intent.get("yoy") and any(row.get("yoy_ratio") is None for row in current_rows):
            warning = "上年同期值为零，无法计算同比增长率"

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
            try:
                raw = self.llm_client.complete(prompt, json_mode=True)
            except (ValueError, OSError, RuntimeError):
                # Validation LLM failed (malformed JSON, network, etc.).
                # Degrade to "accept" — we'd rather surface the original
                # query result than crash the whole pipeline on a
                # validator hiccup.
                return {"accepted": True, "reason": "validator_llm_failed"}
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
            if intent.get("yoy"):
                if {"current_value", "previous_value", "yoy_ratio"}.issubset(present):
                    expected = set()
                else:
                    present |= {"current_value", "previous_value", "yoy_ratio"}
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

    _PERIOD_ALIAS_MAP = {
        "Q2": "HY",  # Chinese listed companies publish semi-annual (HY), not Q2 alone
        "Q4": "FY",  # Annual (FY), not Q4
        "H1": "HY",
        "H2": "FY",
        "FY1": "FY",
        "": None,
    }

    def _normalize_period(self, period: str) -> str:
        """Coerce LLM-returned periods into the DB schema form (FY/Q1/HY/Q3)."""
        match = re.fullmatch(r"(\d{4})([A-Z0-9]+)", str(period or "").strip().upper())
        if not match:
            return period
        year, suffix = match.group(1), match.group(2)
        mapped = self._PERIOD_ALIAS_MAP.get(suffix, suffix)
        if mapped is None:
            return period
        return f"{year}{mapped}"

    def _validate_intent(self, intent: dict[str, Any]) -> None:
        if not isinstance(intent, dict):
            raise UserFacingError("无法识别查询意图。")
        for key in ["tables", "fields", "companies", "periods"]:
            intent.setdefault(key, [])
        intent.setdefault("is_trend", False)
        intent.setdefault("top_n", None)
        intent.setdefault("order_direction", None)
        intent.setdefault("yoy", False)
        normalized_periods = []
        for period in intent["periods"]:
            fixed = self._normalize_period(period)
            if not re.fullmatch(r"\d{4}(FY|Q1|HY|Q3)", fixed):
                # Drop silently rather than error out — user may ask about a
                # period that doesn't exist (e.g. "Q4"). Query layer falls
                # back to trend / generic queries.
                continue
            normalized_periods.append(fixed)
        intent["periods"] = normalized_periods

    _CN_DIGIT_MAP: dict[str, int] = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }

    def _get_max_report_year(self) -> int | None:
        """Return the max year that has FY (annual) data, not just quarterly."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT MAX(report_year) FROM ("
                "SELECT report_year FROM core_performance_indicators_sheet WHERE report_period LIKE '%FY' "
                "UNION ALL SELECT report_year FROM balance_sheet WHERE report_period LIKE '%FY' "
                "UNION ALL SELECT report_year FROM income_sheet WHERE report_period LIKE '%FY' "
                "UNION ALL SELECT report_year FROM cash_flow_sheet WHERE report_period LIKE '%FY'"
                ")"
            ).fetchone()
            if row and row[0] is not None:
                return int(row[0])
            row = conn.execute(
                "SELECT MAX(report_year) FROM ("
                "SELECT report_year FROM core_performance_indicators_sheet "
                "UNION ALL SELECT report_year FROM balance_sheet "
                "UNION ALL SELECT report_year FROM income_sheet "
                "UNION ALL SELECT report_year FROM cash_flow_sheet"
                ")"
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else None
        finally:
            conn.close()

    def _parse_recent_n_years(self, text: str) -> tuple[int | None, list[str]]:
        match = re.search(r"近(\d+|[一二三四五六七八九十]+)年", text)
        if not match:
            return None, []
        raw = match.group(1)
        n = self._CN_DIGIT_MAP.get(raw) if raw in self._CN_DIGIT_MAP else int(raw) if raw.isdigit() else None
        if not n:
            return None, []
        max_year = self._get_max_report_year()
        if not max_year:
            return n, []
        periods = [f"{max_year - i}FY" for i in range(n - 1, -1, -1)]
        return n, periods

    def _parse_top_n(self, text: str) -> tuple[int | None, str | None]:
        patterns = [
            (r"[Tt][Oo][Pp]\s*(\d+)", "DESC"),
            (r"排名前\s*(\d+)", "DESC"),
            (r"最高的?\s*(\d+)\s*家", "DESC"),
            (r"最低的?\s*(\d+)\s*家", "ASC"),
            (r"最少的?\s*(\d+)\s*家", "ASC"),
            (r"最多的?\s*(\d+)\s*家", "DESC"),
        ]
        for pattern, direction in patterns:
            m = re.search(pattern, text)
            if m:
                return int(m.group(1)), direction
        return None, None

    def _contains_yoy_keyword(self, text: str) -> bool:
        if "环比" in text:
            return False
        if any(keyword in text for keyword in YOY_KEYWORDS):
            return True
        return False

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
        recent_n, recent_periods = self._parse_recent_n_years(text)
        is_trend = any(token in text for token in ["变化趋势", "趋势", "走势", "近几年", "历年"])
        if recent_n and recent_periods:
            periods = recent_periods
            is_trend = True
        field_map = {
            "利润总额": ("income_sheet", "total_profit"),
            "净利润": ("income_sheet", "net_profit"),
            "营业收入": ("income_sheet", "total_operating_revenue"),
            "营业总收入": ("income_sheet", "total_operating_revenue"),
            "主营业务收入": ("income_sheet", "total_operating_revenue"),
            "销售额": ("income_sheet", "total_operating_revenue"),
            "总资产": ("balance_sheet", "asset_total_assets"),
            "总负债": ("balance_sheet", "liability_total_liabilities"),
            "负债": ("balance_sheet", "liability_total_liabilities"),
            "净现金流": ("cash_flow_sheet", "net_cash_flow"),
            "经营现金流": ("cash_flow_sheet", "operating_cf_net_amount"),
            "每股收益": ("core_performance_indicators_sheet", "eps"),
            "净资产收益率": ("core_performance_indicators_sheet", "roe"),
            "利润": ("income_sheet", "total_profit"),
        }
        tables, fields = [], []
        matched_terms: set[str] = set()
        for cn, (table, field) in field_map.items():
            if cn in text and not any(cn in term and cn != term for term in matched_terms):
                tables.append(table)
                fields.append(field)
                matched_terms.add(cn)
        if not fields and any(token in text for token in ["变化趋势", "趋势", "走势"]):
            tables.append("income_sheet")
            fields.append("total_profit")
        top_n, order_direction = self._parse_top_n(text)
        if top_n:
            companies = []
        yoy = self._contains_yoy_keyword(text)
        return {
            "tables": list(dict.fromkeys(tables)),
            "fields": list(dict.fromkeys(fields)),
            "companies": companies,
            "periods": periods,
            "is_trend": is_trend,
            "top_n": top_n,
            "order_direction": order_direction,
            "yoy": yoy,
        }

    def _heuristic_sql(self, question: str, intent: dict[str, Any]) -> str:
        if not intent["tables"]:
            raise UserFacingError("未识别到可查询的数据表。")
        table = intent["tables"][0]
        fields = intent["fields"] or ["*"]
        top_n = intent.get("top_n")
        if intent.get("yoy"):
            return self._build_yoy_sql(table, fields, intent)
        is_trend = intent.get("is_trend") or any(
            token in question for token in ["趋势", "变化", "历年", "走势", "近几年", "近几年的"]
        )
        if top_n and fields and fields != ["*"]:
            return self._build_top_n_sql(table, fields, intent, top_n)
        return self._build_single_period_sql(table, fields, intent, include_company=bool(intent.get("companies")), is_trend=is_trend)

    def _build_single_period_sql(
        self,
        table: str,
        fields: list[str],
        intent: dict[str, Any],
        include_company: bool = False,
        is_trend: bool | None = None,
    ) -> str:
        trend = intent.get("is_trend") if is_trend is None else is_trend
        select_fields = list(fields)
        if trend:
            select_fields = ["report_period", *fields]
        elif include_company and "stock_abbr" not in select_fields:
            select_fields = ["stock_abbr", *select_fields]
        where = []
        companies = intent.get("companies") or []
        if companies:
            if len(companies) == 1:
                where.append(f"stock_abbr = '{companies[0]}'")
            else:
                companies_in = ", ".join(f"'{company}'" for company in companies)
                where.append(f"stock_abbr IN ({companies_in})")
        if intent.get("periods"):
            periods_in = ", ".join(f"'{p}'" for p in intent["periods"])
            if len(intent["periods"]) == 1:
                where.append(f"report_period = '{intent['periods'][0]}'")
            else:
                where.append(f"report_period IN ({periods_in})")
        sql = f"SELECT {', '.join(dict.fromkeys(select_fields))} FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if trend:
            sql += " ORDER BY report_year, report_period"
        return sql

    def _build_yoy_sql(self, table: str, fields: list[str], intent: dict[str, Any]) -> str:
        if not intent.get("periods"):
            raise UserFacingError("同比查询缺少报告期。")
        current_period = intent["periods"][0]
        match = re.fullmatch(r"(\d{4})(FY|Q1|HY|Q3)", current_period)
        if not match:
            raise UserFacingError("同比报告期格式不支持，期待 2024FY / 2025Q1 / 2025HY / 2025Q3。")
        previous_period = f"{int(match.group(1)) - 1}{match.group(2)}"
        if not fields:
            raise UserFacingError("同比查询缺少指标字段，请明确说明要查询的财务指标。")
        metric = fields[0]
        select_fields = [
            "a.stock_abbr",
            "a.report_period",
            f"a.{metric} AS current_value",
            f"b.{metric} AS previous_value",
            (
                f"CASE WHEN b.{metric} = 0 THEN NULL "
                f"ELSE ROUND((a.{metric} - b.{metric}) * 1.0 / b.{metric}, 4) END AS yoy_ratio"
            ),
        ]
        where = [f"a.report_period = '{current_period}'", f"b.report_period = '{previous_period}'"]
        companies = intent.get("companies") or []
        if companies:
            if len(companies) == 1:
                where.append(f"a.stock_abbr = '{companies[0]}'")
            else:
                companies_in = ", ".join(f"'{company}'" for company in companies)
                where.append(f"a.stock_abbr IN ({companies_in})")
        sql = (
            f"SELECT {', '.join(select_fields)} FROM {table} a "
            f"JOIN {table} b ON a.stock_abbr = b.stock_abbr "
            f"WHERE {' AND '.join(where)}"
        )
        if intent.get("top_n"):
            direction = intent.get("order_direction") or "DESC"
            sql += f" ORDER BY yoy_ratio {direction} LIMIT {int(intent['top_n'])}"
        return sql

    def _build_top_n_sql(
        self, table: str, fields: list[str], intent: dict[str, Any], top_n: int,
    ) -> str:
        direction = intent.get("order_direction") or "DESC"
        order_field = fields[0]
        select_fields = ["stock_abbr", *fields]
        where = []
        if intent["periods"]:
            periods_in = ", ".join(f"'{p}'" for p in intent["periods"])
            if len(intent["periods"]) == 1:
                where.append(f"report_period = '{intent['periods'][0]}'")
            else:
                where.append(f"report_period IN ({periods_in})")
        sql = f"SELECT {', '.join(dict.fromkeys(select_fields))} FROM {table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order_field} {direction} LIMIT {top_n}"
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

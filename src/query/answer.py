"""Answer formatting utilities."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.etl.schema import load_schema_metadata

CHART_TYPE_LABELS = {
    "line": "折线图",
    "bar": "柱状图",
    "pie": "饼图",
    "none": "无",
}

IDENTIFIER_FIELDS = {"stock_abbr", "report_period"}
META_FIELDS = {"serial_number", "stock_code"}

# Build field → unit and field → label lookups from schema
_FIELD_UNITS: dict[str, str] = {}
_FIELD_LABELS: dict[str, str] = {}
for _fields in load_schema_metadata().values():
    for _f in _fields:
        if _f.unit and _f.name not in _FIELD_UNITS:
            _FIELD_UNITS[_f.name] = _f.unit
        if _f.label and _f.name not in _FIELD_LABELS:
            # Strip unit suffix like "(万元)" from label for display
            _FIELD_LABELS[_f.name] = re.sub(r"[（(][^)）]*[)）]$", "", _f.label).strip()


def format_number(value: Any, unit: str = "万元") -> str:
    """Format a number with appropriate Chinese unit."""
    if not isinstance(value, (int, float)):
        return str(value)
    abs_value = abs(float(value))
    if unit == "万元":
        if abs_value >= 10000:
            return f"{value / 10000:.2f}亿元"
        return f"{value:,.2f}万元"
    if unit == "元":
        return f"{value:.2f}元"
    if unit == "%":
        return f"{value:.2f}%"
    return f"{value:,.2f}"


def _format_report_period(period: Any) -> str:
    text = str(period or "")
    match = re.fullmatch(r"(\d{4})(FY|Q1|HY|Q3)", text)
    if not match:
        return text
    year, suffix = match.groups()
    suffix_map = {"FY": "年", "Q1": "年第一季度", "HY": "年半年度", "Q3": "年第三季度"}
    return f"{year}{suffix_map.get(suffix, '')}"


def _resolve_intent_field(intent: dict[str, Any] | None) -> str | None:
    if not isinstance(intent, dict):
        return None
    fields = intent.get("fields") or []
    if not isinstance(fields, list) or not fields:
        return None
    return str(fields[0])


def _format_metric_value(value: Any, unit: str) -> str:
    if unit == "元" and isinstance(value, (int, float)):
        return format_number(float(value) / 10000, "万元")
    if unit == "万元" and isinstance(value, (int, float)) and abs(float(value)) >= 1_000_000:
        return f"{float(value) / 10000:,.2f}万元"
    return format_number(value, unit)


def _format_yoy_row(row: dict[str, Any], intent_fields: list[str] | None = None) -> str:
    field_name = intent_fields[0] if intent_fields else None
    field_label = _FIELD_LABELS.get(field_name or "", field_name or "指标")
    unit = _FIELD_UNITS.get(field_name or "", "万元")
    company = str(row.get("stock_abbr") or "")
    period = _format_report_period(row.get("report_period"))
    current_value = _format_metric_value(row.get("current_value"), unit)
    prefix = "：".join(part for part in [company] if part) + ("：" if company else "")
    subject = f"{period}{field_label}" if period else field_label
    yoy_ratio = row.get("yoy_ratio")
    if yoy_ratio is None:
        return f"{prefix}{subject}无法计算同比（上期值为零），本期{current_value}"
    direction = "增长" if float(yoy_ratio) >= 0 else "下降"
    ratio_text = f"{abs(float(yoy_ratio)) * 100:.2f}%"
    previous_value = _format_metric_value(row.get("previous_value"), unit)
    return f"{prefix}{subject}同比{direction}{ratio_text}（本期{current_value}，上期{previous_value}）"


def _display_label(field_name: str) -> str:
    return _FIELD_LABELS.get(field_name, field_name)


def _format_single_value(field_name: str, value: Any) -> str:
    field_label = _display_label(field_name)
    unit = _FIELD_UNITS.get(field_name, "")
    if unit == "%" and "同比" in field_label and isinstance(value, (int, float)):
        direction = "增长" if value >= 0 else "下降"
        base_name = re.sub(r"[-\s]*(同比)?[增减降长]*$", "", field_label).strip() or field_name
        return f"{base_name}同比{direction}{abs(float(value)):.2f}%。"
    return f"{field_label}{format_number(value, unit)}。"


def build_answer_content(question: str, rows: Sequence[dict], intent: dict[str, Any] | None = None) -> str:
    if not rows:
        return "未查询到符合条件的数据。"
    if all({"current_value", "previous_value", "yoy_ratio"}.issubset(set(row.keys())) for row in rows):
        intent_field = _resolve_intent_field(intent)
        return "\n".join(_format_yoy_row(row, [intent_field] if intent_field else None) for row in rows)
    if len(rows) == 1 and len(rows[0]) == 1:
        field_name = next(iter(rows[0].keys()))
        value = next(iter(rows[0].values()))
        return _format_single_value(field_name, value)
    # Multi-row: build a readable summary
    parts = []
    for row in rows:
        identifiers = [
            _format_report_period(row[field]) if field == "report_period" else str(row[field])
            for field in ("stock_abbr", "report_period")
            if row.get(field) not in (None, "")
        ]
        items = []
        for k, v in row.items():
            if k in META_FIELDS or k in IDENTIFIER_FIELDS:
                continue
            unit = _FIELD_UNITS.get(k, "")
            display_value = format_number(v, unit) if isinstance(v, (int, float)) else v
            display_name = _display_label(k)
            if unit == "%" and isinstance(v, (int, float)) and "同比" in display_name:
                direction = "增长" if v >= 0 else "下降"
                base_name = re.sub(r"[-\s]*(同比)?[增减降长]*$", "", display_name).strip() or k
                items.append(f"{base_name}同比{direction}{abs(v):.2f}%")
            else:
                items.append(f"{display_name}={display_value}")
        line = "，".join(identifiers)
        if items:
            metrics = "，".join(items)
            line = f"{line}：{metrics}" if line else metrics
        parts.append(line or "-")
    return "\n".join(parts)


def build_answer_record(
    question: str,
    content: str,
    image: list[str] | None = None,
    chart_type: str = "none",
    sql: str = "",
) -> dict:
    return {
        "Q": question,
        "A": {"content": content, "image": image or []},
        "chart_type": CHART_TYPE_LABELS.get(chart_type, "无"),
        "sql": sql,
    }


def write_result_xlsx(
    records: Sequence[dict], output_path: str, sql_map: dict[str, str] | None = None,
) -> str:
    rows = []
    sql_map = sql_map or {}
    for idx, record in enumerate(records, start=1):
        rows.append({
            "编号": f"B{idx:04d}",
            "问题": json.dumps([{"Q": record["Q"]}], ensure_ascii=False),
            "SQL查询语句": record.get("sql") or sql_map.get(record["Q"], ""),
            "图形格式": record.get("chart_type", "无"),
            "回答": json.dumps([{"Q": record["Q"], "A": record["A"]}], ensure_ascii=False),
        })
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)

"""Answer formatting utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd


CHART_TYPE_LABELS = {
    "line": "折线图",
    "bar": "柱状图",
    "pie": "饼图",
    "none": "无",
}


def format_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        abs_value = abs(float(value))
        if abs_value >= 10000:
            return f"{value / 10000:.2f}亿元"
        return f"{value:.2f}万元"
    return str(value)


def build_answer_content(question: str, rows: Sequence[dict]) -> str:
    if not rows:
        return "未查询到符合条件的数据。"
    if len(rows) == 1 and len(rows[0]) == 1:
        value = next(iter(rows[0].values()))
        return f"{question}：{format_number(value)}。"
    return json.dumps(rows, ensure_ascii=False)


def build_answer_record(question: str, content: str, image: list[str] | None = None, chart_type: str = "none") -> dict:
    return {"Q": question, "A": {"content": content, "image": image or []}, "chart_type": CHART_TYPE_LABELS.get(chart_type, "无")}


def write_result_xlsx(records: Sequence[dict], output_path: str, sql_map: dict[str, str] | None = None) -> str:
    rows = []
    sql_map = sql_map or {}
    for idx, record in enumerate(records, start=1):
        rows.append(
            {
                "编号": f"B{idx:04d}",
                "问题": json.dumps([{"Q": record["Q"]}], ensure_ascii=False),
                "SQL查询语句": sql_map.get(record["Q"], ""),
                "图形格式": record.get("chart_type", "无"),
                "回答": json.dumps([{"Q": record["Q"], "A": record["A"]}], ensure_ascii=False),
            }
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)

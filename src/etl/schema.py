from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from config import COMPANY_XLSX, SCHEMA_XLSX


TABLE_SHEET_MAP = {
    "core_performance_indicators_sheet": "核心业绩指标表",
    "balance_sheet": "资产负债表",
    "income_sheet": "利润表",
    "cash_flow_sheet": "现金流量表",
}

COMMON_KEY_TYPES = {
    "serial_number": "INTEGER",
    "stock_code": "TEXT",
    "stock_abbr": "TEXT",
    "report_period": "TEXT",
    "report_year": "INTEGER",
}


@dataclass(frozen=True)
class FieldMeta:
    name: str
    label: str
    sqlite_type: str
    excel_type: str
    unit: str
    description: str


def excel_type_to_sqlite(excel_type: str) -> str:
    text = str(excel_type).lower()
    if "int" in text:
        return "INTEGER"
    if "decimal" in text or "float" in text or "double" in text:
        return "REAL"
    return "TEXT"


def infer_unit(label: str) -> str:
    if "(万元)" in label or "（万元）" in label:
        return "万元"
    if "(元)" in label or "（元）" in label:
        return "元"
    if "(%)" in label or "（%）" in label:
        return "%"
    if "比率" in label:
        return "比率"
    return ""


def load_schema_metadata(schema_path: Path = SCHEMA_XLSX) -> dict[str, list[FieldMeta]]:
    metadata: dict[str, list[FieldMeta]] = {}
    for table_name, sheet_name in TABLE_SHEET_MAP.items():
        df = pd.read_excel(schema_path, sheet_name=sheet_name)
        fields: list[FieldMeta] = []
        for _, row in df.iterrows():
            field_name = str(row["字段名称"]).strip()
            label = str(row["中文名称"]).strip()
            excel_type = str(row[df.columns[2]]).strip()
            unit = infer_unit(label)
            if table_name == "cash_flow_sheet" and field_name == "net_cash_flow":
                unit = "万元"
            fields.append(
                FieldMeta(
                    name=field_name,
                    label=label,
                    sqlite_type=excel_type_to_sqlite(excel_type),
                    excel_type=excel_type,
                    unit=unit,
                    description=str(row.get("字段说明", "")).strip(),
                )
            )
        metadata[table_name] = fields
    return metadata


def create_tables(db_path: Path) -> dict[str, list[FieldMeta]]:
    metadata = load_schema_metadata()
    conn = sqlite3.connect(db_path)
    try:
        for table_name, fields in metadata.items():
            columns = []
            for field in fields:
                col_type = COMMON_KEY_TYPES.get(field.name, field.sqlite_type)
                columns.append(f'"{field.name}" {col_type}')
            unique = "UNIQUE(stock_code, report_period)"
            ddl = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)}, {unique})'
            conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()
    return metadata


def validate_schema(db_path: Path, metadata: dict[str, list[FieldMeta]] | None = None) -> None:
    metadata = metadata or load_schema_metadata()
    conn = sqlite3.connect(db_path)
    try:
        for table_name, fields in metadata.items():
            rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            actual = [row[1] for row in rows]
            expected = [field.name for field in fields]
            if actual != expected:
                raise AssertionError(f"Schema mismatch for {table_name}: {actual} != {expected}")
    finally:
        conn.close()


def load_company_mapping(company_path: Path = COMPANY_XLSX) -> dict[str, dict[str, str]]:
    df = pd.read_excel(company_path, sheet_name="基本信息表")
    mapping: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        stock_code = str(row["股票代码"]).strip().zfill(6)
        stock_abbr = str(row["A股简称"]).strip()
        mapping[stock_code] = {"stock_code": stock_code, "stock_abbr": stock_abbr}
        mapping[stock_abbr] = {"stock_code": stock_code, "stock_abbr": stock_abbr}
    return mapping

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


def load_official_stock_codes(company_path: Path = COMPANY_XLSX) -> set[str]:
    """Return the set of 6-digit stock codes listed in 附件1 (官方赛事公司清单).

    Used as the seed of the ETL allowlist; the loader extends this by scanning
    附件2 摘要 PDFs so that companies with real reports but absent from 附件1
    (e.g. 香雪制药, 长药控股) are still accepted while references to unrelated
    companies (平安银行 / 贵州茅台 inside some report body) are rejected.
    """
    df = pd.read_excel(company_path, sheet_name="基本信息表")
    return {str(row["股票代码"]).strip().zfill(6) for _, row in df.iterrows()}


def build_dynamic_company_mapping(
    pdf_dir: Path,
    company_path: Path = COMPANY_XLSX,
) -> tuple[dict[str, dict[str, str]], set[str]]:
    """Augment 附件1 mapping with companies discovered by scanning 附件2.

    Two discovery rules:
      1. SSE filename `\\d{6}_\\d{8}_[A-Z0-9]+\\.pdf` — the 6-digit prefix IS
         the stock_code. No PDF read required.
      2. SZSE filename `abbr：YYYY年...摘要.pdf` where abbr not already in 附件1 —
         open the 摘要 PDF and scan the first page for 证券代码: \\d{6}. The 摘要
         cover page reliably carries this, even when the full report doesn't.

    Returns (mapping, allowlist) where:
      - mapping has both `{stock_code: {…}}` and `{stock_abbr: {…}}` keys.
      - allowlist is the set of all 6-digit stock codes known to the ETL.
    """
    import pdfplumber

    mapping: dict[str, dict[str, str]] = dict(load_company_mapping(company_path))
    allowlist: set[str] = load_official_stock_codes(company_path)

    sse_re = re.compile(r"^(\d{6})_\d{8}_[A-Z0-9]+\.pdf$")
    szse_summary_re = re.compile(r"^([^：:]+)[：:]20\d{2}年.*?摘要")
    code_re = re.compile(r"(?:证券代码|股票代码|公司代码)[：:\s]*(\d{6})")

    for pdf in sorted(Path(pdf_dir).rglob("*.pdf")):
        m_sse = sse_re.match(pdf.name)
        if m_sse:
            code = m_sse.group(1).zfill(6)
            allowlist.add(code)
            continue
        m_szse = szse_summary_re.match(pdf.name)
        if not m_szse:
            continue
        abbr = m_szse.group(1).strip()
        if abbr in mapping:
            continue
        try:
            with pdfplumber.open(pdf) as doc:
                if not doc.pages:
                    continue
                text = doc.pages[0].extract_text() or ""
        except Exception:
            continue
        cm = code_re.search(text)
        if not cm:
            continue
        code = cm.group(1).zfill(6)
        mapping[abbr] = {"stock_code": code, "stock_abbr": abbr}
        mapping.setdefault(code, {"stock_code": code, "stock_abbr": abbr})
        allowlist.add(code)
    return mapping, allowlist

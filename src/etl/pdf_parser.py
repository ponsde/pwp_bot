from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from src.etl.schema import load_company_mapping


SZSE_RE = re.compile(r"(?P<abbr>[^：:]+)[：:](?P<year>20\d{2})年(?P<period>年度报告摘要|年度报告|一季度报告|半年度报告摘要|半年度报告|三季度报告)")
SSE_FILE_RE = re.compile(r"(?P<code>\d{6})_(?P<date>\d{8})_[A-Z0-9]+\.pdf$")
SSE_TITLE_RE = re.compile(r"(?P<year>20\d{2})\s*年\s*(?P<period>年度报告摘要|年度报告|第一季度报告|半年度报告摘要|半年度报告|第三季度报告)")

PERIOD_MAP = {
    "年度报告": "FY",
    "一季度报告": "Q1",
    "第一季度报告": "Q1",
    "半年度报告": "HY",
    "三季度报告": "Q3",
    "第三季度报告": "Q3",
}

HEAD_PAGE_LIMIT = 20
FULL_SCAN_PAGE_LIMIT = 120

TABLE_TITLE_PATTERNS = {
    "core_performance_indicators_sheet": ["主要会计数据", "主要财务指标", "分季度主要财务指标"],
    "balance_sheet": ["合并资产负债表"],
    "income_sheet": ["合并利润表", "合并年初到报告期末利润表"],
    "cash_flow_sheet": ["合并现金流量表", "合并年初到报告期末现金流量表"],
}


@dataclass
class ParsedTable:
    page_number: int
    raw_rows: list[list[Any]]
    text: str
    title: str | None = None
    table_type: str | None = None


@dataclass
class ParsedPDF:
    file_path: Path
    stock_code: str
    stock_abbr: str
    report_period: str
    report_year: int
    is_summary: bool
    exchange: str
    tables: list[ParsedTable] = field(default_factory=list)
    page_texts: list[str] = field(default_factory=list)


class PDFParser:
    def __init__(self) -> None:
        self.company_mapping = load_company_mapping()

    def parse(self, pdf_path: str | Path) -> ParsedPDF:
        path = Path(pdf_path)
        if "深交所" in str(path.parent):
            meta = self._parse_szse_meta(path)
            exchange = "SZSE"
        else:
            meta = self._parse_sse_meta(path)
            exchange = "SSE"
        meta["exchange"] = exchange

        page_texts: list[str] = []
        tables: list[ParsedTable] = []
        with pdfplumber.open(path) as pdf:
            if meta["report_period"].endswith("FY"):
                tail_start = 99 if meta["exchange"] == "SZSE" else 75
                page_indices = list(range(min(len(pdf.pages), HEAD_PAGE_LIMIT))) + list(range(tail_start, min(len(pdf.pages), FULL_SCAN_PAGE_LIMIT)))
            else:
                page_indices = list(range(min(len(pdf.pages), 40)))
            seen = set()
            for page_idx in page_indices:
                if page_idx in seen:
                    continue
                seen.add(page_idx)
                page = pdf.pages[page_idx]
                idx = page_idx + 1
                text = page.extract_text() or ""
                page_texts.append(text)
                raw_tables = page.extract_tables() or []
                for raw in raw_tables:
                    parsed = ParsedTable(page_number=idx, raw_rows=raw, text=text)
                    parsed.title = self._guess_title(text)
                    parsed.table_type = self._classify_table(parsed)
                    tables.append(parsed)
        return ParsedPDF(file_path=path, tables=self._merge_cross_page_tables(tables), page_texts=page_texts, **meta)

    def _parse_szse_meta(self, path: Path) -> dict[str, Any]:
        m = SZSE_RE.search(path.name)
        if not m:
            raise ValueError(f"Unrecognized SZSE file name: {path.name}")
        stock_abbr = m.group("abbr")
        info = self.company_mapping.get(stock_abbr)
        if not info:
            raise ValueError(f"Unknown company: {stock_abbr} (not in 附件1)")
        period_name = m.group("period")
        year = int(m.group("year"))
        is_summary = "摘要" in period_name
        period = f"{year}{PERIOD_MAP[period_name.replace('摘要','')]}"
        return {
            "stock_code": info["stock_code"],
            "stock_abbr": stock_abbr,
            "report_period": period,
            "report_year": year,
            "is_summary": is_summary,
        }

    def _parse_sse_meta(self, path: Path) -> dict[str, Any]:
        m = SSE_FILE_RE.search(path.name)
        if not m:
            raise ValueError(f"Unrecognized SSE file name: {path.name}")
        stock_code = m.group("code")
        info = self.company_mapping.get(stock_code)
        if not info:
            raise ValueError(f"Unknown stock_code: {stock_code} (not in 附件1)")
        file_date = m.group("date")
        with pdfplumber.open(path) as pdf:
            first_text = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(2, len(pdf.pages))))
        t = SSE_TITLE_RE.search(first_text)
        if t:
            year = int(t.group("year"))
            period_name = t.group("period")
            is_summary = "摘要" in period_name
            normalized = period_name.replace("摘要", "")
            period = f"{year}{PERIOD_MAP[normalized]}"
        else:
            year, period, is_summary = self._infer_sse_period_from_filename_date(file_date)
        return {
            "stock_code": stock_code,
            "stock_abbr": info["stock_abbr"],
            "report_period": period,
            "report_year": year,
            "is_summary": is_summary,
        }

    def _infer_sse_period_from_filename_date(self, file_date: str) -> tuple[int, str, bool]:
        year = int(file_date[:4])
        month = int(file_date[4:6])
        if month == 4:
            report_year = year - 1
            suffix = "FY"
        elif month == 8:
            report_year = year
            suffix = "HY"
        elif month == 10:
            report_year = year
            suffix = "Q3"
        else:
            report_year = year
            suffix = "Q1"
        return report_year, f"{report_year}{suffix}", False

    def _guess_title(self, page_text: str) -> str | None:
        for titles in TABLE_TITLE_PATTERNS.values():
            for title in titles:
                if title in page_text:
                    return title
        return None

    def _classify_table(self, table: ParsedTable) -> str | None:
        text = (table.title or "") + "\n" + table.text[:1500]
        if "合并资产负债表" in text:
            return "balance_sheet"
        if "合并利润表" in text or "合并年初到报告期末利润表" in text:
            return "income_sheet"
        if "合并现金流量表" in text or "合并年初到报告期末现金流量表" in text:
            return "cash_flow_sheet"
        if any(p in text for p in TABLE_TITLE_PATTERNS["core_performance_indicators_sheet"]):
            return "core_performance_indicators_sheet"
        for table_type, patterns in TABLE_TITLE_PATTERNS.items():
            if any(p in text for p in patterns):
                return table_type
        return None

    def _merge_cross_page_tables(self, tables: list[ParsedTable]) -> list[ParsedTable]:
        merged: list[ParsedTable] = []
        for table in tables:
            if merged and table.table_type and table.table_type == merged[-1].table_type and 1 <= table.page_number - merged[-1].page_number <= 2:
                merged[-1].raw_rows.extend(table.raw_rows)
                merged[-1].text += "\n" + table.text
                continue
            merged.append(table)
        return merged

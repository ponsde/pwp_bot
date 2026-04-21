from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from src.etl.schema import load_company_mapping


SZSE_RE = re.compile(
    r"(?P<abbr>[^：:]+)[：:]"
    r".*?"                                   # optional: repeated abbr before year
    r"(?P<year>20\d{2})年"
    r"(?P<period>"
    r"(?:第?一季度报告|半年度报告摘要|半年度报告|第?三季度报告|年度报告摘要|年度报告)"
    r"(?:全文)?"
    r")"
    r"(?:（[^）]+）)?"                        # optional trailing: (更新后)/(更正后)/(英文版)/...
)
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
FULL_SCAN_PAGE_LIMIT = 200

TABLE_TITLE_PATTERNS = {
    "core_performance_indicators_sheet": ["主要会计数据", "主要财务指标", "分季度主要财务指标"],
    "balance_sheet": ["合并资产负债表"],
    "income_sheet": ["合并利润表", "合并年初到报告期末利润表"],
    "cash_flow_sheet": ["合并现金流量表", "合并年初到报告期末现金流量表"],
}

CONFIRM_KEYWORDS = {
    "balance_sheet": ("货币资金", "负债合计", "所有者权益合计", "股东权益合计", "资产总计", "资产总额"),
    "income_sheet": ("营业收入", "营业总收入", "利润总额", "净利润", "营业支出", "手续费及佣金净收入"),
    "cash_flow_sheet": ("销售商品", "销售商品、提供劳务收到的现金", "销售商品及提供劳务收到的现金", "经营活动产生的现金流量净额", "现金及现金等价物净增加额"),
    "core_performance_indicators_sheet": ("基本每股收益", "每股收益", "营业收入", "净利润", "归属于上市公司股东的净利润"),
}

INVALID_TABLE_KEYWORDS = (
    "母公司资产负债表",
    "母公司利润表",
    "母公司现金流量表",
    "母公司所有者权益变动表",
    "母公司股东权益变动表",
)
EXCLUDED_STATEMENT_KEYWORDS = ("股东权益变动", "所有者权益变动", "所有者权益内部结转", "上年年末余额", "本年增减变动金额")


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
    def __init__(self, company_mapping: dict[str, dict[str, str]] | None = None) -> None:
        self.company_mapping = company_mapping if company_mapping is not None else load_company_mapping()

    def parse(self, pdf_path: str | Path) -> ParsedPDF:
        path = Path(pdf_path)
        if SZSE_RE.search(path.name):
            meta = self._parse_szse_meta(path)
            exchange = "SZSE"
        elif SSE_FILE_RE.search(path.name):
            meta = self._parse_sse_meta(path)
            exchange = "SSE"
        else:
            raise ValueError(f"Unrecognized file name format: {path.name}")
        meta["exchange"] = exchange

        page_texts: list[str] = []
        tables: list[ParsedTable] = []
        with pdfplumber.open(path) as pdf:
            page_indices = list(range(len(pdf.pages)))
            seen = set()
            previous_text = ""
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
                    parsed.table_type = self._classify_table(parsed, previous_text=previous_text)
                    tables.append(parsed)
                previous_text = text
        return ParsedPDF(file_path=path, tables=self._merge_cross_page_tables(tables), page_texts=page_texts, **meta)

    def _parse_szse_meta(self, path: Path) -> dict[str, Any]:
        m = SZSE_RE.search(path.name)
        if not m:
            raise ValueError(f"Unrecognized SZSE file name: {path.name}")
        stock_abbr = m.group("abbr")
        info = self.company_mapping.get(stock_abbr)
        if not info:
            info = self._extract_company_from_pdf(path, stock_abbr)
        period_name = m.group("period")
        year = int(m.group("year"))
        is_summary = "摘要" in period_name
        normalized = period_name.replace("摘要", "").replace("全文", "")
        period = f"{year}{PERIOD_MAP[normalized]}"
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
            info = {"stock_code": stock_code, "stock_abbr": stock_code}
        file_date = m.group("date")
        with pdfplumber.open(path) as pdf:
            first_text = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(2, len(pdf.pages))))
        t = SSE_TITLE_RE.search(first_text)
        if t:
            year = int(t.group("year"))
            period_name = t.group("period")
            is_summary = "摘要" in period_name
            normalized = period_name.replace("摘要", "").replace("全文", "")
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
        if month == 3:
            report_year = year
            suffix = "Q1"
        elif month == 4:
            report_year = year - 1
            suffix = "FY"
        elif month in {7, 8}:
            report_year = year
            suffix = "HY"
        elif month == 10:
            report_year = year
            suffix = "Q3"
        else:
            raise ValueError(f"Cannot infer SSE report period from filename date: {file_date}")
        return report_year, f"{report_year}{suffix}", False

    @staticmethod
    def _extract_company_from_pdf(path: Path, stock_abbr: str) -> dict[str, str]:
        code_re = re.compile(r"(?:证券代码|股票代码|公司代码)[：:\s]*(\d{6})")
        with pdfplumber.open(path) as pdf:
            for i in range(min(10, len(pdf.pages))):
                text = pdf.pages[i].extract_text() or ""
                m = code_re.search(text)
                if m:
                    return {"stock_code": m.group(1), "stock_abbr": stock_abbr}
        raise ValueError(f"Unknown company: {stock_abbr} (not in 附件1, and could not extract stock_code from PDF)")

    def _guess_title(self, page_text: str) -> str | None:
        for titles in TABLE_TITLE_PATTERNS.values():
            for title in titles:
                if title in page_text:
                    return title
        return None

    def _classify_table(self, table: ParsedTable, previous_text: str = "") -> str | None:
        if self._count_data_rows(table) < 3:
            compact_preview = self._compact(self._table_rows_text(table, max_rows=12) + (table.title or "") + table.text[:500] + previous_text[-300:])
            if not (
                any(token in compact_preview for token in ("合并现金流量表", "销售商品", "经营活动产生的现金流量"))
                and any(token in compact_preview for token in ("2023年度", "2022年度", "本期发生额", "本期数", "现金流量"))
            ):
                return None

        table_header = self._table_first_rows_text(table)
        table_body = self._table_rows_text(table, max_rows=12)
        full_context = "\n".join(filter(None, [table_header, table.title or "", table.text[:1000], previous_text[-400:]]))
        compact_context = self._compact(full_context)
        compact_body = self._compact(table_body)
        combined_compact = compact_context + compact_body

        if any(token in combined_compact for keyword in map(self._compact, INVALID_TABLE_KEYWORDS) for token in (keyword,)):
            return None
        if any(keyword in combined_compact for keyword in map(self._compact, EXCLUDED_STATEMENT_KEYWORDS)):
            return None
        if self._has_parent_company_marker(table):
            return None
        if "金额" in compact_body and "占比" in compact_body and all(token in compact_body for token in ("营业收入", "净利润", "利润总额")):
            return None

        candidates: list[str] = []
        core_indicator_tokens = (
            "基本每股收益",
            "每股收益",
            "加权平均净资产收益率",
            "净资产收益率",
            "归属于上市公司股东的净利润",
            "归属于上市公司股东",
            "经营活动产生的现金流量净额",
            "营业收入",
        )
        if any(token in table_header for token in TABLE_TITLE_PATTERNS["core_performance_indicators_sheet"]):
            if any(token in compact_body for token in map(self._compact, core_indicator_tokens)):
                candidates.append("core_performance_indicators_sheet")
        elif any(self._compact(token) in compact_context for token in ("主要会计数据和财务指标", "主要会计数据", "主要财务指标")):
            if any(token in compact_body for token in map(self._compact, core_indicator_tokens)):
                candidates.append("core_performance_indicators_sheet")
        if "合并资产负债表" in compact_context and not any(token in combined_compact for token in map(self._compact, EXCLUDED_STATEMENT_KEYWORDS)):
            candidates.append("balance_sheet")
        if any(token in compact_body for token in ("负债合计", "所有者权益合计", "股东权益合计", "资产总计", "资产总额")) and not any(token in combined_compact for token in ("营业收入", "利润总额", "经营活动产生的现金流量净额")):
            candidates.append("balance_sheet")
        if any(token in compact_context for token in ("合并利润表", "合并年初到报告期末利润表")):
            candidates.append("income_sheet")
        elif ("金额" in compact_body and any(token in compact_body for token in ("营业收入", "营业收入合计", "营业收入总额", "手续费及佣金净收入", "利润总额", "净利润")) and any(token in compact_body for token in ("所得税费用", "营业利润", "营业支出", "信用减值损失"))):
            candidates.append("income_sheet")
        if any(token in compact_context for token in ("合并现金流量表", "合并年初到报告期末现金流量表")):
            candidates.append("cash_flow_sheet")
        elif (
            any(token in compact_body for token in ("经营活动产生的现金流量净额", "现金及现金等价物净增加额", "现金及现金等价物的净增加额", "投资活动产生的现金流量净额", "筹资活动产生的现金流量净额"))
            and any(token in combined_compact for token in ("销售商品", "购买商品", "收回投资收到的现金", "取得借款收到的现金", "现金流入小计", "现金流出小计"))
        ):
            candidates.append("cash_flow_sheet")
        elif ("小计" in compact_body and any(token in compact_body for token in ("经营活动产生的现金流量净额", "现金及现金等价物净增加额", "投资活动产生的现金流量净额", "筹资活动产生的现金流量净额"))):
            candidates.append("cash_flow_sheet")
        if not candidates:
            if "流动资产" in table_header and any(token in compact_body for token in ("货币资金", "资产总计")):
                candidates.append("balance_sheet")
            if any(token in table_header for token in ("营业收入", "营业总收入", "手续费及佣金净收入")) and "利润总额" in compact_body:
                candidates.append("income_sheet")
            if any(token in table_header for token in ("销售商品", "经营活动产生的现金流量净额", "现金及现金等价物净增加额")):
                candidates.append("cash_flow_sheet")

        for table_type in dict.fromkeys(candidates):
            if self._has_confirmation_keyword(table_type, compact_context + compact_body):
                return table_type
        return None

    @staticmethod
    def _table_first_rows_text(table: ParsedTable) -> str:
        parts = []
        for row in table.raw_rows[:3]:
            for cell in row:
                if cell:
                    parts.append(str(cell).replace("\n", ""))
        return " ".join(parts)

    @staticmethod
    def _table_rows_text(table: ParsedTable, max_rows: int = 12) -> str:
        parts = []
        for row in table.raw_rows[:max_rows]:
            for cell in row:
                if cell:
                    parts.append(str(cell).replace("\n", ""))
        return " ".join(parts)

    @staticmethod
    def _compact(text: str) -> str:
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _count_data_rows(table: ParsedTable) -> int:
        count = 0
        for row in table.raw_rows:
            if not row:
                continue
            non_empty = [str(cell).strip() for cell in row if cell not in (None, "") and str(cell).strip()]
            if len(non_empty) >= 2:
                count += 1
        return count

    @staticmethod
    def _has_parent_company_marker(table: ParsedTable) -> bool:
        for row in table.raw_rows[:5]:
            row_text = "".join(str(c) for c in row if c)
            if "母公司" in row_text:
                return True
        return False

    def _has_confirmation_keyword(self, table_type: str, compact_context: str) -> bool:
        return any(self._compact(keyword) in compact_context for keyword in CONFIRM_KEYWORDS.get(table_type, ()))

    def _merge_cross_page_tables(self, tables: list[ParsedTable]) -> list[ParsedTable]:
        merged: list[ParsedTable] = []
        last_merged_page: int = 0
        pending_cross_page: ParsedTable | None = None
        for table in tables:
            if not merged:
                merged.append(table)
                last_merged_page = table.page_number
                pending_cross_page = table if table.table_type else None
                continue
            prev = merged[-1]
            same_page = table.page_number == prev.page_number
            near_page = table.page_number - last_merged_page <= 3 and table.page_number > prev.page_number
            if same_page:
                if prev.table_type is None and table.table_type and not self._has_parent_company_marker(table):
                    if table.page_number == prev.page_number and table.page_number > 1 and any(token in self._compact((table.title or "") + self._table_first_rows_text(table)) for token in ("合并现金流量表", "现金流量净额", "销售商品")):
                        leading_rows = self._extract_trailing_context_rows(prev)
                    else:
                        leading_rows = self._leading_non_numeric_rows(prev)
                    if leading_rows:
                        table.raw_rows = leading_rows + table.raw_rows
                    merged.append(table)
                    pending_cross_page = table
                elif prev.table_type and table.table_type is None and not self._has_distinct_confirmation(prev.table_type, table) and not self._has_parent_company_marker(table):
                    table.table_type = prev.table_type
                    prev.raw_rows.extend(table.raw_rows)
                    prev.text += "\n" + table.text
                    pending_cross_page = prev
                else:
                    merged.append(table)
                    pending_cross_page = table if table.table_type else pending_cross_page
                last_merged_page = table.page_number
                continue
            if prev.table_type and table.table_type == prev.table_type and near_page:
                prev.raw_rows.extend(table.raw_rows)
                prev.text += "\n" + table.text
                last_merged_page = table.page_number
                pending_cross_page = prev
                continue
            if prev.table_type and table.table_type is None and near_page and not self._has_distinct_confirmation(prev.table_type, table) and not self._has_parent_company_marker(table):
                table.table_type = prev.table_type
                prev.raw_rows.extend(table.raw_rows)
                prev.text += "\n" + table.text
                last_merged_page = table.page_number
                pending_cross_page = prev
                continue
            if (
                pending_cross_page
                and table.table_type == pending_cross_page.table_type
                and table.page_number > pending_cross_page.page_number
                and table.page_number - pending_cross_page.page_number <= 3
            ):
                pending_cross_page.raw_rows.extend(table.raw_rows)
                pending_cross_page.text += "\n" + table.text
                last_merged_page = table.page_number
                continue
            merged.append(table)
            last_merged_page = table.page_number
            pending_cross_page = table if table.table_type else pending_cross_page
        return merged

    @staticmethod
    def _extract_trailing_context_rows(table: ParsedTable, max_rows: int = 12) -> list[list[Any]]:
        context_rows: list[list[Any]] = []
        capture = False
        for row in table.raw_rows[-max_rows:]:
            row_text = "".join(str(cell) for cell in row if cell)
            compact = re.sub(r"\s+", "", row_text)
            if not capture and any(token in compact for token in ("合并现金流量表", "现金流量表", "项目附注", "项目2023年度", "项目2024年度")):
                capture = True
            if capture:
                context_rows.append(row)
        return context_rows

    @staticmethod
    def _leading_non_numeric_rows(table: ParsedTable, max_rows: int = 8) -> list[list[Any]]:
        rows: list[list[Any]] = []
        for row in table.raw_rows[:max_rows]:
            cells = [str(cell).strip() for cell in row if cell not in (None, "") and str(cell).strip()]
            if not cells:
                continue
            if any(re.fullmatch(r"-?\d+(?:,\d{3})*(?:\.\d+)?", cell.replace("\n", "")) for cell in cells):
                break
            rows.append(row)
        return rows

    def _has_distinct_confirmation(self, table_type: str, table: ParsedTable) -> bool:
        context = self._compact(self._table_first_rows_text(table))
        for other_type, keywords in CONFIRM_KEYWORDS.items():
            if other_type == table_type:
                continue
            if any(self._compact(keyword) in context for keyword in keywords):
                return True
        return False

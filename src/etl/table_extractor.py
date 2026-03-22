from __future__ import annotations

import math
import re
from typing import Any

from src.etl.pdf_parser import ParsedPDF, ParsedTable
from src.etl.schema import FieldMeta, load_schema_metadata


BASE_COLUMNS = {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}

ALIASES = {
    "income_sheet": {
        "净利润": "net_profit",
        "其他收益": "other_income",
        "营业总收入": "total_operating_revenue",
        "营业收入": "total_operating_revenue",
        "营业成本": "operating_expense_cost_of_sales",
        "销售费用": "operating_expense_selling_expenses",
        "管理费用": "operating_expense_administrative_expenses",
        "财务费用": "operating_expense_financial_expenses",
        "研发费用": "operating_expense_rnd_expenses",
        "税金及附加": "operating_expense_taxes_and_surcharges",
        "营业总成本": "total_operating_expenses",
        "营业利润": "operating_profit",
        "利润总额": "total_profit",
        "资产减值损失": "asset_impairment_loss",
        "信用减值损失": "credit_impairment_loss",
    },
    "balance_sheet": {
        "货币资金": "asset_cash_and_cash_equivalents",
        "应收账款": "asset_accounts_receivable",
        "存货": "asset_inventory",
        "交易性金融资产": "asset_trading_financial_assets",
        "在建工程": "asset_construction_in_progress",
        "资产总计": "asset_total_assets",
        "负债和所有者权益总计": "asset_total_assets",
        "应付账款": "liability_accounts_payable",
        "预收款项": "liability_advance_from_customers",
        "负债合计": "liability_total_liabilities",
        "合同负债": "liability_contract_liabilities",
        "短期借款": "liability_short_term_loans",
        "未分配利润": "equity_unappropriated_profit",
        "所有者权益合计": "equity_total_equity",
        "股东权益合计": "equity_total_equity",
        "所有者权益（或股东权益）合计": "equity_total_equity",
    },
    "cash_flow_sheet": {
        "现金及现金等价物净增加额": "net_cash_flow",
        "五、现金及现金等价物净增加额": "net_cash_flow",
        "经营活动产生的现金流量净额": "operating_cf_net_amount",
        "销售商品、提供劳务收到的现金": "operating_cf_cash_from_sales",
        "投资活动产生的现金流量净额": "investing_cf_net_amount",
        "投资支付的现金": "investing_cf_cash_for_investments",
        "收回投资收到的现金": "investing_cf_cash_from_investment_recovery",
        "取得借款收到的现金": "financing_cf_cash_from_borrowing",
        "偿还债务支付的现金": "financing_cf_cash_for_debt_repayment",
        "筹资活动产生的现金流量净额": "financing_cf_net_amount",
    },
    "core_performance_indicators_sheet": {
        "基本每股收益（元/股）": "eps",
        "基本每股收益": "eps",
        "营业收入": "total_operating_revenue",
        "营业总收入": "total_operating_revenue",
        "归属于上市公司股东的净利润": "net_profit_10k_yuan",
        "归属于上市公司股东的扣除非经常性损益的净利润": "net_profit_excl_non_recurring",
        "归属于上市公司股东的每股净资产": "net_asset_per_share",
        "每股净资产": "net_asset_per_share",
        "加权平均净资产收益率": "roe",
        "每股经营现金流量": "operating_cf_per_share",
        "每股经营活动产生的现金流量净额": "operating_cf_per_share",
        "毛利率": "gross_profit_margin",
        "净利率": "net_profit_margin",
        "扣除非经常性损益后的加权平均净资产收益率": "roe_weighted_excl_non_recurring",
    },
}

UNIT_RE = re.compile(r"单位[：:]\s*([人民币]*)(元|万元)")
YEAR_HEADER_RE = re.compile(r"20\d{2}年(?:末)?")


class TableExtractor:
    def __init__(self) -> None:
        self.schema = load_schema_metadata()
        self.meta_by_field = {
            table: {field.name: field for field in fields}
            for table, fields in self.schema.items()
        }

    def extract(self, parsed_pdf: ParsedPDF) -> tuple[dict[str, dict[str, Any]], list[str]]:
        records = {
            table_name: {
                "serial_number": 1,
                "stock_code": parsed_pdf.stock_code,
                "stock_abbr": parsed_pdf.stock_abbr,
                "report_period": parsed_pdf.report_period,
                "report_year": parsed_pdf.report_year,
            }
            for table_name in self.schema
        }
        warnings: list[str] = []
        for table in parsed_pdf.tables:
            if not table.table_type:
                continue
            source_unit = self._detect_source_unit(table)
            if table.table_type == "core_performance_indicators_sheet":
                self._extract_core_metrics(table, records[table.table_type], parsed_pdf.report_period, source_unit, warnings)
            else:
                self._extract_statement_table(table, table.table_type, records[table.table_type], source_unit, warnings)
        self._compute_derived_fields(records)
        income = records["income_sheet"]
        core = records["core_performance_indicators_sheet"]
        balance = records["balance_sheet"]
        if income.get("net_profit") is None and core.get("net_profit_10k_yuan") is not None:
            income["net_profit"] = core["net_profit_10k_yuan"]
        if income.get("total_operating_revenue") is None and core.get("total_operating_revenue") is not None:
            income["total_operating_revenue"] = core["total_operating_revenue"]
        if balance.get("asset_total_assets") is None:
            for text in parsed_pdf.page_texts:
                unit = self._detect_text_unit(text)
                m = re.search(r"资产总计\s+(-?[\d,]+(?:\.\d+)?)", text.replace("\n", " "))
                if m:
                    balance["asset_total_assets"] = self._convert_value(m.group(1), self.meta_by_field["balance_sheet"]["asset_total_assets"], unit)
                    break
        return records, warnings

    def _extract_statement_table(
        self,
        table: ParsedTable,
        table_type: str,
        target: dict[str, Any],
        source_unit: str | None,
        warnings: list[str],
    ) -> None:
        aliases = ALIASES[table_type]
        for row in table.raw_rows:
            if not row:
                continue
            cells = [self._clean_text(cell) for cell in row if cell not in (None, "")]
            if len(cells) < 2:
                continue
            label = cells[0]
            value = self._find_first_numeric(cells[1:])
            field = aliases.get(label) or aliases.get(self._normalize_label(label))
            if field and value is not None:
                target[field] = self._convert_value(value, self.meta_by_field[table_type][field], source_unit)
            elif value is not None and label not in aliases and label not in {"项目", "附注", "流动资产：", "负债合计", "所有者权益（或股东权益）"}:
                warnings.append(f"Unmapped {table_type} field: {label}")

    def _extract_core_metrics(
        self,
        table: ParsedTable,
        target: dict[str, Any],
        report_period: str,
        source_unit: str | None,
        warnings: list[str],
    ) -> None:
        aliases = ALIASES["core_performance_indicators_sheet"]
        header = self._extract_header_cells(table)
        period_key = self._infer_core_period_key(report_period)
        for row in table.raw_rows:
            if not row:
                continue
            normalized_row = [self._clean_text(cell) if cell not in (None, "") else "" for cell in row]
            cells = [cell for cell in normalized_row if cell]
            if len(cells) < 2:
                continue
            label = cells[0]
            field = aliases.get(label)
            if field:
                value = self._select_core_value(normalized_row, header, period_key)
                if value is not None:
                    target[field] = self._convert_value(value, self.meta_by_field["core_performance_indicators_sheet"][field], source_unit)
                    continue
            if label in {"项目", "本报告期", "本报告期末"} or any(token in label for token in ("第一季度", "第二季度", "第三季度", "第四季度", "一季度", "二季度", "三季度", "四季度")):
                continue
            if self._find_first_numeric(cells[1:]) is not None and label not in aliases:
                warnings.append(f"Unmapped core field: {label}")

    def _compute_derived_fields(self, records: dict[str, dict[str, Any]]) -> None:
        balance = records["balance_sheet"]
        if balance.get("asset_total_assets") is not None and balance.get("liability_total_liabilities") is not None:
            total_assets = balance["asset_total_assets"]
            total_liabilities = balance["liability_total_liabilities"]
            if total_assets:
                balance["asset_liability_ratio"] = round(total_liabilities / total_assets * 100, 4)
            if balance.get("equity_total_equity") is None:
                balance["equity_total_equity"] = round(total_assets - total_liabilities, 2)

        cash = records["cash_flow_sheet"]
        net_cash_flow = cash.get("net_cash_flow")  # in 元
        if net_cash_flow not in (None, 0):
            for numerator, ratio_field in [
                ("operating_cf_net_amount", "operating_cf_ratio_of_net_cf"),
                ("investing_cf_net_amount", "investing_cf_ratio_of_net_cf"),
                ("financing_cf_net_amount", "financing_cf_ratio_of_net_cf"),
            ]:
                numerator_value = cash.get(numerator)  # in 万元
                if numerator_value is not None:
                    # Convert numerator from 万元 to 元 to match denominator
                    cash[ratio_field] = round((numerator_value * 10000 / net_cash_flow) * 100, 4)

    @staticmethod
    def _normalize_label(label: str) -> str:
        """Strip numbering prefixes like '一、' '二、' '（一）' and parenthetical notes."""
        text = re.sub(r"^[一二三四五六七八九十]+、", "", label)
        text = re.sub(r"^（[一二三四五六七八九十\d]+）", "", text)
        text = re.sub(r"（[^）]*）$", "", text)  # trailing parenthetical
        text = re.sub(r"\([^)]*\)$", "", text)
        return text.strip()

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = str(value).replace("\n", "").strip()
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _find_first_numeric(cells: list[str]) -> str | None:
        for cell in cells:
            cleaned = cell.replace(",", "")
            if re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
                return cell
        return None

    def _select_core_value(self, row: list[str], header: list[str], period_key: str) -> str | None:
        if not header:
            return self._find_first_numeric([cell for cell in row[1:] if cell])
        candidates = self._candidate_period_headers(period_key)
        for idx, title in enumerate(header[1:], start=1):
            normalized = self._clean_text(title)
            if normalized and any(token in normalized for token in candidates):
                value = row[idx] if idx < len(row) else ""
                if value and self._is_numeric_text(value):
                    return value
        for idx, title in enumerate(header[1:], start=1):
            normalized = self._clean_text(title)
            if period_key == "FY" and YEAR_HEADER_RE.fullmatch(normalized):
                value = row[idx] if idx < len(row) else ""
                if value and self._is_numeric_text(value):
                    return value
        return self._find_first_numeric([cell for cell in row[1:] if cell])

    @staticmethod
    def _infer_core_period_key(report_period: str) -> str:
        if report_period.endswith("FY"):
            return "FY"
        return report_period[-2:]

    @staticmethod
    def _candidate_period_headers(period_key: str) -> tuple[str, ...]:
        mapping = {
            "Q1": ("第一季度", "一季度", "本报告期", "本报告期末", "1-3月份"),
            "HY": ("半年度", "上半年", "本报告期", "本报告期末", "1-6月", "1-6月份"),
            "Q3": ("第三季度", "三季度", "本报告期", "本报告期末", "7-9月份", "9月30日"),
            "FY": ("本期", "本报告期", "本期末"),
        }
        return mapping.get(period_key, tuple())

    def _extract_header_cells(self, table: ParsedTable) -> list[str]:
        for row in table.raw_rows[:4]:
            normalized = [self._clean_text(cell) if cell not in (None, "") else "" for cell in row]
            non_empty = [cell for cell in normalized if cell]
            if len(non_empty) >= 2 and any(self._looks_like_header_cell(cell) for cell in non_empty[1:]):
                return normalized
        return []

    @staticmethod
    def _looks_like_header_cell(text: str) -> bool:
        return any(token in text for token in ("季度", "年度", "本报告期", "本期", "期末", "月份", "年"))

    def _detect_source_unit(self, table: ParsedTable) -> str | None:
        text = "\n".join(filter(None, [table.title or "", table.text, self._flatten_rows(table.raw_rows)]))
        return self._detect_text_unit(text)

    @staticmethod
    def _flatten_rows(rows: list[list[Any]]) -> str:
        return "\n".join(" ".join(str(cell) for cell in row if cell not in (None, "")) for row in rows)

    def _detect_text_unit(self, text: str) -> str | None:
        match = UNIT_RE.search(text)
        if match:
            return match.group(2)
        return None

    @staticmethod
    def _is_numeric_text(text: str) -> bool:
        cleaned = text.replace(",", "").replace("%", "")
        return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned))

    @staticmethod
    def _parse_number(text: str) -> float:
        text = text.replace(",", "")
        text = text.replace("%", "")
        text = text.replace("—", "").replace("--", "")
        if not text:
            raise ValueError("empty numeric text")
        return float(text)

    def _convert_value(self, value: str, meta: FieldMeta, source_unit: str | None) -> float:
        numeric = self._parse_number(value)
        if meta.unit == "万元":
            if source_unit == "元":
                return round(numeric / 10000, 2)
            return round(numeric, 2)
        if meta.unit == "元":
            if source_unit == "万元":
                return round(numeric * 10000, 2)
            return round(numeric, 2)
        if meta.unit in {"%", "比率"}:
            return round(numeric, 4)
        return round(numeric, 4)

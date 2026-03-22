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
        "四、净利润（净亏损以\"－\"号填列）": "net_profit",
        "四、净利润（净亏损以“－”号填列）": "net_profit",
        "其他收益": "other_income",
        "一、营业总收入": "total_operating_revenue",
        "营业总收入": "total_operating_revenue",
        "营业成本": "operating_expense_cost_of_sales",
        "销售费用": "operating_expense_selling_expenses",
        "管理费用": "operating_expense_administrative_expenses",
        "财务费用": "operating_expense_financial_expenses",
        "研发费用": "operating_expense_rnd_expenses",
        "税金及附加": "operating_expense_taxes_and_surcharges",
        "二、营业总成本": "total_operating_expenses",
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
        "加权平均净资产收益率": "roe",
        "经营活动产生的现金流量净额": "operating_cf_per_share",
        "毛利率": "gross_profit_margin",
        "净利率": "net_profit_margin",
        "扣除非经常性损益后的加权平均净资产收益率": "roe_weighted_excl_non_recurring",
    },
}


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
            if table.table_type == "core_performance_indicators_sheet":
                self._extract_core_metrics(table, records[table.table_type], warnings)
            else:
                self._extract_statement_table(table, table.table_type, records[table.table_type], warnings)
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
                m = re.search(r"资产总计\s+(-?[\d,]+(?:\.\d+)?)", text.replace("\n", " "))
                if m:
                    balance["asset_total_assets"] = round(float(m.group(1).replace(',', '')) / 10000, 2)
                    break
        return records, warnings

    def _extract_statement_table(self, table: ParsedTable, table_type: str, target: dict[str, Any], warnings: list[str]) -> None:
        aliases = ALIASES[table_type]
        for row in table.raw_rows:
            if not row:
                continue
            cells = [self._clean_text(cell) for cell in row if cell not in (None, "")]
            if len(cells) < 2:
                continue
            label = cells[0]
            value = self._find_first_numeric(cells[1:])
            field = aliases.get(label)
            if field and value is not None:
                target[field] = self._convert_value(value, self.meta_by_field[table_type][field])
            elif value is not None and label not in aliases and label not in {"项目", "附注", "流动资产：", "负债合计", "所有者权益（或股东权益）"}:
                warnings.append(f"Unmapped {table_type} field: {label}")

    def _extract_core_metrics(self, table: ParsedTable, target: dict[str, Any], warnings: list[str]) -> None:
        aliases = ALIASES["core_performance_indicators_sheet"]
        quarter_labels = {"第一季度": 1, "第二季度": 2, "第三季度": 3, "第四季度": 4}
        period_suffix = target["report_period"][-2:]
        for row in table.raw_rows:
            if not row:
                continue
            cells = [self._clean_text(cell) for cell in row if cell not in (None, "")]
            if len(cells) < 2:
                continue
            label = cells[0]
            field = aliases.get(label)
            if field:
                value = self._select_core_value(cells, period_suffix)
                if value is not None:
                    target[field] = self._convert_value(value, self.meta_by_field["core_performance_indicators_sheet"][field])
                    continue
            if any(k in label for k in quarter_labels) or label in {"项目", "本报告期", "本报告期末"}:
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
        net_cash_flow = cash.get("net_cash_flow")
        if net_cash_flow not in (None, 0):
            for numerator, ratio_field in [
                ("operating_cf_net_amount", "operating_cf_ratio_of_net_cf"),
                ("investing_cf_net_amount", "investing_cf_ratio_of_net_cf"),
                ("financing_cf_net_amount", "financing_cf_ratio_of_net_cf"),
            ]:
                if cash.get(numerator) is not None:
                    cash[ratio_field] = round((cash[numerator] * 10000) / net_cash_flow * 100, 4)

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

    def _select_core_value(self, cells: list[str], period_suffix: str) -> str | None:
        if period_suffix == "FY":
            return self._find_first_numeric(cells[1:])
        if period_suffix in {"Q1", "HY", "Q3"}:
            return self._find_first_numeric(cells[1:])
        return None

    @staticmethod
    def _parse_number(text: str) -> float:
        text = text.replace(",", "")
        text = text.replace("%", "")
        text = text.replace("—", "").replace("--", "")
        if not text:
            raise ValueError("empty numeric text")
        return float(text)

    def _convert_value(self, value: str, meta: FieldMeta) -> float:
        numeric = self._parse_number(value)
        if meta.unit == "万元":
            return round(numeric / 10000, 2)
        if meta.unit in {"元", "%", "比率", ""}:
            return round(numeric, 4) if meta.unit in {"%", "比率"} else round(numeric, 2 if meta.unit == "元" else 4)
        return numeric

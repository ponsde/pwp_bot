from __future__ import annotations

import re
from typing import Any

from src.etl.pdf_parser import ParsedPDF, ParsedTable
from src.etl.schema import FieldMeta, load_schema_metadata


BASE_COLUMNS = {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}
NET_PROFIT_PARENT_LABELS = (
    "归属于母公司股东的净利润",
    "归属于母公司所有者的净利润",
    "归属于上市公司股东的净利润",
    "归属母公司净利润",
)

INCOME_ALIASES = {
    "净利润": "net_profit",
    "归属于母公司所有者的净利润": "net_profit",
    "归属于母公司股东的净利润": "net_profit",
    "归属于上市公司股东的净利润": "net_profit",
    "归属于上市公司股东": "net_profit",
    "归属母公司净利润": "net_profit",
    "营业收入": "total_operating_revenue",
    "营业总收入": "total_operating_revenue",
    "营业成本": "operating_expense_cost_of_sales",
    "销售费用": "operating_expense_selling_expenses",
    "管理费用": "operating_expense_administrative_expenses",
    "财务费用": "operating_expense_financial_expenses",
    "研发费用": "operating_expense_rnd_expenses",
    "研发经费": "operating_expense_rnd_expenses",
    "税金及附加": "operating_expense_taxes_and_surcharges",
    "营业税金及附加": "operating_expense_taxes_and_surcharges",
    "营业总成本": "total_operating_expenses",
    "营业总支出": "total_operating_expenses",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "其他收益": "other_income",
    "资产减值损失": "asset_impairment_loss",
    "信用减值损失": "credit_impairment_loss",
}

BALANCE_ALIASES = {
    "货币资金": "asset_cash_and_cash_equivalents",
    "应收账款": "asset_accounts_receivable",
    "应收帐款": "asset_accounts_receivable",
    "存货": "asset_inventory",
    "交易性金融资产": "asset_trading_financial_assets",
    "在建工程": "asset_construction_in_progress",
    "资产总计": "asset_total_assets",
    "资产合计": "asset_total_assets",
    "总资产": "asset_total_assets",
    "资产总额": "asset_total_assets",
    "应付账款": "liability_accounts_payable",
    "应付帐款": "liability_accounts_payable",
    "预收款项": "liability_advance_from_customers",
    "预收账款": "liability_advance_from_customers",
    "负债合计": "liability_total_liabilities",
    "总负债": "liability_total_liabilities",
    "负债总计": "liability_total_liabilities",
    "合同负债": "liability_contract_liabilities",
    "短期借款": "liability_short_term_loans",
    "未分配利润": "equity_unappropriated_profit",
    "所有者权益合计": "equity_total_equity",
    "股东权益合计": "equity_total_equity",
    "所有者权益或股东权益合计": "equity_total_equity",
    "股本": "share_capital",
    "实收资本": "share_capital",
    "实收资本或股本": "share_capital",
}

CASHFLOW_ALIASES = {
    "现金及现金等价物净增加额": "net_cash_flow",
    "现金及现金等价物的净增加额": "net_cash_flow",
    "经营活动产生的现金流量净额": "operating_cf_net_amount",
    "销售商品、提供劳务收到的现金": "operating_cf_cash_from_sales",
    "销售商品及提供劳务收到的现金": "operating_cf_cash_from_sales",
    "销售商品提供劳务收到的现金": "operating_cf_cash_from_sales",
    "投资活动产生的现金流量净额": "investing_cf_net_amount",
    "投资支付的现金": "investing_cf_cash_for_investments",
    "收回投资收到的现金": "investing_cf_cash_from_investment_recovery",
    "收到的投资回收现金": "investing_cf_cash_from_investment_recovery",
    "收回投资所得现金": "investing_cf_cash_from_investment_recovery",
    "取得借款收到的现金": "financing_cf_cash_from_borrowing",
    "偿还债务支付的现金": "financing_cf_cash_for_debt_repayment",
    "筹资活动产生的现金流量净额": "financing_cf_net_amount",
}

CORE_ALIASES = {
    "基本每股收益": "eps",
    "基本每股收益元股": "eps",
    "基本每股收": "eps",
    "每股收益": "eps",
    "营业收入": "total_operating_revenue",
    "营业收入元": "total_operating_revenue",
    "营业总收入": "total_operating_revenue",
    "归属于上市公司股东的净利润": "net_profit_10k_yuan",
    "归属于上市公司股东的净利润元": "net_profit_10k_yuan",
    "归属于上市公司股东": "net_profit_10k_yuan",
    "归属于母公司所有者的净利润": "net_profit_10k_yuan",
    "归属于母公司股东的净利润": "net_profit_10k_yuan",
    "归属母公司净利润": "net_profit_10k_yuan",
    "净利润": "net_profit_10k_yuan",
    "归属于上市公司股东的扣除非经常性损益的净利润": "net_profit_excl_non_recurring",
    "归属于上市公司股东的扣除非经常性损益的净利润元": "net_profit_excl_non_recurring",
    "归属于上市公司股东的扣除非经常": "net_profit_excl_non_recurring",
    "扣除非经常性损益后归属于母公司所有者的净利润": "net_profit_excl_non_recurring",
    "扣非净利润": "net_profit_excl_non_recurring",
    "归属于上市公司股东的每股净资产": "net_asset_per_share",
    "每股净资产": "net_asset_per_share",
    "每股净资产元股": "net_asset_per_share",
    "加权平均净资产收益率": "roe",
    "加权平均净资产收益率%": "roe",
    "加权平均净资产收益": "roe",
    "加权平均净": "roe",
    "净资产收益率": "roe",
    "每股经营现金流量": "operating_cf_per_share",
    "每股经营活动产生的现金流量净额": "operating_cf_per_share",
    "毛利率": "gross_profit_margin",
    "销售毛利率": "gross_profit_margin",
    "净利率": "net_profit_margin",
    "销售净利率": "net_profit_margin",
    "扣除非经常性损益后的加权平均净资产收益率": "roe_weighted_excl_non_recurring",
}

ALIASES = {
    "income_sheet": INCOME_ALIASES,
    "balance_sheet": BALANCE_ALIASES,
    "cash_flow_sheet": CASHFLOW_ALIASES,
    "core_performance_indicators_sheet": CORE_ALIASES,
}

PREFIX_RE = re.compile(r"^(?:[一二三四五六七八九十]+、|[（(][一二三四五六七八九十\d]+[)）]|\d+[\.、]|[加减]：|其中[:：])")
BRACKET_NOTE_RE = re.compile(r"[（(][^）)]*[)）]")
UNIT_RE = re.compile(r"单位[：:]\s*(?:人民币)?(元|万元|千元|百万元)")
NUMERIC_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?%?")


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
        page_units = [self._detect_text_unit(text) for text in parsed_pdf.page_texts]
        for table in parsed_pdf.tables:
            if not table.table_type:
                continue
            source_unit = self._detect_source_unit(table, page_units)
            if table.table_type == "core_performance_indicators_sheet":
                self._extract_core_metrics(table, records[table.table_type], parsed_pdf.report_period, source_unit, warnings)
            else:
                self._extract_statement_table(table, table.table_type, records[table.table_type], source_unit, warnings)

        self._fill_income_sheet_from_page_text(parsed_pdf, records["income_sheet"])
        self._compute_derived_fields(records)
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
        pending_label = ""
        for row in table.raw_rows:
            if not row:
                continue
            cells = [self._clean_text(cell) for cell in row if cell not in (None, "")]
            if len(cells) < 2:
                if cells and not self._find_first_numeric(cells):
                    text = cells[0]
                    if self._is_section_header(text):
                        pending_label = ""
                    else:
                        candidate = self._normalize_label(pending_label + text)
                        if aliases.get(candidate):
                            pending_label = candidate
                        else:
                            pending_label = ""
                continue
            label = self._normalize_label(pending_label + cells[0])
            pending_label = ""
            if not label or label in {"项目", "科目", "资产", "负债", "流动资产", "非流动资产", "流动负债", "非流动负债"}:
                continue
            field = aliases.get(label)
            if not field:
                continue
            value = self._find_first_numeric(cells[1:])
            if value is None:
                pending_label = label
                continue
            converted = self._convert_statement_value(table_type, field, value, source_unit)
            if field not in target:
                target[field] = converted

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
        year = report_period[:4]
        period_key = self._infer_core_period_key(report_period)
        rows = [
            [self._clean_text(cell) if cell not in (None, "") else "" for cell in row]
            for row in table.raw_rows
            if row
        ]
        idx = 0
        while idx < len(rows):
            row = rows[idx]
            if not any(cell for cell in row):
                idx += 1
                continue
            label_cells, row_numeric_values = self._split_core_row_segments(row)
            if not label_cells:
                idx += 1
                continue
            label = self._normalize_label("".join(label_cells))
            consumed_rows = 0
            next_idx = idx + 1
            combined_numeric_values = list(row_numeric_values)
            while next_idx < len(rows):
                next_row = rows[next_idx]
                next_label_cells, next_numeric_values = self._split_core_row_segments(next_row)
                if not next_label_cells:
                    if next_numeric_values:
                        combined_numeric_values.extend(next_numeric_values)
                    break
                next_label = self._normalize_label(label + "".join(next_label_cells))
                next_field = aliases.get(next_label)
                if next_field is None and any(self._is_numeric_text(cell) for cell in next_row if cell):
                    break
                label = next_label
                combined_numeric_values.extend(next_numeric_values)
                consumed_rows += 1
                next_idx += 1
                if next_field is not None:
                    break
            field = aliases.get(label)
            if not field:
                idx += max(1, consumed_rows + 1)
                continue
            value = self._select_core_value(row, header, period_key, year)
            if value is None:
                value = self._select_value_from_candidates(combined_numeric_values, period_key)
            if value is not None and field not in target:
                target[field] = self._convert_value(value, self._get_field_meta("core_performance_indicators_sheet", field), source_unit)
            idx += max(1, consumed_rows + 1)

    def _compute_derived_fields(self, records: dict[str, dict[str, Any]]) -> None:
        income = records["income_sheet"]
        balance = records["balance_sheet"]
        core = records["core_performance_indicators_sheet"]
        report_period = str(core.get("report_period") or income.get("report_period") or "")

        revenue = income.get("total_operating_revenue")
        net_profit = income.get("net_profit")
        cost_of_sales = income.get("operating_expense_cost_of_sales")

        if (core.get("total_operating_revenue") is None or report_period.endswith("Q3")) and revenue is not None:
            core["total_operating_revenue"] = revenue
        if core.get("net_profit_10k_yuan") is None and net_profit is not None:
            core["net_profit_10k_yuan"] = net_profit
        if core.get("gross_profit_margin") is None and revenue not in (None, 0) and cost_of_sales is not None:
            core["gross_profit_margin"] = round((revenue - cost_of_sales) / revenue * 100, 4)
        if core.get("net_profit_margin") is None and revenue not in (None, 0) and net_profit is not None:
            core["net_profit_margin"] = round(net_profit / revenue * 100, 4)

        share_capital = balance.get("share_capital")
        operating_cf_net_amount = records["cash_flow_sheet"].get("operating_cf_net_amount")
        if core.get("operating_cf_per_share") is None and share_capital not in (None, 0) and operating_cf_net_amount is not None:
            core["operating_cf_per_share"] = round((operating_cf_net_amount * 10000) / share_capital, 4)
        if core.get("net_asset_per_share") is None and balance.get("equity_total_equity") is not None and share_capital not in (None, 0):
            core["net_asset_per_share"] = round((balance["equity_total_equity"] * 10000) / share_capital, 4)

        if core.get("roe") is None and core.get("net_profit_10k_yuan") is not None and balance.get("equity_total_equity") not in (None, 0):
            core["roe"] = round(core["net_profit_10k_yuan"] / balance["equity_total_equity"] * 100, 4)
        if (
            core.get("roe_weighted_excl_non_recurring") is None
            and core.get("net_profit_excl_non_recurring") is not None
            and balance.get("equity_total_equity") not in (None, 0)
        ):
            core["roe_weighted_excl_non_recurring"] = round(
                core["net_profit_excl_non_recurring"] / balance["equity_total_equity"] * 100,
                4,
            )
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
                numerator_value = cash.get(numerator)
                if numerator_value is not None:
                    cash[ratio_field] = round((numerator_value / net_cash_flow) * 100, 4)

    @staticmethod
    def _normalize_label(label: str) -> str:
        text = str(label).replace("\n", "").strip()
        while True:
            new_text = PREFIX_RE.sub("", text)
            if new_text == text:
                break
            text = new_text.strip()
        text = BRACKET_NOTE_RE.sub("", text).strip()
        text = text.replace("/", "").replace("－", "-")
        text = re.sub(r"[：:、,，。\s]+", "", text)
        return text

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = str(value).replace("\n", "").strip()
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _find_first_numeric(cells: list[str]) -> str | None:
        for cell in cells:
            compact = cell.replace(" ", "").replace("\n", "")
            m = NUMERIC_RE.fullmatch(compact)
            if m:
                return compact
        return None

    def _select_core_value(self, row: list[str], header: list[str], period_key: str, year: str = "") -> str | None:
        numeric_cells = [(idx, cell) for idx, cell in enumerate(row[1:], start=1) if cell and self._is_numeric_text(cell)]
        if not header:
            return numeric_cells[0][1] if numeric_cells else None

        target_indices = self._match_header_indices(header, period_key, year)
        for col_idx in target_indices:
            for offset in (0, -1, 1, -2, 2):
                actual_idx = col_idx + offset
                if 1 <= actual_idx < len(row):
                    value = row[actual_idx]
                    if value and self._is_numeric_text(value):
                        return value

        current_period_candidates = self._find_current_period_numeric_indices(header, numeric_cells, period_key)
        if current_period_candidates:
            return current_period_candidates[0][1]
        return numeric_cells[0][1] if numeric_cells else None

    @staticmethod
    def _infer_core_period_key(report_period: str) -> str:
        if report_period.endswith("FY"):
            return "FY"
        return report_period[-2:]

    @staticmethod
    def _candidate_period_headers(period_key: str, year: str = "") -> tuple[str, ...]:
        base = {
            "Q1": ("第一季度", "一季度", "本报告期", "本报告期末", "1-3月份"),
            "HY": ("半年度", "上半年", "本报告期", "本报告期末", "1-6月", "1-6月份"),
            "Q3": ("第三季度", "三季度", "本报告期", "本报告期末", "7-9月份", "9月30日", "年初至报告期末"),
            "FY": ("本期", "本报告期", "本期末", "第四季度"),
        }
        candidates = list(base.get(period_key, ()))
        if year:
            candidates.append(f"{year}年")
        return tuple(candidates)

    def _extract_header_cells(self, table: ParsedTable) -> list[str]:
        for row in table.raw_rows[:12]:
            normalized = [self._clean_text(cell) if cell not in (None, "") else "" for cell in row]
            non_empty = [cell for cell in normalized if cell]
            if len(non_empty) >= 2 and any(self._looks_like_header_cell(cell) for cell in non_empty[1:]):
                return normalized
        return []

    @staticmethod
    def _looks_like_header_cell(text: str) -> bool:
        return any(token in text for token in ("季度", "年度", "本报告期", "本期", "期末", "月份", "年", "同比", "增减"))

    def _detect_source_unit(self, table: ParsedTable, page_units: list[str | None]) -> str | None:
        text = "\n".join(filter(None, [table.title or "", table.text, self._flatten_rows(table.raw_rows)]))
        unit = self._detect_text_unit(text)
        if unit:
            return unit
        if 1 <= table.page_number <= len(page_units):
            unit = page_units[table.page_number - 1]
            if unit:
                return unit
        if table.page_number >= 2 and table.page_number - 2 < len(page_units):
            return page_units[table.page_number - 2]
        return None

    @staticmethod
    def _flatten_rows(rows: list[list[Any]]) -> str:
        return "\n".join(" ".join(str(cell) for cell in row if cell not in (None, "")) for row in rows)

    def _detect_text_unit(self, text: str) -> str | None:
        match = UNIT_RE.search(text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_section_header(text: str) -> bool:
        return text.endswith("：") or text.endswith(":") or text in (
            "流动资产", "非流动资产", "流动负债", "非流动负债",
            "所有者权益", "股东权益", "经营活动", "投资活动", "筹资活动",
        )

    @staticmethod
    def _is_numeric_text(text: str) -> bool:
        cleaned = text.replace(",", "").replace("%", "").replace("\n", "")
        return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned))

    @staticmethod
    def _parse_number(text: str) -> float:
        text = text.replace(",", "").replace("%", "").replace("\n", "")
        text = text.replace("—", "").replace("--", "")
        if not text:
            raise ValueError("empty numeric text")
        return float(text)

    def _convert_value(self, value: str, meta: FieldMeta, source_unit: str | None) -> float:
        numeric = self._parse_number(value)
        source_unit = source_unit or "元"
        if meta.unit == "万元":
            if source_unit == "元":
                return round(numeric / 10000, 2)
            if source_unit == "千元":
                return round(numeric / 10, 2)
            if source_unit == "百万元":
                return round(numeric * 100, 2)
            return round(numeric, 2)
        if meta.unit == "元":
            if source_unit == "万元":
                return round(numeric * 10000, 2)
            if source_unit == "千元":
                return round(numeric * 1000, 2)
            if source_unit == "百万元":
                return round(numeric * 1000000, 2)
            return round(numeric, 2)
        if meta.unit in {"%", "比率"}:
            return round(numeric, 4)
        return round(numeric, 4)

    def _convert_statement_value(self, table_type: str, field: str, value: str, source_unit: str | None) -> float:
        meta = self._get_field_meta(table_type, field)
        if table_type == "cash_flow_sheet" and field == "net_cash_flow":
            meta = FieldMeta(
                name=meta.name,
                label=meta.label,
                sqlite_type=meta.sqlite_type,
                excel_type=meta.excel_type,
                unit="万元",
                description=meta.description,
            )
        return self._convert_value(value, meta, source_unit)

    def _match_header_indices(self, header: list[str], period_key: str, year: str) -> list[int]:
        candidates = self._candidate_period_headers(period_key, year)
        excluded_tokens = ("增减", "同比", "变动", "增长")
        matches: list[int] = []
        for idx, title in enumerate(header):
            normalized = self._clean_text(title)
            if not normalized or any(token in normalized for token in excluded_tokens):
                continue
            if any(token in normalized for token in candidates):
                matches.append(idx)
        if not matches and period_key == "FY" and year:
            for idx, title in enumerate(header):
                normalized = self._clean_text(title)
                if not normalized or any(token in normalized for token in excluded_tokens):
                    continue
                if year in normalized and YEAR_HEADER_RE.fullmatch(normalized):
                    matches.append(idx)
        return matches

    def _find_current_period_numeric_indices(
        self,
        header: list[str],
        numeric_cells: list[tuple[int, str]],
        period_key: str,
    ) -> list[tuple[int, str]]:
        if period_key == "FY":
            return numeric_cells[:1] if numeric_cells else []
        if period_key == "Q3":
            ytd_tokens = ("年初至报告期末", "年初至报", "报告期末")
            filtered = [item for item in numeric_cells if any(token in (header[item[0]] or "") for token in ytd_tokens)]
            if filtered:
                return filtered
        current_tokens = ("本报告期", "本期", "本报告期末", "期末")
        filtered = [item for item in numeric_cells if any(token in (header[item[0]] or "") for token in current_tokens)]
        if filtered:
            return filtered
        if period_key in {"Q1", "HY"} and numeric_cells:
            return numeric_cells[:1]
        return []

    def _split_core_row_segments(self, row: list[str]) -> tuple[list[str], list[str]]:
        label_cells: list[str] = []
        numeric_values: list[str] = []
        for cell in row:
            if not cell or cell in {"—", "--", "-", "不适用"}:
                continue
            if self._is_numeric_text(cell):
                numeric_values.append(cell)
                continue
            label_cells.append(cell)
        return label_cells, numeric_values

    def _select_value_from_candidates(self, numeric_values: list[str], period_key: str) -> str | None:
        if not numeric_values:
            return None
        return numeric_values[0]

    def _fill_income_sheet_from_page_text(self, parsed_pdf: ParsedPDF, target: dict[str, Any]) -> None:
        if target.get("net_profit") is None:
            source_unit = None
            for table in parsed_pdf.tables:
                if table.table_type == "income_sheet":
                    source_unit = self._detect_source_unit(table, [self._detect_text_unit(text) for text in parsed_pdf.page_texts])
                    break
            for label in (*NET_PROFIT_PARENT_LABELS, "净利润"):
                value = self._extract_income_value_from_page_text(parsed_pdf.page_texts, label)
                if value is not None:
                    target["net_profit"] = self._convert_value(value, self._get_field_meta("income_sheet", "net_profit"), source_unit)
                    break

    def _extract_income_value_from_page_text(self, page_texts: list[str], label: str) -> str | None:
        normalized_label = self._normalize_label(label)
        pattern = re.compile(rf"{re.escape(label)}（[^\n]*?填列）\s+(-?\d+(?:,\d{{3}})*(?:\.\d+)?)", re.MULTILINE)
        fallback_pattern = re.compile(
            rf"{re.escape(label)}[：:\s]{{0,20}}(-?\d+(?:,\d{{3}})*(?:\.\d+)?)",
            re.MULTILINE,
        )
        for text in page_texts:
            if normalized_label not in self._normalize_label(text):
                continue
            match = pattern.search(text) or fallback_pattern.search(text)
            if match:
                return match.group(1)
        return None

    def _get_field_meta(self, table_type: str, field: str) -> FieldMeta:
        table_meta = self.meta_by_field[table_type]
        meta = table_meta.get(field)
        if meta is not None:
            return meta
        inferred_unit = ""
        if field == "share_capital":
            inferred_unit = "元"
        return FieldMeta(name=field, label=field, sqlite_type="REAL", excel_type="REAL", unit=inferred_unit, description="inferred")


YEAR_HEADER_RE = re.compile(r"20\d{2}年(?:末)?")

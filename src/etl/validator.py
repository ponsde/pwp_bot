from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


REPORT_PERIOD_RE = re.compile(r"^20\d{2}(FY|Q1|HY|Q3)$")
FATAL_WARNING_MARKERS = ("balance_sheet:", "fatal:")


@dataclass
class ValidationResult:
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(self._is_fatal_warning(warning) for warning in self.warnings)

    @staticmethod
    def _is_fatal_warning(warning: str) -> bool:
        return any(warning.startswith(marker) for marker in FATAL_WARNING_MARKERS)


class DataValidator:
    def validate(self, records: dict[str, dict[str, Any]]) -> ValidationResult:
        warnings: list[str] = []
        self._validate_format(records, warnings)
        self._validate_balance(records, warnings)
        self._validate_income(records, warnings)
        self._validate_cross_table(records, warnings)
        return ValidationResult(warnings=warnings)

    def _validate_format(self, records: dict[str, dict[str, Any]], warnings: list[str]) -> None:
        for table_name, row in records.items():
            period = row.get("report_period")
            if not REPORT_PERIOD_RE.match(str(period)):
                warnings.append(f"{table_name}: invalid report_period {period}")
            for key, value in row.items():
                if key in {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"} or value is None:
                    continue
                if not isinstance(value, (int, float)):
                    warnings.append(f"{table_name}: field {key} should be numeric, got {type(value).__name__}")

        balance = records.get("balance_sheet", {})
        if balance.get("asset_total_assets") is None or balance.get("liability_total_liabilities") is None:
            warnings.append("fatal: missing key balance sheet fields")

    def _validate_balance(self, records: dict[str, dict[str, Any]], warnings: list[str]) -> None:
        row = records["balance_sheet"]
        assets = row.get("asset_total_assets")
        liabilities = row.get("liability_total_liabilities")
        equity = row.get("equity_total_equity")
        if None not in (assets, liabilities, equity):
            diff = round(assets - liabilities - equity, 2)
            tolerance = abs(assets) * 0.01
            if abs(diff) > tolerance:
                warnings.append(f"balance_sheet: assets != liabilities + equity, diff={diff}")

    def _validate_income(self, records: dict[str, dict[str, Any]], warnings: list[str]) -> None:
        row = records["income_sheet"]
        revenue = row.get("total_operating_revenue")
        expenses = row.get("total_operating_expenses")
        other = row.get("other_income") or 0
        op_profit = row.get("operating_profit")
        if None not in (revenue, expenses, op_profit):
            expected = round(revenue - expenses + other, 2)
            if abs(expected - op_profit) > max(10.0, abs(op_profit) * 0.2):
                warnings.append(f"income_sheet: operating_profit reconciliation warning expected≈{expected}, actual={op_profit}")

    def _validate_cross_table(self, records: dict[str, dict[str, Any]], warnings: list[str]) -> None:
        income_net_profit = records["income_sheet"].get("net_profit")
        core_net_profit = records["core_performance_indicators_sheet"].get("net_profit_10k_yuan")
        if None not in (income_net_profit, core_net_profit) and abs(income_net_profit - core_net_profit) > max(10.0, abs(income_net_profit) * 0.2):
            warnings.append(
                f"cross_table: income_sheet.net_profit ({income_net_profit}) != core_performance.net_profit_10k_yuan ({core_net_profit})"
            )

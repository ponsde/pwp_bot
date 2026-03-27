from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.etl.pdf_parser import PDFParser
from src.etl.schema import create_tables, validate_schema
from src.etl.table_extractor import TableExtractor
from src.etl.validator import DataValidator


_PERIOD_ORDER = {"Q1": 1, "HY": 2, "Q3": 3, "FY": 4}


class ETLLoader:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.schema = create_tables(db_path)
        validate_schema(db_path, self.schema)
        self.parser = PDFParser()
        self.extractor = TableExtractor()
        self.validator = DataValidator()

    def load_pdf(self, pdf_path: str | Path) -> dict[str, Any]:
        parsed = self.parser.parse(pdf_path)
        if parsed.is_summary:
            return {"status": "skipped", "reason": "summary_report", "file": str(pdf_path)}
        records, extract_warnings = self.extractor.extract(parsed)
        validation = self.validator.validate(records)
        if not validation.ok:
            return {
                "status": "rejected",
                "file": str(pdf_path),
                "stock_code": parsed.stock_code,
                "report_period": parsed.report_period,
                "warnings": extract_warnings + validation.warnings,
            }
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_share_capital_cache_table(conn)
            share_capital = records.get("balance_sheet", {}).pop("share_capital", None)
            for table_name, row in records.items():
                columns = list(row.keys())
                placeholders = ", ".join(["?"] * len(columns))
                sql = f'INSERT OR REPLACE INTO "{table_name}" ({", ".join(columns)}) VALUES ({placeholders})'
                conn.execute(sql, [row.get(column) for column in columns])
            self._cache_share_capital(conn, records["balance_sheet"], share_capital)
            self._postprocess_fallback_fields(conn)
            self._postprocess_growth_fields(conn)
            conn.commit()
        return {
            "status": "loaded",
            "file": str(pdf_path),
            "stock_code": parsed.stock_code,
            "report_period": parsed.report_period,
            "warnings": extract_warnings + validation.warnings,
        }

    def _ensure_share_capital_cache_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _share_capital_cache (
                stock_code TEXT NOT NULL,
                report_period TEXT NOT NULL,
                share_capital REAL,
                PRIMARY KEY (stock_code, report_period)
            )
            """
        )

    def _cache_share_capital(self, conn: sqlite3.Connection, balance_row: dict[str, Any], share_capital: float | None) -> None:
        if share_capital is None:
            return
        conn.execute(
            """
            INSERT OR REPLACE INTO _share_capital_cache (stock_code, report_period, share_capital)
            VALUES (?, ?, ?)
            """,
            [balance_row.get("stock_code"), balance_row.get("report_period"), share_capital],
        )

    def _postprocess_fallback_fields(self, conn: sqlite3.Connection) -> None:
        core_rows = conn.execute(
            """
            SELECT stock_code, report_period, net_profit_10k_yuan, roe, net_asset_per_share
            FROM core_performance_indicators_sheet
            """
        ).fetchall()
        for stock_code, report_period, net_profit_10k_yuan, roe, net_asset_per_share in core_rows:
            updates: dict[str, float] = {}
            if roe is None and net_profit_10k_yuan is not None:
                equity = self._latest_non_null_balance_value(conn, stock_code, report_period, "equity_total_equity")
                if equity not in (None, 0):
                    updates["roe"] = round(net_profit_10k_yuan / equity * 100, 4)
            if net_asset_per_share is None:
                equity = self._latest_non_null_balance_value(conn, stock_code, report_period, "equity_total_equity")
                share_capital = self._latest_non_null_share_capital(conn, stock_code, report_period)
                if equity is not None and share_capital not in (None, 0):
                    updates["net_asset_per_share"] = round((equity * 10000) / share_capital, 4)
            if updates:
                conn.execute(
                    """
                    UPDATE core_performance_indicators_sheet
                    SET roe = COALESCE(roe, ?),
                        net_asset_per_share = COALESCE(net_asset_per_share, ?)
                    WHERE stock_code = ? AND report_period = ?
                    """,
                    [updates.get("roe"), updates.get("net_asset_per_share"), stock_code, report_period],
                )

    def _latest_non_null_balance_value(
        self,
        conn: sqlite3.Connection,
        stock_code: str,
        current_report_period: str,
        field_name: str,
    ) -> float | None:
        current_year = int(current_report_period[:4])
        current_order = _PERIOD_ORDER.get(current_report_period[4:], 0)
        row = conn.execute(
            f"""
            SELECT {field_name}
            FROM balance_sheet
            WHERE stock_code = ?
              AND {field_name} IS NOT NULL
              AND (report_year < ? OR (report_year = ? AND CASE SUBSTR(report_period, 5)
                WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3 WHEN 'HY' THEN 2 WHEN 'Q1' THEN 1 ELSE 0
              END <= ?))
            ORDER BY report_year DESC, CASE SUBSTR(report_period, 5)
                WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3 WHEN 'HY' THEN 2 WHEN 'Q1' THEN 1 ELSE 0
            END DESC
            LIMIT 1
            """,
            [stock_code, current_year, current_year, current_order],
        ).fetchone()
        return row[0] if row else None

    def _latest_non_null_share_capital(self, conn: sqlite3.Connection, stock_code: str, current_report_period: str) -> float | None:
        current_year = int(current_report_period[:4])
        current_order = _PERIOD_ORDER.get(current_report_period[4:], 0)
        row = conn.execute(
            """
            SELECT share_capital
            FROM _share_capital_cache
            WHERE stock_code = ?
              AND share_capital IS NOT NULL
              AND (CAST(SUBSTR(report_period, 1, 4) AS INTEGER) < ? OR (CAST(SUBSTR(report_period, 1, 4) AS INTEGER) = ? AND CASE SUBSTR(report_period, 5)
                WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3 WHEN 'HY' THEN 2 WHEN 'Q1' THEN 1 ELSE 0
              END <= ?))
            ORDER BY CAST(SUBSTR(report_period, 1, 4) AS INTEGER) DESC, CASE SUBSTR(report_period, 5)
                WHEN 'FY' THEN 4 WHEN 'Q3' THEN 3 WHEN 'HY' THEN 2 WHEN 'Q1' THEN 1 ELSE 0
            END DESC
            LIMIT 1
            """,
            [stock_code, current_year, current_year, current_order],
        ).fetchone()
        return row[0] if row else None

    def _postprocess_growth_fields(self, conn: sqlite3.Connection) -> None:
        self._postprocess_core_growth_fields(conn)
        self._postprocess_balance_growth_fields(conn)
        self._postprocess_income_growth_fields(conn)
        self._postprocess_cashflow_growth_fields(conn)

    def _postprocess_core_growth_fields(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT stock_code, report_period, total_operating_revenue, net_profit_10k_yuan, net_profit_excl_non_recurring
            FROM core_performance_indicators_sheet
            """
        ).fetchall()
        records = {
            (stock_code, report_period): {
                "total_operating_revenue": revenue,
                "net_profit_10k_yuan": net_profit,
                "net_profit_excl_non_recurring": net_profit_excl,
            }
            for stock_code, report_period, revenue, net_profit, net_profit_excl in rows
        }
        for (stock_code, report_period), values in records.items():
            yoy_period = self._previous_yoy_period(report_period)
            updates = {
                "operating_revenue_yoy_growth": self._compute_growth(values["total_operating_revenue"], records.get((stock_code, yoy_period), {}).get("total_operating_revenue")),
                "net_profit_yoy_growth": self._compute_growth(values["net_profit_10k_yuan"], records.get((stock_code, yoy_period), {}).get("net_profit_10k_yuan")),
                "net_profit_excl_non_recurring_yoy": self._compute_growth(values["net_profit_excl_non_recurring"], records.get((stock_code, yoy_period), {}).get("net_profit_excl_non_recurring")),
            }
            conn.execute(
                """
                UPDATE core_performance_indicators_sheet
                SET operating_revenue_yoy_growth = COALESCE(operating_revenue_yoy_growth, ?),
                    net_profit_yoy_growth = COALESCE(net_profit_yoy_growth, ?),
                    net_profit_excl_non_recurring_yoy = COALESCE(net_profit_excl_non_recurring_yoy, ?)
                WHERE stock_code = ? AND report_period = ?
                """,
                [
                    updates["operating_revenue_yoy_growth"],
                    updates["net_profit_yoy_growth"],
                    updates["net_profit_excl_non_recurring_yoy"],
                    stock_code,
                    report_period,
                ],
            )

    def _postprocess_balance_growth_fields(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT stock_code, report_period, asset_total_assets, liability_total_liabilities
            FROM balance_sheet
            """
        ).fetchall()
        records = {
            (stock_code, report_period): {
                "asset_total_assets": total_assets,
                "liability_total_liabilities": total_liabilities,
            }
            for stock_code, report_period, total_assets, total_liabilities in rows
        }
        for (stock_code, report_period), values in records.items():
            yoy_period = self._previous_yoy_period(report_period)
            conn.execute(
                """
                UPDATE balance_sheet
                SET asset_total_assets_yoy_growth = COALESCE(asset_total_assets_yoy_growth, ?),
                    liability_total_liabilities_yoy_growth = COALESCE(liability_total_liabilities_yoy_growth, ?)
                WHERE stock_code = ? AND report_period = ?
                """,
                [
                    self._compute_growth(values["asset_total_assets"], records.get((stock_code, yoy_period), {}).get("asset_total_assets")),
                    self._compute_growth(values["liability_total_liabilities"], records.get((stock_code, yoy_period), {}).get("liability_total_liabilities")),
                    stock_code,
                    report_period,
                ],
            )

    def _postprocess_income_growth_fields(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT stock_code, report_period, total_operating_revenue, net_profit
            FROM income_sheet
            """
        ).fetchall()
        records = {
            (stock_code, report_period): {
                "total_operating_revenue": revenue,
                "net_profit": net_profit,
            }
            for stock_code, report_period, revenue, net_profit in rows
        }
        for (stock_code, report_period), values in records.items():
            yoy_period = self._previous_yoy_period(report_period)
            conn.execute(
                """
                UPDATE income_sheet
                SET operating_revenue_yoy_growth = COALESCE(operating_revenue_yoy_growth, ?),
                    net_profit_yoy_growth = COALESCE(net_profit_yoy_growth, ?)
                WHERE stock_code = ? AND report_period = ?
                """,
                [
                    self._compute_growth(values["total_operating_revenue"], records.get((stock_code, yoy_period), {}).get("total_operating_revenue")),
                    self._compute_growth(values["net_profit"], records.get((stock_code, yoy_period), {}).get("net_profit")),
                    stock_code,
                    report_period,
                ],
            )

    def _postprocess_cashflow_growth_fields(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT stock_code, report_period, net_cash_flow
            FROM cash_flow_sheet
            """
        ).fetchall()
        records = {
            (stock_code, report_period): {
                "net_cash_flow": net_cash_flow,
            }
            for stock_code, report_period, net_cash_flow in rows
        }
        for (stock_code, report_period), values in records.items():
            yoy_period = self._previous_yoy_period(report_period)
            conn.execute(
                """
                UPDATE cash_flow_sheet
                SET net_cash_flow_yoy_growth = COALESCE(net_cash_flow_yoy_growth, ?)
                WHERE stock_code = ? AND report_period = ?
                """,
                [
                    self._compute_growth(values["net_cash_flow"], records.get((stock_code, yoy_period), {}).get("net_cash_flow")),
                    stock_code,
                    report_period,
                ],
            )

    @staticmethod
    def _compute_growth(current: float | None, previous: float | None) -> float | None:
        if current is None or previous in (None, 0):
            return None
        return round((current - previous) / abs(previous) * 100, 4)

    @staticmethod
    def _previous_yoy_period(report_period: str) -> str | None:
        year = int(report_period[:4])
        suffix = report_period[4:]
        if suffix in {"FY", "HY", "Q1", "Q3"}:
            return f"{year - 1}{suffix}"
        return None

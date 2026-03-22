from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.etl.pdf_parser import PDFParser
from src.etl.schema import create_tables, validate_schema
from src.etl.table_extractor import TableExtractor
from src.etl.validator import DataValidator


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
            for table_name, row in records.items():
                columns = list(row.keys())
                placeholders = ", ".join(["?"] * len(columns))
                sql = f'INSERT OR REPLACE INTO "{table_name}" ({", ".join(columns)}) VALUES ({placeholders})'
                conn.execute(sql, [row.get(column) for column in columns])
            conn.commit()
        return {
            "status": "loaded",
            "file": str(pdf_path),
            "stock_code": parsed.stock_code,
            "report_period": parsed.report_period,
            "warnings": extract_warnings + validation.warnings,
        }

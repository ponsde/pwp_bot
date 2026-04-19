"""End-to-end: tiny xlsx + tiny db → audit runs, produces a report."""
from pathlib import Path
import subprocess
import sys

import openpyxl


def _build_mini_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["编号", "问题", "SQL查询语句", "图形格式", "回答"])
    ws.append([
        "B1001",
        '[{"Q":"金花股份利润总额是多少"}]',
        "SELECT 31400000.0 AS total_profit",
        "无",
        '[{"Q":"x","A":{"content":"利润是 3140 万元。"}}]',
    ])
    ws.append([
        "B1002",
        '[{"Q":"xx"}]',
        "SELECT 31400000.0 AS total_profit",
        "无",
        '[{"Q":"x","A":{"content":"利润是 99 万元。"}}]',
    ])
    wb.save(path)


def test_cli_produces_report(tmp_path: Path):
    xlsx = tmp_path / "result_2.xlsx"
    db = tmp_path / "finance.db"
    report = tmp_path / "audit.md"
    _build_mini_xlsx(xlsx)
    # db path doesn't need to exist for SELECT on constant, but create an empty
    # one so run_sql_strict's sqlite3.connect succeeds.
    import sqlite3
    sqlite3.connect(db).close()

    rc = subprocess.run(
        [
            sys.executable,
            "scripts/audit_results.py",
            "--xlsx", str(xlsx),
            "--db", str(db),
            "--out", str(report),
            "--no-judge",
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
    ).returncode
    assert rc == 0
    body = report.read_text(encoding="utf-8")
    assert "阻塞" in body and "B1002" in body

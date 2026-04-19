from pathlib import Path

import pytest

from src.audit.checks import (
    Finding,
    check_chart_file,
    check_number_consistency,
)


def test_finding_defaults():
    f = Finding(row_id="B1001", severity="blocking", kind="num_mismatch", detail="x")
    assert f.severity in {"blocking", "suspect", "hint"}


def test_number_consistency_passes_when_all_numbers_present():
    sql_rows = [{"total_profit": 31_400_000.0}]
    content = "金花股份 2025 年第三季度的利润总额是 3140 万元。"
    findings = check_number_consistency("B1001", content=content, sql_rows=sql_rows)
    assert findings == []


def test_number_consistency_flags_mismatch_over_threshold():
    sql_rows = [{"total_profit": 31_400_000.0}]
    content = "利润总额是 500 万元。"
    findings = check_number_consistency("B1001", content=content, sql_rows=sql_rows)
    assert findings and findings[0].severity == "blocking"
    assert "500" in findings[0].detail


def test_number_consistency_tolerates_rounding():
    sql_rows = [{"total_profit": 31_400_000.0}]
    content = "利润总额约 3141 万元。"
    assert check_number_consistency("B1001", content=content, sql_rows=sql_rows) == []


def test_number_consistency_skips_when_no_sql():
    assert check_number_consistency("B2002", content="100 万元", sql_rows=[]) == []


def test_chart_file_missing(tmp_path: Path):
    findings = check_chart_file("B1002", path=tmp_path / "does_not_exist.jpg")
    assert findings and findings[0].severity == "blocking"


def test_chart_file_zero_bytes(tmp_path: Path):
    p = tmp_path / "empty.jpg"
    p.write_bytes(b"")
    findings = check_chart_file("B1002", path=p)
    assert findings and findings[0].severity == "blocking"


def test_chart_file_small_dimensions_flags_suspect(tmp_path: Path):
    p = tmp_path / "tiny.jpg"
    try:
        from PIL import Image
        Image.new("RGB", (10, 10), "white").save(p, "JPEG")
    except ImportError:
        pytest.skip("Pillow unavailable")
    findings = check_chart_file("B1002", path=p)
    assert any(f.severity == "suspect" for f in findings)

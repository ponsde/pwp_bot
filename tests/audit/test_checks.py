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


def test_number_consistency_accepts_pairwise_difference():
    # SQL returned two values, content cites their difference (growth amount)
    sql_rows = [{"a": 157478.76}, {"a": 146238.21}]   # 万元-scale
    content = "同比下降约 1.12 亿元。"                # 157478.76 - 146238.21 = 11240.55 万 = 1.124 亿
    findings = check_number_consistency("B1005", content=content, sql_rows=sql_rows)
    assert findings == []


def test_number_consistency_demotes_rough_match_to_suspect():
    # content off by ~12% from any direct or pairwise value → suspect, not blocking
    sql_rows = [{"a": 100.0}]
    content = "约 88 元。"   # 12% low → suspect
    findings = check_number_consistency("B9999", content=content, sql_rows=sql_rows)
    assert findings and all(f.severity == "suspect" for f in findings)


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

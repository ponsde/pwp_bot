"""Tests for the allowlist filter in ETLLoader.

Any PDF whose parsed stock_code is NOT in 附件1 must be skipped with
reason='not_in_allowlist_附件1', not loaded into the DB.
"""
from src.etl.schema import load_official_stock_codes


def test_official_stock_codes_is_nonempty_set_of_6digits():
    codes = load_official_stock_codes()
    assert isinstance(codes, set)
    assert len(codes) >= 60, "附件1 should list ~60+ 中药 companies"
    for c in codes:
        assert len(c) == 6 and c.isdigit(), f"non-6-digit code: {c!r}"


def test_unrelated_stock_codes_not_in_allowlist():
    codes = load_official_stock_codes()
    # 平安银行, 贵州茅台, 长药控股 — none of these are 中药 companies in 附件1
    assert "000001" not in codes
    assert "600519" not in codes
    assert "300391" not in codes

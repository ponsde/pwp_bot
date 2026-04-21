"""Unit tests for the magnitude-guarded aggregate-field overwrite helper."""
import pytest

from src.etl.table_extractor import _should_overwrite_aggregate as owr


def test_none_existing_accepts_new():
    assert owr(None, 100.0) is True


def test_none_existing_with_zero_new_accepts():
    assert owr(None, 0.0) is True


def test_none_new_rejected():
    assert owr(100.0, None) is False


def test_garbage_existing_overwritten_by_plausible_new():
    # 天士力 pattern: existing=19 (garbage) → new=1,643,027 万元 (real)
    assert owr(19.46, 1_643_027.0) is True


def test_plausible_existing_not_overwritten_by_garbage():
    # reverse: existing=1,643,027 → new=19 (garbage)
    assert owr(1_643_027.0, 19.46) is False


def test_consolidated_vs_parent_accepted():
    # 天士力 example: 合并 1,643,027 vs 母公司 1,423,938 → 87%, should overwrite
    assert owr(1_643_027.0, 1_423_938.0) is True


def test_quarter_value_rejected_vs_annual():
    # 佐力药业 pattern: annual 27,300 万元 vs Q1 quarterly 6,874 万元 → 25%, reject
    assert owr(27_300.0, 6_874.0) is False


def test_doubling_allowed_within_range():
    # 2x should still overwrite (inside [0.3, 3.0])
    assert owr(100_000.0, 200_000.0) is True


def test_5x_overwrite_rejected():
    # 5x is outside [0.3, 3.0], reject (e.g., forgot to divide by 10000)
    assert owr(100_000.0, 500_000.0) is False


def test_zero_existing_accepts_nonzero_new():
    assert owr(0.0, 100.0) is True


def test_zero_existing_with_zero_new_rejected():
    assert owr(0.0, 0.0) is False


def test_negative_values_by_magnitude():
    # net_profit can be negative; ratio logic operates on absolute values
    assert owr(-1000.0, -1500.0) is True       # 1.5x, within range
    assert owr(-1000.0, 10.0) is False          # new is garbage (< floor)
    assert owr(-10.0, -1500.0) is True          # existing is garbage, new escapes


# ── Asymmetric rule for consolidated-only fields ──────────────────────────────

def test_consolidated_field_rejects_shrinking_write():
    # 重药控股 2025HY pattern: liab existing 277,789 (合并 OK) → new 90,906 (母公司)
    # Without field hint: ratio 0.33 passes [0.3, 3.0] — BAD
    # With field='liability_total_liabilities': asymmetric [1.0, 3.0] rejects
    assert owr(277_789.0, 90_906.0) is True       # default rule allows
    assert owr(277_789.0, 90_906.0, field="liability_total_liabilities") is False


def test_consolidated_field_accepts_equal_or_larger():
    # 合并 on top of 母公司: 母公司 100 → 合并 200 (2x), should overwrite
    assert owr(100_000.0, 200_000.0, field="asset_total_assets") is True
    # exactly equal also accepted
    assert owr(100_000.0, 100_000.0, field="asset_total_assets") is True


def test_consolidated_field_still_escapes_garbage_floor():
    # existing is garbage regardless of field kind
    assert owr(19.46, 1_643_027.0, field="asset_total_assets") is True


def test_net_profit_rejects_shrinking_write():
    # 附件3 schema says income_sheet.net_profit = 合并净利润 (not 归母). When main
    # 利润表 writes 合并 first, a later 归母 row (smaller by 少数股东损益) must not
    # overwrite it. 白云山 2024Q3: 合并 328944 vs 归母 315897 (ratio 0.96) — the
    # symmetric [0.3, 3.0] rule would incorrectly allow this overwrite.
    # Consolidated-only [1.0, 3.0] rule rejects it, keeping 合并 correct.
    assert owr(10_000.0, 5_000.0, field="net_profit") is False  # 0.5x, reject
    assert owr(10_000.0, 9_600.0, field="net_profit") is False  # 0.96x (realistic 归母/合并)
    # But larger values (合并 overwriting earlier 母公司 write) should still pass
    assert owr(5_000.0, 10_000.0, field="net_profit") is True

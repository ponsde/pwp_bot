"""Tests for PDF filename parsing — new SZSE-format variants exposed by full dataset."""
from pathlib import Path

import pytest

from src.etl.pdf_parser import PDFParser, SZSE_RE


# --- regex-only tests ---------------------------------------------------------

def test_szse_regex_matches_update_suffix():
    m = SZSE_RE.search("佐力药业：2023年第三季度报告（更新后）.pdf")
    assert m is not None
    assert m.group("abbr") == "佐力药业"
    assert m.group("year") == "2023"
    assert m.group("period") == "第三季度报告"


def test_szse_regex_matches_correction_suffix():
    m = SZSE_RE.search("桂林三金：2024年第一季度报告（更正后）.pdf")
    assert m is not None
    assert m.group("period") == "第一季度报告"


def test_szse_regex_matches_plain_first_quarter():
    m = SZSE_RE.search("盘龙药业：2024年第一季度报告.pdf")
    assert m is not None
    assert m.group("period") == "第一季度报告"


def test_szse_regex_matches_plain_third_quarter():
    m = SZSE_RE.search("维康药业：2022年第三季度报告（更新后）.pdf")
    assert m is not None
    assert m.group("period") == "第三季度报告"


def test_szse_regex_matches_repeated_abbr_and_full_text():
    m = SZSE_RE.search("启迪药业：启迪药业2022年年度报告全文（更正后）.pdf")
    assert m is not None
    assert m.group("abbr") == "启迪药业"
    assert m.group("year") == "2022"
    assert m.group("period") == "年度报告全文"


# --- regression: original formats must still match ----------------------------

def test_szse_regex_regression_annual():
    m = SZSE_RE.search("云南白药：2024年年度报告.pdf")
    assert m is not None
    assert m.group("period") == "年度报告"


def test_szse_regex_regression_annual_summary():
    m = SZSE_RE.search("云南白药：2023年年度报告摘要.pdf")
    assert m is not None
    assert m.group("period") == "年度报告摘要"


def test_szse_regex_regression_half_year_summary():
    m = SZSE_RE.search("云南白药：2023年半年度报告摘要.pdf")
    assert m is not None
    assert m.group("period") == "半年度报告摘要"


# --- end-to-end meta parsing (abbrs in 附件1, so no PDF reads needed) ---------

@pytest.fixture(scope="module")
def parser() -> PDFParser:
    return PDFParser()


def test_parse_szse_meta_third_quarter_with_update_suffix(parser, tmp_path):
    fake = tmp_path / "佐力药业：2023年第三季度报告（更新后）.pdf"
    meta = parser._parse_szse_meta(fake)
    assert meta["stock_code"] == "300181"
    assert meta["report_period"] == "2023Q3"
    assert meta["is_summary"] is False


def test_parse_szse_meta_annual_full_text_normalizes_to_fy(parser, tmp_path):
    fake = tmp_path / "启迪药业：启迪药业2022年年度报告全文（更正后）.pdf"
    meta = parser._parse_szse_meta(fake)
    assert meta["stock_code"] == "000590"
    assert meta["report_period"] == "2022FY"
    assert meta["is_summary"] is False


def test_parse_szse_meta_summary_flagged(parser, tmp_path):
    fake = tmp_path / "云南白药：2023年半年度报告摘要.pdf"
    meta = parser._parse_szse_meta(fake)
    assert meta["is_summary"] is True
    assert meta["report_period"] == "2023HY"

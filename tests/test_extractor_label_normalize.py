"""Tests for label normalization — handles truncated brackets and prefix stripping."""
from src.etl.table_extractor import TableExtractor


def test_normalize_strips_full_bracket_note():
    assert TableExtractor._normalize_label("一、利润总额（亏损总额以-号填列）") == "利润总额"


def test_normalize_strips_unclosed_trailing_bracket():
    # pdfplumber truncation: "四、利润总额（亏损总额以"－"号" (bracket never closes)
    assert TableExtractor._normalize_label("四、利润总额（亏损总额以\"－\"号") == "利润总额"


def test_normalize_strips_prefix_variants():
    assert TableExtractor._normalize_label("1.营业收入") == "营业收入"
    assert TableExtractor._normalize_label("（一）持续经营净利润") == "持续经营净利润"
    assert TableExtractor._normalize_label("加：信用减值损失") == "信用减值损失"


def test_normalize_preserves_already_clean():
    assert TableExtractor._normalize_label("归属于母公司股东的净利润") == "归属于母公司股东的净利润"


def test_normalize_does_not_strip_bracket_in_middle():
    # "股东权益合计" should be preserved as-is; no brackets involved
    assert TableExtractor._normalize_label("股东权益合计") == "股东权益合计"

"""Tests for hardcoded stock-code fallback when a company is missing from 附件1."""
from src.etl.pdf_parser import PDFParser


def test_fallback_hits_known_out_of_list_abbr():
    assert PDFParser._fallback_stock_code("长药控股") == {
        "stock_code": "300391",
        "stock_abbr": "长药控股",
    }


def test_fallback_returns_none_for_unknown_abbr():
    assert PDFParser._fallback_stock_code("虚构药业") is None


def test_fallback_returns_none_for_empty_string():
    assert PDFParser._fallback_stock_code("") is None

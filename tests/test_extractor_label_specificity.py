"""Integration tests for label-specificity guard in the statement extractor.

Verifies that once a more-specific alias (e.g. "归属于母公司股东的净利润") has
written a field, a less-specific alias (e.g. bare "净利润") from a later table
cannot overwrite it.
"""
from src.etl.pdf_parser import ParsedTable
from src.etl.table_extractor import TableExtractor


def _make_table(rows: list[list[str]], page: int = 1) -> ParsedTable:
    return ParsedTable(
        page_number=page,
        raw_rows=rows,
        text="合并利润表\n项目 本期数 上期数",
        title="合并利润表",
        table_type="income_sheet",
    )


def test_specific_label_blocks_subsequent_generic_overwrite():
    extractor = TableExtractor()
    target: dict = {
        "serial_number": 1,
        "stock_code": "600080",
        "stock_abbr": "金花股份",
        "report_period": "2023FY",
        "report_year": 2023,
    }
    label_specificity: dict[str, int] = {}

    # Table 1: main 利润表 writes net_profit via the long, specific alias.
    # Use a value in 万元 so source_unit='万元' keeps it as-is.
    main = _make_table([
        ["项目", "本期数", "上期数"],
        ["归属于母公司股东的净利润", "-4289.06", "3345.95"],
    ])
    extractor._extract_statement_table(main, "income_sheet", target, "万元", [], label_specificity)
    assert target.get("net_profit") == -4289.06

    # Table 2: auxiliary table (misclassified as income_sheet) has bare "净利润" row
    # with a different value. The label "净利润" (3 chars) is less specific than
    # the previous write's "归属于母公司股东的净利润" (12 chars) → must be rejected.
    aux = _make_table([
        ["项目", "本期数", "上期数"],
        ["净利润", "4398.75", "0"],
    ], page=160)
    extractor._extract_statement_table(aux, "income_sheet", target, "万元", [], label_specificity)
    assert target.get("net_profit") == -4289.06, "specific-label write must not be overwritten by generic-label write"


def test_generic_label_is_overwritten_by_specific_label():
    extractor = TableExtractor()
    target: dict = {
        "serial_number": 1,
        "stock_code": "600080",
        "stock_abbr": "金花股份",
        "report_period": "2023FY",
        "report_year": 2023,
    }
    label_specificity: dict[str, int] = {}

    # Table 1: Some earlier table only has bare 净利润 → writes with low specificity.
    t1 = _make_table([
        ["项目", "本期数", "上期数"],
        ["净利润", "1000.00", "900.00"],
    ])
    extractor._extract_statement_table(t1, "income_sheet", target, "万元", [], label_specificity)
    assert target.get("net_profit") == 1000.0

    # Table 2: real 合并利润表 comes later with the specific label. Should overwrite.
    t2 = _make_table([
        ["项目", "本期数", "上期数"],
        ["归属于母公司股东的净利润", "1100.00", "950.00"],
    ], page=85)
    extractor._extract_statement_table(t2, "income_sheet", target, "万元", [], label_specificity)
    assert target.get("net_profit") == 1100.0, "specific-label write must overwrite generic-label write"


def test_consolidated_overwrites_parent_for_balance_assets():
    # 母公司 first (smaller), 合并 second (larger) → 合并 wins
    extractor = TableExtractor()
    target: dict = {
        "serial_number": 1,
        "stock_code": "000000",
        "stock_abbr": "测试",
        "report_period": "2023FY",
        "report_year": 2023,
    }
    label_specificity: dict[str, int] = {}

    parent = ParsedTable(
        page_number=1,
        raw_rows=[
            ["项目", "期末余额", "期初余额"],
            ["资产总计", "900000", "800000"],
        ],
        text="母公司资产负债表\n项目 期末余额 期初余额",
        title="母公司资产负债表",
        table_type="balance_sheet",
    )
    extractor._extract_statement_table(parent, "balance_sheet", target, "万元", [], label_specificity)
    assert target.get("asset_total_assets") == 900000.0

    # 合并 (larger) should overwrite
    consolidated = ParsedTable(
        page_number=2,
        raw_rows=[
            ["项目", "期末余额", "期初余额"],
            ["资产合计", "1000000", "900000"],
        ],
        text="合并资产负债表\n项目 期末余额 期初余额",
        title="合并资产负债表",
        table_type="balance_sheet",
    )
    extractor._extract_statement_table(consolidated, "balance_sheet", target, "万元", [], label_specificity)
    assert target.get("asset_total_assets") == 1000000.0


def test_parent_cannot_overwrite_consolidated_for_balance():
    # 合并 first (correct, larger), 母公司 second (smaller) → 母公司 rejected
    # This directly covers the 重药控股 2025HY regression where 母公司 value
    # 90,906 was clobbering the correct 合并 value 277,789.
    extractor = TableExtractor()
    target: dict = {
        "serial_number": 1,
        "stock_code": "000000",
        "stock_abbr": "测试",
        "report_period": "2023FY",
        "report_year": 2023,
    }
    label_specificity: dict[str, int] = {}

    consolidated = ParsedTable(
        page_number=1,
        raw_rows=[
            ["项目", "期末余额", "期初余额"],
            ["负债合计", "277789", "250000"],
        ],
        text="合并资产负债表\n项目 期末余额 期初余额",
        title="合并资产负债表",
        table_type="balance_sheet",
    )
    extractor._extract_statement_table(consolidated, "balance_sheet", target, "万元", [], label_specificity)
    assert target.get("liability_total_liabilities") == 277789.0

    # 母公司 负债合计 (smaller) must NOT overwrite
    parent = ParsedTable(
        page_number=2,
        raw_rows=[
            ["项目", "期末余额", "期初余额"],
            ["负债合计", "90906", "80000"],
        ],
        text="母公司资产负债表\n项目 期末余额 期初余额",
        title="母公司资产负债表",
        table_type="balance_sheet",
    )
    extractor._extract_statement_table(parent, "balance_sheet", target, "万元", [], label_specificity)
    assert target.get("liability_total_liabilities") == 277789.0, "smaller 母公司 value must not clobber larger 合并 value"

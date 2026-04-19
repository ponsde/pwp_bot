from src.audit.number_extractor import extract_numbers, NumToken


def test_extract_simple_cn_amount():
    text = "金花股份 2025 年第三季度的利润总额是 3140 万元。"
    toks = extract_numbers(text)
    vals = [t.value_in_yuan for t in toks]
    assert 31_400_000.0 in vals


def test_extract_yi_unit():
    toks = extract_numbers("营业收入 181.49 亿元")
    assert toks and abs(toks[0].value_in_yuan - 18_149_000_000.0) < 1.0


def test_extract_percent_is_kept_separately():
    toks = extract_numbers("同比增长 18.85%")
    assert any(t.unit == "%" and abs(t.value - 18.85) < 1e-6 for t in toks)


def test_extract_ignores_year_like_numbers():
    toks = extract_numbers("2024 年")
    assert all(t.unit for t in toks)


def test_extract_handles_comma_separated():
    toks = extract_numbers("资产总计 1,234,567.89 元")
    assert any(abs(t.value_in_yuan - 1234567.89) < 1e-6 for t in toks)

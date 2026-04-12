## Purpose

同比查询结果的自然语言格式化，包括百分比转换和字段语义恢复。

## Requirements

### Requirement: YoY results formatted as natural language
When result rows contain `current_value`, `previous_value`, and `yoy_ratio` columns, `build_answer_content` SHALL format each row as natural language instead of "field=value" format.

#### Scenario: Single company YoY result
- **WHEN** row is `{stock_abbr: "华润三九", report_period: "2024FY", current_value: 400000000, previous_value: 350000000, yoy_ratio: 0.1429}`
- **AND** intent fields include `net_profit`
- **THEN** output SHALL be: "华润三九：2024年净利润同比增长14.29%（本期40,000.00万元，上期35,000.00万元）"

#### Scenario: YoY ratio is None (division by zero)
- **WHEN** row has `yoy_ratio: None`
- **THEN** output SHALL be: "华润三九：2024年净利润无法计算同比（上期值为零），本期40,000.00万元"

#### Scenario: Negative YoY (decline)
- **WHEN** `yoy_ratio` is negative (e.g., -0.15)
- **THEN** output SHALL use "下降" instead of "增长": "净利润同比下降15.00%"

### Requirement: Superlative sub-question answer includes full data
When a sub-question contains "最大"/"最高"/"最低"/"最多"/"最少" and returns only 1 row, the answer SHALL include the company name AND the specific metric value, not just the company name.

#### Scenario: "Which company has highest YoY growth"
- **WHEN** sub-question asks "年同比上涨幅度最大的是哪家企业"
- **AND** result is `{stock_abbr: "金花股份", yoy_ratio: 2.716}`
- **THEN** answer SHALL be like "年同比上涨幅度最大的是金花股份，同比增长271.60%"
- **NOT** just "金花股份。"

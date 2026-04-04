## MODIFIED Requirements

### Requirement: Multi-row formatting displays human-readable identifiers
`build_answer_content` SHALL format identifier fields in a human-readable way when building multi-row summaries. Specifically, `report_period` values SHALL be converted using `_format_report_period` (e.g., `2022FY` → `2022年`, `2024HY` → `2024年半年度`).

#### Scenario: Multi-row result with report_period
- **WHEN** rows contain `report_period` field with value `2022FY`
- **THEN** output SHALL display `2022年` instead of `2022FY`

#### Scenario: Multi-row result with quarterly period
- **WHEN** rows contain `report_period` field with value `2024Q3`
- **THEN** output SHALL display `2024年第三季度`

### Requirement: Single-row single-column result does not echo question text
When `build_answer_content` receives a single row with a single column, the output SHALL contain only the field label and formatted value, NOT the question parameter text.

#### Scenario: Single value result for sub-question (non-YoY field)
- **WHEN** rows is `[{"total_profit": 50000.00}]`
- **AND** question is "在这些企业中利润最高的是哪家"
- **THEN** output SHALL be like `利润总额5.00亿元。`
- **NOT** `在这些企业中利润最高的是哪家：50000.00万元。`

#### Scenario: Single value result with YoY percentage field
- **WHEN** rows is `[{"net_profit_yoy_growth": 271.60}]`
- **AND** field label from schema contains "同比"
- **THEN** output SHALL be like `净利润同比增长271.60%`
- **NOT** `在这些企业中年同比上涨幅度最大的是哪家企业：271.60%`

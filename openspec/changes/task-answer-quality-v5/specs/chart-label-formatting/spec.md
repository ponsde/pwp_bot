## ADDED Requirements

### Requirement: Chart X-axis displays human-readable report_period
When chart data uses `report_period` as the label field, the displayed label SHALL be the human-readable format instead of the raw code.

#### Scenario: Line chart with report_period labels
- **WHEN** `safe_chart_data` processes rows where `label_field == "report_period"`
- **AND** a row has `report_period = "2022FY"`
- **THEN** the chart label SHALL display `2022年` instead of `2022FY`

#### Scenario: Bar chart with quarterly period
- **WHEN** chart label comes from `report_period = "2024Q3"`
- **THEN** the chart label SHALL display `2024年第三季度`

### Requirement: Chart data annotations include unit suffix
Line chart and bar chart data annotations SHALL include the unit suffix to match the Y-axis label.

#### Scenario: Line chart with values in 万元 scale
- **WHEN** `_detect_unit_scale` returns `unit_label = "万元"`
- **THEN** each data point annotation SHALL display like `4,790.10万元` instead of `4,790.10`

#### Scenario: Bar chart with values in 亿元 scale
- **WHEN** `_detect_unit_scale` returns `unit_label = "亿元"`
- **THEN** each bar annotation SHALL display like `45.94亿元`

#### Scenario: Pie chart is unaffected
- **WHEN** chart type is `pie`
- **THEN** annotations SHALL remain as percentage (`%1.1f%%`), unchanged

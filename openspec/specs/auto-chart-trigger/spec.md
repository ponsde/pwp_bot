## Purpose

Task3 研报路径的自动图表触发逻辑——基于 SQL 查询结果特征（多公司排名、同比对比）自动触发图表生成，不依赖用户显式"可视化"关键词。

## Requirements

### Requirement: Auto-trigger chart for Top N results
When SQL query returns multiple rows with `stock_abbr` column (indicating cross-company comparison), `_select_chart_type` SHALL return "bar" even without explicit visualization keywords.

#### Scenario: Top 10 query auto-generates bar chart
- **WHEN** question is "2024年利润最高的top10企业是哪些" (no "可视化" keyword)
- **AND** result contains multiple rows with `stock_abbr` column
- **THEN** chart_type SHALL be "bar" (not "无")

#### Scenario: Single company query does not auto-trigger
- **WHEN** question is "华润三九2024年净利润是多少"
- **AND** result contains 1 row
- **THEN** chart_type remains "无" (unless explicit visualization keyword present)

### Requirement: Auto-trigger chart for YoY comparison results
When SQL query returns rows containing `yoy_ratio` column, `_select_chart_type` SHALL return "bar".

#### Scenario: YoY multi-company comparison auto-generates chart
- **WHEN** result rows contain `yoy_ratio` column and multiple `stock_abbr` values
- **THEN** chart_type SHALL be "bar"

### Requirement: Chart trigger applies only in task3 research path
The auto-trigger logic SHALL only apply in `ResearchQAEngine._select_chart_type`, not in the task2 answer path, to avoid unwanted charts for simple data lookups.

#### Scenario: Task2 query does not auto-trigger
- **WHEN** task2 pipeline processes "金花股份利润总额是多少"
- **THEN** chart behavior unchanged (requires explicit keyword)

## ADDED Requirements

### Requirement: Heuristic intent recognizes YoY keywords
The system SHALL detect "同比"、"增长率"、"同比增长"、"同比下降"、"增减" in the question text and set `yoy: true` in the intent dict. Note: "环比" is excluded because this change only supports FY-to-FY comparison (self-join on report_year - 1), which is incompatible with quarter-over-quarter semantics. Standalone "增长"/"下降" without "同比" prefix are also excluded to avoid false positives on two-period comparison queries (e.g., "2024年比2023年增长多少").

#### Scenario: Question with 同比 keyword
- **WHEN** user asks "华润三九2024年净利润同比增长多少"
- **THEN** intent contains `yoy: true`, `periods: ["2024FY"]`, `fields: ["net_profit"]`

#### Scenario: Question without YoY keyword
- **WHEN** user asks "华润三九2024年净利润是多少"
- **THEN** intent contains `yoy: false` or `yoy: null`

### Requirement: Generate self-join SQL for YoY calculation
When `yoy: true`, `generate_sql` SHALL produce a self-join SQL that computes `(current - previous) / previous` as the YoY ratio.

#### Scenario: YoY SQL for single company annual profit
- **WHEN** intent is `{yoy: true, tables: ["income_sheet"], fields: ["net_profit"], companies: ["华润三九"], periods: ["2024FY"]}`
- **THEN** SQL SHALL join the table on `stock_abbr` with `b.report_period = '{year-1}FY'` (explicit period, not LIKE), selecting current value, previous value, and YoY ratio
- **THEN** SQL SHALL include `ROUND((a.net_profit - b.net_profit) * 1.0 / b.net_profit, 4) AS yoy_ratio` (explicit alias for downstream formatting)

#### Scenario: YoY SQL for multiple companies (from slot inheritance)
- **WHEN** intent is `{yoy: true, tables: ["income_sheet"], fields: ["net_profit"], companies: ["华润三九", "金花股份", ...], periods: ["2024FY"]}`
- **THEN** SQL SHALL use `WHERE a.stock_abbr IN ('华润三九', '金花股份', ...)` instead of single-company equality

#### Scenario: YoY with no previous year data
- **WHEN** self-join returns empty result (no previous year FY data exists)
- **THEN** system SHALL fallback to returning current year data only with a warning "上年同期数据不存在，无法计算同比"

### Requirement: YoY question missing period triggers clarification
When a YoY question does not contain a period and no period exists in conversation slots, the system SHALL request clarification rather than guessing.

#### Scenario: YoY question without period
- **WHEN** user asks "华润三九营业收入同比是多少" with no prior conversation context
- **THEN** system returns clarification asking for 报告期
- **NOTE**: This is handled by existing `missing_slots` logic — `yoy: true` does not exempt from period requirement

### Requirement: LLM post-fix injects YoY flag
After LLM returns intent, `analyze()` SHALL check if the question contains YoY keywords and inject `yoy: true` if the LLM did not set it.

#### Scenario: LLM omits yoy field
- **WHEN** question contains "同比" but LLM intent has no `yoy` key
- **THEN** `_fix_yoy_intent` sets `yoy: true`

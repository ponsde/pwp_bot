## MODIFIED Requirements

### Requirement: YoY fallback marks intent with yoy_fallback flag
When the YoY query cannot find prior-period data and falls back to single-period results, the returned intent SHALL include `yoy_fallback: True` so downstream formatters can adjust the answer semantics.

#### Scenario: YoY query falls back to single-period SQL
- **WHEN** `_query_with_recovery` detects `intent.yoy == True` and `current_rows` is empty
- **AND** `_build_single_period_sql` returns non-empty fallback rows
- **THEN** the returned `intent` dict SHALL include `"yoy_fallback": True`
- **AND** the warning SHALL remain `"上年同期数据不存在，无法计算同比"`

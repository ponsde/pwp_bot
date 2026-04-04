## MODIFIED Requirements

### Requirement: Intent extraction schema
The intent dict SHALL include the following additional fields beyond the existing schema:
- `yoy`: boolean — whether YoY calculation is needed
- `top_n`: integer or null — number of top results to return
- `order_direction`: "ASC" or "DESC" or null — sort direction for top N

#### Scenario: Full intent with all new fields
- **WHEN** user asks "2024年净利润同比增长最高的top5企业"
- **THEN** intent SHALL contain `{yoy: true, top_n: 5, order_direction: "DESC", fields: ["net_profit"], periods: ["2024FY"]}`

### Requirement: seek_table.md prompt includes new fields
The prompt template SHALL document `yoy`, `top_n`, and `order_direction` fields with descriptions and few-shot examples.

#### Scenario: LLM returns new fields natively
- **WHEN** question contains "同比" and prompt includes yoy field documentation
- **THEN** LLM MAY return `yoy: true` directly without post-fix correction

#### Scenario: Few-shot example for YoY
- **WHEN** seek_table.md is loaded
- **THEN** it SHALL contain at least one few-shot example with `yoy: true`

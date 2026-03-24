## ADDED Requirements

### Requirement: Format answers per 附件7 specification
The system SHALL produce answers in the JSON structure required by the competition: [{Q, A: {content, image}}] for task 2. The system SHALL save results to result_2.xlsx with columns: 编号, 问题, SQL查询语句, 图形格式, 回答.

#### Scenario: Single-turn answer
- **WHEN** answering question B1002 with a chart
- **THEN** output JSON includes content text + image paths
- **AND** the row in result_2.xlsx has the SQL, chart type, and JSON answer

#### Scenario: Multi-turn answer
- **WHEN** answering B1001 (2 turns: clarification then answer)
- **THEN** JSON array has 2 entries, first with clarification content, second with actual answer

### Requirement: Number formatting
The system SHALL format large numbers with appropriate Chinese units (万元/亿元) in the answer content.

#### Scenario: Format revenue
- **WHEN** raw value is 1476936.05 (万元)
- **THEN** display as "约147.69亿元" or "1,476,936.05万元"

## ADDED Requirements

### Requirement: Multi-turn dialogue with context
The system SHALL maintain conversation history and resolve follow-up questions using prior context. Questions come as arrays: [{"Q": "first"}, {"Q": "follow-up"}].

#### Scenario: Follow-up question
- **WHEN** first question is "金花股份利润总额是多少" and follow-up is "2025年第三季度的"
- **THEN** the system combines context to understand "金花股份2025Q3利润总额"

### Requirement: Intent clarification
The system SHALL detect when a query is missing critical information (company name, period, metric) and ask the user to clarify instead of guessing.

#### Scenario: Missing period
- **WHEN** user asks "金花股份利润总额是多少" without specifying period
- **THEN** the system responds "请问你查询哪一个报告期的利润总额？"

## ADDED Requirements

### Requirement: Forward query results between sub-questions
In `_answer_sql`, after each sub-question completes, the system SHALL extract result metadata (company names, field values) and inject them into the ConversationManager slots for subsequent sub-questions.

#### Scenario: Top N result feeds into follow-up question
- **WHEN** first sub-question "2024年利润最高的top10企业是哪些" returns rows with stock_abbr values
- **THEN** the company list from results is stored in `conversation.slots["companies"]` **before** the next sub-question's `analyze()` call
- **THEN** second sub-question "这些企业的利润同比是多少" calls `analyze()` → `_heuristic_intent` returns `companies: []` → `merge_intent` inherits companies from slots
- **NOTE**: This works because `merge_intent` already falls back to slot values when intent has empty list for a key. The injection point is between sub-question iterations in `_answer_sql`, not inside text2sql.

#### Scenario: No results to forward
- **WHEN** first sub-question returns empty results or an error
- **THEN** slots are NOT modified, subsequent sub-questions proceed independently

### Requirement: Anaphora detection for context inheritance
The system SHALL detect anaphoric references ("这些"、"上述"、"其"、"它们") in sub-questions and use forwarded slot data for resolution.

#### Scenario: Sub-question with anaphoric reference
- **WHEN** sub-question starts with "这些企业" and slots contain companies from previous result
- **THEN** the sub-question's intent uses the companies from slots instead of requiring clarification

#### Scenario: Sub-question without anaphoric reference
- **WHEN** sub-question explicitly names a company like "华润三九"
- **THEN** explicit company name takes precedence over slot data

## MODIFIED Requirements

### Requirement: Multi-sub-question answers do not contain duplicate paragraphs
When `_answer_sql` joins answer parts from multiple sub-questions, the final answer SHALL NOT contain duplicate lines.

#### Scenario: Two sub-questions return overlapping data
- **WHEN** sub-question 1 returns `金花股份：利润总额=4,203.93万元`
- **AND** sub-question 2 also produces `金花股份：利润总额=4,203.93万元` as part of its answer
- **THEN** the joined answer SHALL contain this line only once

#### Scenario: Non-duplicate lines are preserved
- **WHEN** two sub-questions produce different answer lines
- **THEN** all unique lines SHALL be preserved in order of first appearance

### Requirement: YoY fallback answer includes "无法计算同比" semantics
When the YoY query falls back to single-period data (because prior-period data is missing), the answer text SHALL explicitly indicate that year-over-year comparison could not be computed, rather than presenting plain metric values as if answering a non-YoY question.

#### Scenario: YoY query with missing prior-period data
- **WHEN** `intent.yoy == True` and `intent.yoy_fallback == True`
- **AND** rows contain plain metric values (not `current_value/previous_value/yoy_ratio`)
- **THEN** the answer SHALL append a note like `（无法计算同比，仅显示本期值）`
- **AND** the main answer content SHALL still display the metric values normally

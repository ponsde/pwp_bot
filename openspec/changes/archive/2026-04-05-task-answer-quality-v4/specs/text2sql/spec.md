## MODIFIED Requirements

### Requirement: Validation and reflection warnings are not shown to users
The `warning` field in `QueryResult` (produced by validation layer 2 and reflection layer 3) SHALL NOT be appended to user-visible answer content by default. Warnings SHALL be used for internal logging, except for explicitly whitelisted factual YoY warnings.

#### Scenario: Validation layer produces a warning with non-empty rows
- **WHEN** `_validate_result` returns `accepted=False` with a reason string
- **AND** query rows are non-empty (data was found)
- **THEN** `QueryResult.warning` SHALL contain the reason (for logging)
- **BUT** `pipeline.py` and `research_qa.py` SHALL NOT append warning to user answer content

#### Scenario: Reflection layer produces a warning
- **WHEN** `_reflect_task` returns `accepted=False` with a reason string
- **AND** query rows are non-empty
- **THEN** `QueryResult.warning` SHALL contain the reason (for logging)
- **BUT** the warning text SHALL NOT appear in the final answer shown to users

#### Scenario: YoY zero-division warning is shown to users
- **WHEN** `warning` is `上年同期值为零，无法计算同比增长率`
- **THEN** this specific warning MAY be shown to users

#### Scenario: YoY missing-prior-period warning is shown to users
- **WHEN** `warning` is `上年同期数据不存在，无法计算同比`
- **THEN** this specific warning MAY be shown to users

#### Scenario: Non-whitelisted warning that starts with similar text is hidden
- **WHEN** `warning` starts with `上年同期` but is not one of the explicitly whitelisted factual warning messages
- **THEN** it SHALL still be hidden from user-visible answer content

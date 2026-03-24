## ADDED Requirements

### Requirement: Generate visualization charts
The system SHALL generate charts from SQL query results using matplotlib. Chart type SHALL be selected based on the query type (trend→line, comparison→bar, proportion→pie). Charts SHALL be saved as images in result/ directory with naming convention {question_id}_{sequence}.jpg.

#### Scenario: Trend chart
- **WHEN** query results contain multiple periods for one metric
- **THEN** generate a line chart with period on x-axis, value on y-axis

#### Scenario: Comparison chart
- **WHEN** query results compare multiple companies on one metric
- **THEN** generate a bar chart

#### Scenario: Chart naming
- **WHEN** generating chart for question B1002
- **THEN** save as ./result/B1002_1.jpg

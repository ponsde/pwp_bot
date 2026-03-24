## ADDED Requirements

### Requirement: Load validated data into SQLite
The system SHALL insert validated records into the corresponding SQLite tables. The system SHALL use INSERT OR REPLACE keyed on (stock_code, report_period) to handle re-runs.

#### Scenario: Successful load
- **WHEN** loading validated data for 华润三九 2023FY
- **THEN** records appear in all 4 tables with correct values

#### Scenario: Idempotent reload
- **WHEN** loading the same company-period data twice
- **THEN** no duplicate rows are created

### Requirement: Load company info from 附件1
The system SHALL read 附件1 xlsx to populate stock_code ↔ stock_abbr mapping for use in the pipeline.

#### Scenario: Company lookup
- **WHEN** looking up stock_code 600080
- **THEN** returns stock_abbr "金花股份"

## ADDED Requirements

### Requirement: Create official schema tables
The system SHALL create 4 SQLite tables matching the official schema from 附件3: core_performance_indicators_sheet, balance_sheet, income_sheet, cash_flow_sheet. All field names, types, and descriptions SHALL match exactly.

#### Scenario: Fresh database creation
- **WHEN** running schema creation
- **THEN** all 4 tables are created with fields matching 附件3
- **AND** each table has stock_code, stock_abbr, report_period (varchar), report_year (int)

#### Scenario: report_period format
- **WHEN** inserting a record
- **THEN** report_period follows the format "{year}{period}" e.g. "2025Q3", "2022FY", "2024HY"

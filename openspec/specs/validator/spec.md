## ADDED Requirements

### Requirement: Accounting identity validation
The system SHALL validate financial accounting identities before loading data.

#### Scenario: Balance sheet identity
- **WHEN** total_assets, total_liabilities, and total_equity are all present
- **THEN** the system checks that total_assets ≈ total_liabilities + total_equity (within 1% tolerance)

#### Scenario: Income statement consistency
- **WHEN** operating_profit and its components are present
- **THEN** the system checks that operating_profit ≈ total_operating_revenue - total_operating_expenses

### Requirement: Cross-table consistency
The system SHALL validate consistency across tables for the same company and period.

#### Scenario: Net profit consistency
- **WHEN** the same company-period has net_profit in both income_sheet and core_performance_indicators_sheet
- **THEN** the values SHALL match (within rounding tolerance)

### Requirement: Format validation
The system SHALL validate data format before loading.

#### Scenario: report_period format check
- **WHEN** a record has report_period
- **THEN** it matches pattern "{4-digit year}{FY|Q1|HY|Q3}"

#### Scenario: Non-negative total assets
- **WHEN** total_assets is present
- **THEN** it SHALL be non-negative

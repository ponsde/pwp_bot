## ADDED Requirements

### Requirement: Two-step NL2SQL with fixed schema
The system SHALL convert natural language questions to SQL using: Step 1 - LLM extracts intent (tables, fields, companies, periods) as JSON; Step 2 - LLM generates SQL given full schema + Step 1 results. The full schema (4 tables) SHALL be included in the prompt.

#### Scenario: Simple query
- **WHEN** the user asks "金花股份2025年第三季度利润总额是多少"
- **THEN** Step 1 extracts {tables: ["income_sheet"], fields: ["total_profit"], companies: ["金花股份"], periods: ["2025Q3"]}
- **AND** Step 2 generates: SELECT total_profit FROM income_sheet WHERE stock_abbr='金花股份' AND report_period='2025Q3'

#### Scenario: Trend query
- **WHEN** the user asks "金花股份近几年的利润总额变化趋势"
- **THEN** the SQL queries multiple periods with ORDER BY report_period

### Requirement: SQL execution with retry
The system SHALL execute SQL against SQLite. On failure, feed error to LLM for correction, up to 2 retries.

#### Scenario: Successful execution
- **WHEN** SQL is valid
- **THEN** return query results as a DataFrame

#### Scenario: Retry on error
- **WHEN** SQL has a syntax error
- **THEN** send error message to LLM, get corrected SQL, retry

### Requirement: User-friendly failure handling
The system SHALL return clear messages when: company not found, field not recognized, period missing, or SQL returns empty results.

#### Scenario: Company not found
- **WHEN** user asks about a company not in the database
- **THEN** return a message listing available companies

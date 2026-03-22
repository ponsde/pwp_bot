## ADDED Requirements

### Requirement: Seek database prompt template
The system SHALL provide a prompt template for Step 1 (intent extraction) that instructs the LLM to output a JSON object with fields: companies (list of company names), accounts (list of financial metric names), years (list of integers).

#### Scenario: Prompt produces valid JSON
- **WHEN** the seek_database prompt is used with question "茅台2023年营收"
- **THEN** the LLM returns parseable JSON with companies, accounts, and years fields

### Requirement: Generate SQL prompt template
The system SHALL provide a prompt template for Step 2 (SQL generation) that includes: the user question, the database schema description, the Step 1 mapping results (resolved stock codes and item names), and sample data rows.

#### Scenario: Prompt includes schema context
- **WHEN** the generate_sql prompt is rendered
- **THEN** it contains the full SQLite table definitions, resolved column mappings, and at least one example data row

### Requirement: Answer generation prompt template
The system SHALL provide a prompt template for generating natural language answers from SQL results. The prompt SHALL instruct the LLM to cite the exact values and include appropriate units (元/万元/亿元).

#### Scenario: Answer prompt with SQL results
- **WHEN** the answer prompt is rendered with SQL results
- **THEN** it includes the original question, the SQL query, and the result data for the LLM to compose an answer

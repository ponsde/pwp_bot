## ADDED Requirements

### Requirement: Prompt template loading and rendering
The system SHALL provide a utility function that loads a prompt template from `src/prompts/` by name (without extension) and renders it by substituting `{variable_name}` placeholders with provided values. Templates are Markdown files with `{...}` placeholders.

#### Scenario: Load and render template
- **WHEN** calling `load_prompt("seek_database", question="茅台2023年营收")`
- **THEN** the system reads `src/prompts/seek_database.md` and returns the content with `{question}` replaced by the actual question

#### Scenario: Missing template
- **WHEN** loading a template name that does not exist
- **THEN** the system raises a FileNotFoundError with the expected path

### Requirement: Seek database prompt template
The system SHALL provide a prompt template for Step 1 (intent extraction) that instructs the LLM to output a JSON object with fields: companies (list of company names), accounts (list of financial metric names), years (list of integers). The template SHALL include examples of expected JSON output.

#### Scenario: Prompt produces valid JSON
- **WHEN** the seek_database prompt is used with question "茅台2023年营收"
- **THEN** the LLM returns parseable JSON with companies, accounts, and years fields

### Requirement: Generate SQL prompt template
The system SHALL provide a prompt template for Step 2 (SQL generation) that includes placeholders for: the user question, the SQLite table definitions (companies, financial_data, item_mapping), the Step 1 mapping results (resolved stock codes and item names), and sample data rows. The template SHALL instruct the LLM to output a single SQL query wrapped in ```sql``` code fences.

#### Scenario: Prompt includes schema context
- **WHEN** the generate_sql prompt is rendered with mapping results
- **THEN** it contains the full SQLite CREATE TABLE statements, resolved column mappings, and at least one example data row

### Requirement: Answer generation prompt template
The system SHALL provide a prompt template for generating natural language answers from SQL results. The prompt SHALL instruct the LLM to cite the exact values and format large numbers with appropriate units (万元/亿元).

#### Scenario: Answer prompt with SQL results
- **WHEN** the answer prompt is rendered with SQL results
- **THEN** it includes the original question, the SQL query, and the result data for the LLM to compose an answer

## ADDED Requirements

### Requirement: Two-step Text2SQL query engine
The system SHALL convert natural language questions into SQL queries using a two-step process: Step 1 extracts intent (company names, financial metrics, years) via LLM; Step 2 generates SQL using the extracted intent plus table schema snapshot.

#### Scenario: Simple numeric query
- **WHEN** the user asks "贵州茅台2023年营业收入是多少？"
- **THEN** Step 1 extracts {companies: ["贵州茅台"], accounts: ["营业收入"], years: [2023]}
- **AND** Step 2 generates valid SQL that returns the correct value

#### Scenario: Comparison query
- **WHEN** the user asks "比亚迪2023年净利润比2022年增长了多少？"
- **THEN** Step 1 extracts {companies: ["比亚迪"], accounts: ["净利润"], years: [2022, 2023]}
- **AND** Step 2 generates SQL that retrieves both years' values

### Requirement: Intent extraction with alias resolution
Step 1 SHALL resolve user-mentioned metric names to canonical item_names using the item_mapping table. The system SHALL handle common aliases (e.g., "营收" → "营业收入", "净利" → "净利润").

#### Scenario: Alias resolution
- **WHEN** the user says "营收" in their question
- **THEN** the system maps it to the canonical item_name "营业收入"

#### Scenario: Company name resolution
- **WHEN** the user says "茅台" (short name)
- **THEN** the system resolves it to stock_code "600519" via the companies table

### Requirement: SQL execution with retry
The system SHALL execute the generated SQL against SQLite. If execution fails (syntax error, no results), the system SHALL feed the error message back to the LLM to regenerate SQL, up to 2 retries.

#### Scenario: SQL succeeds on first try
- **WHEN** the generated SQL is valid and returns results
- **THEN** the system returns the query results directly

#### Scenario: SQL fails then succeeds on retry
- **WHEN** the first SQL has a syntax error
- **THEN** the system sends the error to the LLM, gets a corrected SQL, and executes it successfully

#### Scenario: All retries exhausted
- **WHEN** SQL fails after 2 retries
- **THEN** the system returns a user-friendly error message explaining it could not find the answer

### Requirement: Answer generation from SQL results
The system SHALL use the LLM to generate a natural language answer from the SQL query results. The answer SHALL include the actual numeric values and appropriate units.

#### Scenario: Numeric answer generation
- **WHEN** SQL returns value=150560000000 for 营业收入
- **THEN** the LLM generates an answer like "贵州茅台2023年营业收入为1505.60亿元"

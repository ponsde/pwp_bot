## ADDED Requirements

### Requirement: Fetch financial statements via AKShare
The system SHALL fetch three types of financial statements (balance sheet, income statement, cash flow statement) for any given stock code using `akshare.stock_financial_report_sina(stock, symbol)`. Each call returns a DataFrame with ~100 rows (one per report period, e.g. "20231231") and 70-150 columns (Chinese metric names). The system SHALL store raw DataFrames locally as CSV cache files (one CSV per stock code per statement type).

#### Scenario: Fetch single company
- **WHEN** fetching financial data for stock code "600519" (Guizhou Moutai)
- **THEN** the system retrieves three DataFrames (利润表: ~83 columns, 资产负债表: ~147 columns, 现金流量表: ~71 columns)
- **AND** each DataFrame has a `报告日` column with values like "20231231"
- **AND** all other columns are Chinese metric names (e.g. "营业收入", "净利润")
- **AND** the raw DataFrame includes metadata columns such as `报告日`, `公告日期`, `类型`, and `币种`

#### Scenario: Batch fetch with progress
- **WHEN** fetching data for 100 stock codes
- **THEN** the system shows progress, handles individual failures gracefully, and continues with remaining companies
- **AND** the system applies rate limiting (sleep between requests) to avoid AKShare/Sina API throttling

#### Scenario: Cached data reuse
- **WHEN** fetching data for a company that was previously fetched
- **THEN** the system uses the cached CSV file instead of re-fetching

#### Scenario: Rate limit handling
- **WHEN** AKShare returns a connection error or rate limit response
- **THEN** the system pauses with exponential backoff and retries automatically

### Requirement: SQLite schema with vertical table design
The system SHALL create a SQLite database with three tables:
- `companies` (stock_code TEXT PK, company_name TEXT) — no industry column in Phase 1 as `stock_info_a_code_name` only returns code and name
- `financial_data` (id INTEGER PK, stock_code TEXT FK, report_date TEXT, statement_type TEXT, item_name TEXT, value REAL) — `report_date` is a string like "20231231" preserving the original AKShare format; `statement_type` is one of "利润表"/"资产负债表"/"现金流量表"
- `item_mapping` (item_name TEXT, alias TEXT, statement_type TEXT, PK(item_name, alias)) — each row maps one alias to one canonical item_name

The system SHALL create a UNIQUE constraint on (stock_code, report_date, statement_type, item_name) for idempotent loading, and indexes on (stock_code, report_date, statement_type) and (item_name) for query performance.

#### Scenario: Database initialization
- **WHEN** running schema creation on a fresh database
- **THEN** all three tables are created with correct column types, foreign keys, indexes, and uniqueness constraints

#### Scenario: Vertical table structure
- **WHEN** inserting Moutai's 2023 annual revenue
- **THEN** a single row is inserted with stock_code="600519", report_date="20231231", statement_type="利润表", item_name="营业收入", value=147693604994.14

### Requirement: Load DataFrames into SQLite
The system SHALL transform AKShare DataFrames (one row per report period, many columns per metric) into the vertical table format (one row per metric per report period). For each row in the DataFrame: iterate over all metric columns (excluding metadata columns), skip NaN values, and insert (stock_code, report_date, statement_type, item_name, value) into `financial_data`. Metadata columns (`报告日`, `公告日期`, `币种`, `类型`, `数据源`, `更新日期`) SHALL NOT be inserted as `item_name`. The system SHALL use INSERT OR IGNORE for idempotent loading.

#### Scenario: Transform and load
- **WHEN** loading Moutai's income statement DataFrame (100 rows x 83 columns)
- **THEN** each non-NaN metric cell becomes a separate row in financial_data
- **AND** metadata columns like `报告日`, `公告日期`, `类型`, `币种`, `数据源`, `更新日期` are not inserted as `item_name`
- **AND** only annual report rows (report_date ending in "1231") are loaded if annual-only mode is selected

#### Scenario: Idempotent loading
- **WHEN** loading the same company-year data twice
- **THEN** no duplicate rows are created (INSERT OR IGNORE on UNIQUE constraint)

### Requirement: Fetch A-share stock list
The system SHALL retrieve the list of A-share listed companies using `akshare.stock_info_a_code_name()` which returns a DataFrame with columns `code` and `name`. The system SHALL populate the `companies` table with stock_code and company_name.

#### Scenario: Stock list retrieval
- **WHEN** fetching the stock list
- **THEN** the companies table contains ~5000 entries with stock_code and company_name

#### Scenario: Partial fetch for Phase 1
- **WHEN** running in Phase 1 mode with a target list of 50-100 stock codes
- **THEN** the system only fetches financial data for the specified subset, not all 5000 companies

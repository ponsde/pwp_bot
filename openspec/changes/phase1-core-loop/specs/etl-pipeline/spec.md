## ADDED Requirements

### Requirement: Fetch financial statements via AKShare
The system SHALL fetch three types of financial statements (balance sheet, income statement, cash flow statement) for any given stock code and store the raw data locally as CSV cache. The system SHALL support batch fetching for multiple stock codes.

#### Scenario: Fetch single company
- **WHEN** fetching financial data for stock code "600519" (Guizhou Moutai)
- **THEN** the system retrieves balance sheet, income statement, and cash flow data with Chinese column names
- **AND** the raw DataFrame includes metadata columns such as `报告日`, `公告日期`, `类型`, and `币种`

#### Scenario: Batch fetch with progress
- **WHEN** fetching data for 100 stock codes
- **THEN** the system shows progress, handles individual failures gracefully, and continues with remaining companies

#### Scenario: Cached data reuse
- **WHEN** fetching data for a company that was previously fetched
- **THEN** the system uses the cached CSV file instead of re-fetching

### Requirement: SQLite schema with vertical table design
The system SHALL create a SQLite database with three tables: `companies` (stock_code, company_name, industry), `financial_data` (stock_code, report_date, year, report_type, statement_type, item_name, value, unit, announcement_date), and `item_mapping` (item_name, alias, statement_type). The schema SHALL preserve AKShare metadata required for filtering and answering while storing financial metrics in vertical form.

#### Scenario: Database initialization
- **WHEN** running schema creation on a fresh database
- **THEN** all three tables are created with correct column types and foreign keys
- **AND** `financial_data` has a uniqueness constraint preventing duplicate metric rows for the same stock/report/statement/item combination

#### Scenario: Vertical table structure
- **WHEN** inserting Moutai's 2023 revenue
- **THEN** a single row is inserted with item_name="营业收入", value=150560000000, statement_type="income"

### Requirement: Load DataFrames into SQLite
The system SHALL load cleaned pandas DataFrames into the SQLite vertical table, transforming horizontal column layout (one column per metric) into vertical rows (one row per metric). The system SHALL handle duplicate detection and skip already-loaded data.

#### Scenario: Transform and load
- **WHEN** loading an AKShare income statement DataFrame with columns like "营业收入", "营业成本"
- **THEN** each metric column becomes a separate row in financial_data with the column name as item_name
- **AND** metadata columns like `报告日`, `公告日期`, `类型`, `币种`, `数据源`, `更新日期` are not inserted as `item_name`

#### Scenario: Idempotent loading
- **WHEN** loading the same company-year data twice
- **THEN** no duplicate rows are created

### Requirement: Fetch A-share stock list
The system SHALL retrieve the full list of A-share listed companies (stock code, company_name, industry) and populate the `companies` table.

#### Scenario: Stock list retrieval
- **WHEN** fetching the stock list
- **THEN** the companies table contains ~5000 entries with stock_code, company_name, and industry

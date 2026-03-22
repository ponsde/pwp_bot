## ADDED Requirements

### Requirement: Extract tables from financial report PDFs
The system SHALL use pdfplumber to extract tabular data from financial report PDFs. The system SHALL handle both formats: 深交所 (Chinese filename with company name and report period) and 上交所 (stock_code_date_random.pdf).

#### Scenario: Parse 深交所 annual report
- **WHEN** parsing "华润三九：2023年年度报告.pdf"
- **THEN** the system extracts balance sheet, income statement, cash flow statement, and core performance indicator tables
- **AND** returns structured data with Chinese column headers and numeric values

#### Scenario: Parse 上交所 report
- **WHEN** parsing "600080_20230428_FQ2V.pdf"
- **THEN** the system identifies the stock_code as "600080" and infers the report period from the publish date or PDF title page

#### Scenario: Handle merged cells and multi-page tables
- **WHEN** a table spans multiple pages or has merged header cells
- **THEN** the system reconstructs the complete table with correct column alignment

### Requirement: Identify report metadata
The system SHALL extract report metadata: stock_code, stock_abbr (company short name), report_period (e.g. "2023FY", "2025Q3"), report_year from either the filename or PDF content.

#### Scenario: 深交所 filename parsing
- **WHEN** the filename is "华润三九：2023年年度报告.pdf"
- **THEN** metadata is {stock_abbr: "华润三九", report_period: "2023FY", report_year: 2023}

#### Scenario: 上交所 date-based inference
- **WHEN** the filename is "600080_20230428_FQ2V.pdf" (April publish date)
- **THEN** metadata infers report_period as "2022FY" (annual report published in April)

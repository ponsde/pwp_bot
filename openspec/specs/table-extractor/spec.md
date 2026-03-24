## ADDED Requirements

### Requirement: Map PDF table columns to official schema fields
The system SHALL map Chinese financial metric names from PDF tables to the official schema English field names defined in 附件3. The system SHALL maintain a mapping dictionary covering common aliases.

#### Scenario: Direct mapping
- **WHEN** PDF table has column "营业总收入"
- **THEN** it maps to field `total_operating_revenue` in income_sheet

#### Scenario: Alias mapping
- **WHEN** PDF table has "一、营业收入" or "营业收入(元)"
- **THEN** it maps to the same field `total_operating_revenue`

#### Scenario: LLM fallback for unknown columns
- **WHEN** a PDF column name doesn't match any entry in the mapping dictionary
- **THEN** the system uses LLM to suggest the best matching official field name

### Requirement: Unit conversion
The system SHALL convert values to the unit specified by the official schema. PDF values are typically in 元 (yuan); the schema requires 万元 (10,000 yuan) for most fields and 元 for per-share metrics.

#### Scenario: Yuan to 万元 conversion
- **WHEN** PDF shows "营业总收入: 1,505,600,000.00" (元)
- **THEN** the stored value is 150560.00 (万元)

#### Scenario: Per-share metrics stay in 元
- **WHEN** PDF shows "基本每股收益: 2.35"
- **THEN** eps is stored as 2.35 (元, no conversion)

### Requirement: Identify which official table a PDF table belongs to
The system SHALL determine whether a PDF table is a balance sheet, income statement, cash flow statement, or core performance summary based on its title and content.

#### Scenario: Table identification
- **WHEN** a PDF table title contains "合并资产负债表"
- **THEN** it is classified as balance_sheet

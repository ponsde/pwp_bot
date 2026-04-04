## ADDED Requirements

### Requirement: Automated ETL pipeline
The system SHALL provide a CLI command `python pipeline.py --task etl --input <dir>` that automatically: discovers PDF files → parses tables → maps fields → validates → loads into SQLite.

#### Scenario: Full ETL run
- **WHEN** running `python pipeline.py --task etl --input data/sample/示例数据/附件2：财务报告/`
- **THEN** all PDFs are processed and data appears in 4 SQLite tables

#### Scenario: Answer questions pipeline
- **WHEN** running `python pipeline.py --task answer --questions <xlsx>`
- **THEN** processes all questions and outputs result_2.xlsx + chart images

### Requirement: Error reporting
The system SHALL log warnings for PDFs that fail parsing or validation but continue processing remaining files.

#### Scenario: Partial failure
- **WHEN** one PDF out of 39 fails parsing
- **THEN** the remaining 38 are processed successfully and the failure is logged

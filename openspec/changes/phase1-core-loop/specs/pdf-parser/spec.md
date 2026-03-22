## ADDED Requirements

### Requirement: Extract full text from PDF
The system SHALL extract all text content from a PDF file page by page using pdfplumber. The system SHALL preserve page boundaries in the output.

#### Scenario: Parse a standard annual report PDF
- **WHEN** parsing a 143-page Moutai annual report PDF
- **THEN** the system returns a list of text strings, one per page, with readable content

#### Scenario: Handle empty or image-only pages
- **WHEN** a page contains no extractable text
- **THEN** the system returns an empty string for that page without errors

### Requirement: Batch PDF processing
The system SHALL support processing a directory of PDF files. The output SHALL be structured as one text file per PDF (or one JSON with metadata).

#### Scenario: Process directory of PDFs
- **WHEN** pointing the parser at `data/raw/` containing 3 PDF files
- **THEN** the system produces 3 corresponding text outputs in `data/processed/`

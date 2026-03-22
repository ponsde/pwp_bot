## ADDED Requirements

### Requirement: OpenViking initialization
The system SHALL initialize an OpenViking client in embedded mode using `ov.OpenViking(path=<data_path>)` with a configured `ov.conf` file. The `ov.conf` SHALL configure the embedding model (BAAI/bge-m3 via OpenAI-compatible endpoint) with correct `provider`, `model`, `api_base`, `api_key`, and `dimension` (1024) fields.

#### Scenario: Successful initialization
- **WHEN** calling `client = ov.OpenViking(path="./data/ov")` and `client.initialize()`
- **THEN** the client is ready to accept resources and perform searches

### Requirement: Import annual report PDF as OV Resource
The system SHALL import PDF files directly into OpenViking using `client.add_resource(path=<pdf_path>, reason=<description>)`. OV has a built-in PDF parser, so no pre-processing with pdfplumber is required for this path. Each annual report SHALL be a separate resource. The system SHALL call `client.wait_processed()` after import to ensure indexing completes.

#### Scenario: Import single PDF report
- **WHEN** importing `data/raw/600519_2023.pdf` via `client.add_resource(path="data/raw/600519_2023.pdf", reason="贵州茅台2023年度报告")`
- **THEN** OV creates a resource and processes it (L0/L1/L2 indexing)
- **AND** the resource is searchable after `wait_processed()` returns

#### Scenario: Import pre-processed text file
- **WHEN** a PDF cannot be parsed by OV's built-in parser
- **THEN** the system falls back to importing the pdfplumber-extracted text file via `client.add_resource(path="data/processed/600519_2023.txt", reason=<description>)`

### Requirement: Verify find retrieval
The system SHALL support querying OV Resources via `client.find(query, limit=N)` which returns a result object with `.resources` attribute (each item has `.uri`, `.score`, `.abstract`).

#### Scenario: Search imported report
- **WHEN** calling `client.find("贵州茅台发展战略", limit=3)`
- **THEN** the system returns relevant resources with score > 0, each having uri and abstract fields

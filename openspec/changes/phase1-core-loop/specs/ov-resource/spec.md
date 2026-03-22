## ADDED Requirements

### Requirement: OpenViking initialization
The system SHALL initialize an OpenViking client in embedded mode with a configured data path and embedding model. The system SHALL provide an `ov.conf` configuration file.

#### Scenario: Successful initialization
- **WHEN** calling OV initialize with valid config
- **THEN** the client is ready to accept resources and perform searches

### Requirement: Import annual report text as OV Resource
The system SHALL import parsed PDF text (from pdf-parser output) into OpenViking as Resources. Each annual report SHALL be a separate resource with metadata (company name, year).

#### Scenario: Import single report
- **WHEN** importing Moutai 2023 annual report text
- **THEN** OV creates a resource at `viking://resources/annual-reports/600519_2023`
- **AND** the resource is searchable after processing completes

### Requirement: Verify find retrieval
The system SHALL support querying OV Resources via `find()` with a natural language query and return relevant text segments.

#### Scenario: Search imported report
- **WHEN** calling find("贵州茅台发展战略")
- **THEN** the system returns relevant text segments from the Moutai annual report resource

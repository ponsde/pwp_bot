## ADDED Requirements

### Requirement: OpenViking initialization
The system SHALL initialize an OpenViking client in embedded mode with a configured data path. The system SHALL provide an `ov.conf` configuration file or equivalent documented initialization path.

#### Scenario: Successful initialization
- **WHEN** calling OV initialize with valid config
- **THEN** the client is ready to accept resources and perform searches

### Requirement: Import annual report text as OV Resource
The system SHALL import parsed PDF text into OpenViking as Resources by first materializing each parsed report as a local text or markdown file, then passing that file path to the OpenViking client. Each annual report SHALL be a separate resource with metadata (company name, year) encoded in its target URI and/or sidecar metadata.

#### Scenario: Import single report
- **WHEN** importing Moutai 2023 annual report text
- **THEN** OV creates a resource at `viking://resources/annual-reports/600519_2023`
- **AND** the resource is searchable after processing completes

### Requirement: Verify find retrieval
The system SHALL support querying OV Resources via `find()` with a natural language query and return relevant text segments.

#### Scenario: Search imported report
- **WHEN** calling find("贵州茅台发展战略") with `target_uri="viking://resources/annual-reports/600519_2023"`
- **THEN** the system returns relevant text segments from the Moutai annual report resource

### Requirement: OpenViking API compatibility
The implementation SHALL be compatible with the actual installed OpenViking Python SDK API. Specifically, the implementation SHALL use the real `SyncOpenViking.add_resource(path, to=..., ...)` and `find(query, target_uri=..., ...)` call patterns instead of assuming undocumented constructors or object types.

#### Scenario: SDK compatibility check
- **WHEN** running the OpenViking integration smoke test
- **THEN** the code path exercises `add_resource` with a local file path and `find` with `target_uri`

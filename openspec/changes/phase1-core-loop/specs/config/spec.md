## ADDED Requirements

### Requirement: Configuration from environment variables
The system SHALL load all sensitive configuration (API keys, API endpoints) from environment variables. The system SHALL provide a `.env.example` file documenting all required variables. The system SHALL fail fast with a clear error message if required variables are missing.

#### Scenario: All required env vars present
- **WHEN** the application starts with all required environment variables set
- **THEN** the configuration object is created successfully with all values populated

#### Scenario: Missing required env var
- **WHEN** the application starts without `LLM_API_KEY` set
- **THEN** the system raises a clear error: "Missing required environment variable: LLM_API_KEY"

### Requirement: Configuration provides project paths
The system SHALL expose paths for SQLite database, raw PDF directory, processed data directory, and OV data directory. All paths SHALL be relative to the project root with sensible defaults.

#### Scenario: Default paths
- **WHEN** no path overrides are set
- **THEN** SQLite path is `data/db/financial.db`, PDF dir is `data/raw/`, OV data dir is `data/ov/`

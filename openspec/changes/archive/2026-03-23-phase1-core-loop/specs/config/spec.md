## ADDED Requirements

### Requirement: Configuration from environment variables
The system SHALL load API keys and endpoints from environment variables via `.env` file. The system SHALL fail fast with a clear error if required variables are missing.

#### Scenario: Successful startup
- **WHEN** all required env vars (LLM_API_KEY, LLM_API_BASE, LLM_MODEL, EMBEDDING_MODEL) are set
- **THEN** the configuration object is created with all values populated

#### Scenario: Missing variable
- **WHEN** LLM_API_KEY is not set
- **THEN** the system raises an error naming the missing variable

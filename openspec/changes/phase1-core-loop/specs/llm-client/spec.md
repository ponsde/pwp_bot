## ADDED Requirements

### Requirement: Chat completion
The system SHALL call the LLM API via OpenAI SDK with configurable temperature and optional JSON mode. The system SHALL retry on transient errors (429/5xx/timeout) up to 3 times with exponential backoff.

#### Scenario: Normal completion
- **WHEN** calling chat_completion with a message list
- **THEN** the system returns the assistant's response as a string

#### Scenario: JSON mode with fallback
- **WHEN** JSON mode is requested but the API doesn't support it
- **THEN** the system falls back to extracting JSON from the text response via regex

#### Scenario: All retries exhausted
- **WHEN** all 3 retries fail
- **THEN** the system raises an exception with the last error

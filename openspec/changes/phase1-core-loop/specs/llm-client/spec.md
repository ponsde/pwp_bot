## ADDED Requirements

### Requirement: Chat completion API
The system SHALL provide a function to call the LLM chat completion API with a list of messages and return the assistant's response text. The function SHALL accept an optional `temperature` parameter (default 0.0) and optional `response_format` for JSON mode.

#### Scenario: Simple chat completion
- **WHEN** calling chat_completion with messages `[{"role": "user", "content": "Hello"}]`
- **THEN** the system returns the assistant's response as a string

#### Scenario: JSON response format
- **WHEN** calling chat_completion with `response_format={"type": "json_object"}`
- **THEN** the system returns a valid JSON string from the LLM

### Requirement: Embedding API
The system SHALL provide a function to generate embeddings for a list of text strings using the configured embedding model. The function SHALL return a list of float vectors.

#### Scenario: Single text embedding
- **WHEN** calling embed with `["营业收入"]`
- **THEN** the system returns a list containing one float vector

### Requirement: Error handling with retry
The system SHALL retry on transient API errors (timeout, 429, 5xx) up to 3 times with exponential backoff. The system SHALL raise a clear exception after all retries are exhausted.

#### Scenario: Transient API error with recovery
- **WHEN** the first API call returns HTTP 429 and the second succeeds
- **THEN** the system returns the successful response without raising an error

#### Scenario: All retries exhausted
- **WHEN** all 3 retry attempts fail
- **THEN** the system raises an exception with the last error message

## ADDED Requirements

### Requirement: Chat interface for financial Q&A
The system SHALL provide a Gradio web interface with chat input, SQL display panel, and chart display area.

#### Scenario: Ask and answer
- **WHEN** user types a financial question
- **THEN** the system displays: answer text, generated SQL (collapsible), chart image (if applicable)

#### Scenario: Multi-turn in UI
- **WHEN** user sends a follow-up message
- **THEN** the system uses conversation history for context

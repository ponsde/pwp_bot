## ADDED Requirements

### Requirement: Chat interface for financial Q&A
The system SHALL provide a Gradio web interface with a chat-style input box where users can type financial questions and receive answers.

#### Scenario: Ask a question and get an answer
- **WHEN** the user types "贵州茅台2023年营业收入是多少？" and submits
- **THEN** the system displays the answer in the chat history

#### Scenario: Display error gracefully
- **WHEN** the system cannot find an answer (SQL fails after retries)
- **THEN** the interface displays a user-friendly error message instead of a traceback

### Requirement: Show SQL query for transparency
The system SHALL display the generated SQL query alongside the answer, in a collapsible or secondary panel, so users can verify the data source.

#### Scenario: SQL visibility
- **WHEN** an answer is successfully generated
- **THEN** the generated SQL is visible in a secondary area below the answer

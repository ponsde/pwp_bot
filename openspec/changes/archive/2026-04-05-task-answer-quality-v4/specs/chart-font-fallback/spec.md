## ADDED Requirements

### Requirement: Chart renders Chinese text when system CJK fonts are missing
When no configured system CJK font (SimHei, WenQuanYi, Noto Sans CJK, etc.) is available, chart rendering SHALL fall back to a known system font path if present; otherwise it SHALL continue with matplotlib default font without raising an error.

#### Scenario: System has CJK font installed (by name)
- **WHEN** at least one CJK font from `_FONT_CANDIDATES` is found by `findfont`
- **THEN** behavior is unchanged (use system font as before)

#### Scenario: System has no named CJK fonts but has wqy-microhei at known path
- **WHEN** `matplotlib.font_manager.findfont` fails for all candidates in `_FONT_CANDIDATES`
- **AND** the file `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc` exists on disk
- **THEN** chart rendering SHALL load that font via `FontProperties(fname=...)` and set it as the default sans-serif font
- **AND** Chinese characters in chart title, labels, and axis SHALL render correctly

#### Scenario: No CJK font available at all
- **WHEN** no system CJK font is found by name AND the known system path does not exist
- **THEN** chart rendering SHALL proceed without error (using matplotlib default)
- **AND** a warning SHALL be logged indicating Chinese characters may not render correctly

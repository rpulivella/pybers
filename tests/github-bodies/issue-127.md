As a Python developer I want to apply a named paragraph style to a cell's whole contents in one call, whatever the cell holds, so that styling a sheet by script reads like styling one in InDesign.

## Acceptance criteria

1. A named paragraph style applied to a cell holding plain text shows as that cell's style in Numbers' Paragraph Styles menu.
1. The same call on a cell holding rich text gives every paragraph in the cell that style.
1. Applied to a range, each cell takes the style, and a merged block takes it once.
1. A style name the document does not hold is refused, and nothing is written.
1. Applying the style a cell already shows, with nothing to clear, reports no change and writes nothing.
1. Each case is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- **Blocked by PYB-8**, which establishes where a cell record keeps its style.
- **Open decision, and what holds this at Concept:** whether applying a style keeps or clears the cell's local overrides and character runs. InDesign offers both at the call site, and what Numbers does is not measured.
- Plain text keeps its style in the cell record and rich text keeps it in a run table, so one intent is two different writes (`findings-04-text.md`).

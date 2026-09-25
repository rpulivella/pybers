As a Python developer I want to create a named paragraph style based on another, so that a document built by script offers its styles to whoever opens it in Numbers.

## Acceptance criteria

1. A created paragraph style appears under its name in Numbers' paragraph style browser.
1. A style is based on an existing named style, as InDesign's Based On and CSS inheritance work, and every property it does not set follows that parent.
1. A name already held by a paragraph style in the document is refused.
1. A refused creation leaves the document unchanged.
1. The created style is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- **Being named and being listed are two writes.** A name alone makes a real style that Numbers never shows, measured in `42-table-titles-captions` (`findings-06-styles.md`).
- `pybers-base` is already created this way for every new table, so this generalizes an existing path rather than adding a second one.

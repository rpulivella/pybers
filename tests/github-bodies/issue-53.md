As a Python developer I want an edit inside a table of more than 255 columns to be exercised end to end so that the rewrite path is proven against a real document rather than against a hand-built row.

## Acceptance criteria

1. A test edits a cell in `tests/fixtures/45-columns-over-255.numbers`, saves, and reads the result back with every other cell in that row unchanged.
2. The saved document is confirmed once in Numbers and locked in as a golden file, so the check is against Numbers rather than against pybers.
3. A gap in the edited row is still a gap after the write, so an empty slot survives a rewrite.

## SPEC

- **The rewrite path is reached only by a unit test.** `applyTableEdits` skips `rewriteRow` when a row has no edits, so the unchanged round trip in `test_wide_columns.py` never reaches it, and the two direct tests there pass hand-built bytes rather than a document.
- **A merge is the one edit that reaches it, measured 2026-09-08.** Every cell is text, so a value write refuses by design, and a formula attach refuses because no dependency tile covers those columns. Adding a merge drops the covered record, which rebuilds the whole offset array, so the capability PYB-49 added makes this ticket buildable with no prerequisite.

[PYB-67](https://github.com/rpulivella/pybers/issues/67)

Node type 25 is a bracket the author typed rather than a list, and the renderer refused it. Reading, rendering and parsing one closes that gap, and the measurement behind it is in `findings-08-formula-text.md`. Two defects the same measurement surfaced are fixed here as well. A guessed table name ate the operator in front of it, costing 1469 formulas in one real document, and an address past the end of a table converted rather than being refused.

## Detail your changes
- [x] Known issues remain (described below)
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: one addition and one refusal. `FormulaGroup` is new and joins the `NodeContent` union, so `FormulaNode.content` can now hold one, and code matching exhaustively on that union gains a case. `columnNumber`, `columnLetter`, `CellReference` and `CellRange` now refuse an address past column 1000 or row 1000000, where `columnNumber("LEDGER")` returned 144936576 before. A caller relying on the old conversion breaks.

**Archive round-trip**: a formula authored from text now stores a node for every bracket, as Numbers does. Reading a file and writing it back unedited is unchanged. One formula in one real document, dragged into three cells, renders identically but gains a node when its text is reparsed, which is the normalization node type 23 already has rather than a new kind of loss.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None. The golden was confirmed by eye in Numbers 15.3.1 on 2026-09-13, including a bracket around a single value and one Numbers itself stores no node for. Recorded in `tests/golden/README.md`.

_Closes #67_

## Ticket
Link: https://github.com/rpulivella/pybers/issues/14
Closes #14

A script can now reach a sheet or a table by its name or its position, and iterate every cell in a document in a stated order, without digging through lists to find what it is acting on. `Document.sheet` and `Sheet.table` take either form, and `Document.cellsIterate` yields `(sheet, table, cell)` for each stored cell, so a caller writes `for sheet, table, cell in document.cellsIterate():` and the cell arrives knowing where it lives. Order comes from the file's own lists throughout, so a position is the place `TN.DocumentArchive.sheets` and `TN.SheetArchive.drawable_infos` put a thing rather than any ordering this library invents.

Three facts from the corpus shaped the API rather than being worked around. A table name is unique within its sheet and case-insensitively so, which is why matching a table folds case and why there is no document-wide table lookup: `20-formula-shapes` carries a `Table 1` on each of two sheets. Sheet names carry no such enforcement, so a repeated one raises rather than being folded into a collision the file does not have. Cells are sparse, so the walk covers cells that exist and leaves the empty rectangle to `Table.extent`.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

### The golden, and what confirming it found

The whole-document edit test is the first place this library writes edits into more than one sheet in a single save, so `documentEditsApplied` walking sheets and filtering tables out of each drawable list had no confirmed file behind it. `tests/golden/20-formula-shapes-multisheet-edited.numbers` closes that. Confirmed on 2026-09-02 in Numbers 15.3.1: it opened with no warning and no repair prompt, and all twelve edits landed in the table they were addressed to, across three tables and two sheets.

The confirmation also measured something the corpus had not settled. Row 11 of `Table 1` still displays the results those formulas cached before the edit, so `A11` shows 55 for `SUM(A1:A10)` while `A1:A10` now sums to 10055. **Numbers does not recalculate on open.** `findings-02-formulas.md` had recorded that a formula caches its result without establishing when the cache is refreshed, and this PR adds the measurement under that finding. The behavior belongs to the write path rather than to the walk, and it is now #25.

The golden README carries one more note worth reading before the next one is confirmed: the first copy of this file was opened in place, and autosave rewrote it on open, so the committed bytes are the untouched writer output rather than the copy that was on screen.

### One commit landed after the review

`6f5d094` moves the `Code Review` status step out of `/ticket-startwork`, which has already exited by the time a pull request exists, and into `/pr-review-code` step 6 beside `pr.py ready`. That gap is why this ticket sat at `In Progress` with an open pull request. The commit changes two markdown files under `.claude/commands/` and touches no source and no tests. Both gates were rerun on it and pass, at 668 tests and 0 standards failures, but the rubric review above was performed before it and does not cover it.

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None.

**Object model (public dataclass fields)**: None. `Cell`, `Table`, `Sheet` and `Document` keep every field they had, and no new type is introduced. `Sheet.table`, `Document.sheet` and `Document.cellsIterate` are additions beside the existing `sheets` and `tables` lists rather than replacements for them.

**Archive round-trip**: None. Nothing in `pybers.reader`, `pybers.writer` or `pybers.numbersfile` changed.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

There is no archive-layer change in this PR, and the round-trip and golden tests pass anyway, including the new multi-sheet golden. The suite is at 668.

## Screenshot(s) / video(s)
None

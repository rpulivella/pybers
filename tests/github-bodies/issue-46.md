[PYB-42](https://github.com/rpulivella/pybers/issues/42)

A formula can now be written into a cell that had no record at all, taken off a cell, and filled across a range the way dragging one fills it in Numbers. Filling stores ONE formula and points every cell at it, so relative references follow each column and locked ones stay put with no special cases, which is what Numbers does rather than a simulation of it. All seven acceptance criteria were confirmed by opening the output in Numbers 15.3.1, and the biggest trap that surfaced fails silently: **the calculation engine keeps its own register of which cells hold formulas, stored twice**, in `cell_dependencies` and again tiled by column. Setting the record flag and pooling the archive is necessary and not sufficient, and updating only one register leaves Numbers showing the formula in its formula bar while never evaluating it. `findings-02-formulas.md` records all three attempts.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: `Table` gains `formulaFill`. No field changed.

**Archive round-trip**: the pooled formula list now SHARES an identical formula rather than storing a second copy, which is what makes filling correct. Two goldens confirmed earlier the same day became byte-different and were re-confirmed rather than left claiming a check performed against other bytes. A created record is type 8, the shape Numbers writes for a formula it could not compute, and Numbers repairs a record type it disagrees with while recalculating, so no caller declares what a formula will evaluate to.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #42_

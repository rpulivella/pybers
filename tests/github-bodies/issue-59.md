[PYB-45](https://github.com/rpulivella/pybers/issues/45)

A formula can now be written the way it is typed in Numbers and read back as the text Numbers displays for it, while the file continues to hold nothing but nodes. Every formula in the corpus is rendered and parsed again, starting from an AST that came out of Numbers.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

**The golden caught a silent defect.** `encodeFormulaReference` left the cross-table identity to the archive bytes each node carried, and a node built from text carries none, so a formula naming another table stored as one naming its own. It reads back as a good formula pointing at the wrong table.

**The operator table and the thunk rule come from Numbers itself**, the `ASTNodeType` enum and `+[TSCEFunctionSpec functionIndexUsesThunks:]`. `findings-08-formula-text.md` records both.

**Three corpus formulas round trip through the text and not through the node type.** Each carries node type 23, whose placement rule is not established, and each is named in the test so a fourth is a failure.

The reader and the writer were split by concern along the way, a pure move: the largest module goes from 1228 lines to 559. The package-wide re-layout is PYB-58.

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: `Table` gains `identifier` and `document`, `Cell` gains `table`, and all three are excluded from equality and `repr`, so nothing that compared a cell or a table before compares differently now. `Cell` also gains the `formulaText` property and `formulaSet`. **Archive round-trip**: a written reference or range now carries its cross-table identity, which no formula this library wrote could do before. An unchanged document still round trips byte for byte.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None. The golden was confirmed in Numbers 15.3.1 and Quick Look on 2026-09-08, recorded in `tests/golden/README.md`.

_Closes #45_

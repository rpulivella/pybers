[PYB-13](https://github.com/rpulivella/pybers/issues/13)

Every reference a document's formulas make is now enumerable in one call, resolves to the `Table` it points at, and can be moved to follow a target that moved. Building the golden for it exposed a separate defect in the formula writer: a range authored from text carried its anchoring in the tract and nowhere else, so Numbers read `SUM($A$1:$A$5)` as unanchored.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: None. `ReferenceLocation` is new, and `Document` gains `referencesIterate` and `tableFor`, but no existing field changed.

**Archive round-trip**: a range now carries `ASTStickyBits` beside its tract, and that second copy is the one Numbers reads. All 9 ranges in the corpus carry them and none is without, so this brings pybers in line rather than inventing a form. Ranges read from a file re-encode byte for byte; only ranges built from text change. Both affected goldens were regenerated and confirmed in Numbers 15.3.1 on 2026-09-09, and the same three cells that displayed as `SUM(A1:A5)` before the fix display as `SUM($A$1:$A$5)` after it.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #13_

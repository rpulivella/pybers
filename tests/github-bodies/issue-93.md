[PYB-92](https://github.com/rpulivella/pybers/issues/92)

Merging cells now releases the formulas, rich text, strings and styles of the records the merge removes, so a later edit in Numbers cannot discard an entry other cells still use, or keep one nothing uses. A string entry released to 0 is removed at the end of the save, as Numbers removes it, and its key stays retired. The calculation engine also learns of each formula a merge removes. Every count rule is measured against the fixtures and recorded in findings-01-values.md.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Known issues
None

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: None
**Archive round-trip**:
- A merge releases the string and the byte 8 styles of each record it removes
- A merge releases the formula and the rich text of each record it removes, and the engine no longer registers a removed formula cell
- A string entry released to 0 is removed unless a cell still names it, and `nextListID` is unchanged
- `11-text-written-and-retyped`, `45-merged-by-pybers` and `22c-merged-by-pybers` are regenerated, `18-merged-over-a-formula` is new, and each was confirmed in Numbers 15.3.1 on 15 September 2026.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #92_

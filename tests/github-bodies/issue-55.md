[PYB-49](https://github.com/rpulivella/pybers/issues/49)

A document converted from Excel did not open at all. Excel writes a cell for every position of a merged range, a covered one carrying a style and no value, and Numbers keeps each of them on import and across every later edit. The reader called `Table.cell` for those positions, which refuses a covered address by design, so the first covered record raised and the whole document was unreadable.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: None **Archive round-trip**: A save no longer strips covered records from a merge it did not create. Every fixture still writes back byte for byte, and a merge pybers makes still clears its covered positions, which `22c-merged-by-pybers` confirms in Numbers.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #49_

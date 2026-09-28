[PYB-62](https://github.com/rpulivella/pybers/issues/62)

A table now walks its declared grid, whole through `Table.gridIterate` or row by row through `Table.rows`, and reaches a cell by `row=` and `col=`. A row is a view that creates a cell only when one is reached, and it counts cells rather than columns, so a merged block sits at its anchor alone. `Cell.mergeAnchored` names the merge a cell anchors, and a merge written with `$` markers no longer discards its own anchor.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: `MergeRange.extent` no longer keeps the locking markers it was built with, so `$A$1:B2` and `A1:B2` are one merge.
**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

No archive code changed, and a walk followed by a save writes the same archives as a save alone.

## Screenshot(s) / video(s)
None

_Closes #62_

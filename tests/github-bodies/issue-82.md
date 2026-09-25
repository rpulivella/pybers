[PYB-78](https://github.com/rpulivella/pybers/issues/78)

Numbers writes a row into a tile only when the row holds something, so a table declaring ten rows can store one. The write path walked those stored rows, never saw the others, and dropped a formula written into one while reporting success. Rows the model needs are now built before that walk runs, so the walk itself is unchanged.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: None

**Archive round-trip**: a save may now add a `TileRowInfo` where it previously added
nothing, and corrects `numrows` to match. `cell_count` is set only on a row this save created, because an edited row carries the count Numbers wrote and this library has never maintained it. Reading a file and writing it back unedited is unchanged, and every existing golden still matches byte for byte.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None. The golden opened in Numbers 15.3.1 on 2026-09-14 with no repair prompt, the four formulas calculating, and the rows nobody wrote to still empty. Recorded in `tests/golden/README.md`.

_Closes #78_

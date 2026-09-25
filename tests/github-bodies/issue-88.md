[PYB-63](https://github.com/rpulivella/pybers/issues/63)

`Document.sheetAdd` and `Sheet.tableAdd` create sheets and tables that open in Numbers, built from templates taken from files Numbers wrote, and registered in the package metadata and the calculation engine. Both start from the pybers reset recorded in `docs/decisions.md`: a sheet printed 1:1, and a table with no strokes, no title and a named `pybers-base` text style, placed at a given top-left corner or below the tables already there. A value written into a created table displays in Numbers, and the measurements behind every step are in `tests/fixtures/findings-10-creation.md`.

Known issue: two or more numbers written into a created table share one automatic number format whose refcount stays at 1, the same undercount PYB-89 tracks for text. A formula in a created table is refused until PYB-86.

## Detail your changes
- [x] Known issues remain (described below)
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: `Sheet` gains `document`, and `Sheet` and `Table` gain the private `_identifier`, with `Table` also gaining `_origin`. All default to None and are excluded from equality, so no existing call changes.
**Archive round-trip**: A save now creates the archives of an added sheet or table. An unchanged document still writes back byte for byte, and a save that fails restores the package and the model's identifiers in memory.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #63_

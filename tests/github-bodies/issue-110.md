[PYB-17](https://github.com/rpulivella/pybers/issues/17)

`Table.rowAdd`, `rowRemove`, `columnAdd` and `columnRemove` add and delete rows and columns, and every formula in the document follows: a range moves only the end past the edit, and a reference whose cell is deleted breaks the way Numbers breaks it. The saved file carries the edit into merges, hidden lines, borders, bands, conditional highlighting, tiles, header buckets and the calculation engine, each compared against a document Numbers edited the same way. Four goldens were confirmed in Numbers 15.3.1.

## Detail your changes
- [x] Known issues remain (described below)
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Known issues
- A save reads each archive as the document opened it, worked around by reading each only once, PYB-109

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: a golden's expected-values file names its manual checks `qa` rather than `human`, and the golden-confirm report heads them "Left for QA".
**Object model (public dataclass fields)**: `FormulaReference` gains `loss`, a `FormulaReferenceLoss` naming the rows and columns a broken reference lost, defaulting to `None`.
**Archive round-trip**: a broken locked reference is written with the locks Numbers writes, and a row's offsets are read by the row's own width flag rather than its tile's. An unchanged document still writes back byte for byte.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change
- [x] I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

## Screenshot(s) / video(s)
None

_Closes #17_

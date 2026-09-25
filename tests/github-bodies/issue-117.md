[PYB-113](https://github.com/rpulivella/pybers/issues/113)

Each concern of the write path now sits in one module. A table's whole save is reached through `TableSave` in `table/_write.py`, so the document writer only walks sheets and tables. The calculation engine is a package with one module per concern, and every archive type identifier is written once, in the type registry.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
None

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

Tests that imported moved private names now import them from their new modules. No assertion changed, and the suite passes 2378 of 2378 at every commit, the same count as on `develop`.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change
- NA I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

No golden is earned, because no saved file changes.

## Screenshot(s) / video(s)
None

_Closes #113_

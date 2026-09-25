[PYB-86](https://github.com/rpulivella/pybers/issues/86)

A formula written into a table pybers created now opens in Numbers showing its result, and recomputes when what it reads changes. Getting there took two fixes, both found by opening a golden in Numbers rather than by any test, and both recorded in the findings.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Known issues
- Created tables sit slightly too close together, which predates this work, PYB-87

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: the preflight no longer runs on a push to `develop`, so the
README badge, which read that branch alone, is removed.
**Object model (public dataclass fields)**: None
**Archive round-trip**: a created table's `table_id` is now its calculation-engine
identity, and every formula pybers writes declares what it reads. Both change what a written file holds; neither changes what an unedited save writes.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #86_

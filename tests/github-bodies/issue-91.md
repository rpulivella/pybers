[PYB-89](https://github.com/rpulivella/pybers/issues/89)

Every format entry pybers changes now counts exactly the cells that name it, so a later edit in Numbers cannot discard a format other cells still use. Writing a cell also stores the kind of format it displays with in byte 9 `0x10`, where pybers had been writing a format key that only matched by coincidence. Both rules are measured against every fixture and recorded in findings-01-values.md, together with what Numbers does with a format nothing names, which pybers now matches.

## Detail your changes
- [x] Known issues remain (described below)
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Known issues
- A merge does not yet release the strings and styles of the records it removes, PYB-92

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: None
**Archive round-trip**:
- A save now writes format refcounts that match their cells, where it had counted one reference per format kind per save
- A written cell stores its format kind (1 number, 5 text) in byte 9 `0x10`
- A format entry released to 0 is removed, as Numbers removes it, unless a cell still names it
- A merge releases the format references of the records it removes
- `11-text-written-and-retyped`, `20-first-text-in-a-table`, `20-tables-added` and `45-merged-by-pybers` are regenerated, and each was confirmed again in Numbers 15.3.1 on 15 September 2026

## Checklist (before requesting review)
- [ ] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #89_

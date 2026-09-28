[PYB-65](https://github.com/rpulivella/pybers/issues/65)

A cell record ends in a run of references and the formula key is not at a fixed place among them: each attribute a cell carries puts one ahead of it. Reading a constant slot found a key the table's pool does not hold, so the cell read as though it never had a formula and the save then removed it, 416 times across one real document.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: None

**Archive round-trip**: `pybers.open` now RAISES on a cell record naming a formula key its table's pool does not hold, where it used to report the cell as holding no formula. That silent answer is what the writer then acted on, so the change is the point rather than a side effect, but it does mean a document that opened before can now be refused. No record across the corpus's 52 documents reaches that path. Files themselves are unaffected: every fixture still writes back with every archive unchanged, and the one document that failed that contract now passes it.

**PYB-66 is fixed by the same commit** and will be closed separately with a pointer here, rather than silently by this merge. Its symptom was a reference resolving to a column at or before the first, which came from attributing a formula to the wrong cell: a reference is an offset from the cell holding it, so the wrong host moves every reference in it.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #65_

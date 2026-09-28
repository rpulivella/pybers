## Ticket
Link: https://github.com/rpulivella/pybers/issues/9
Closes #9

Addressing becomes a type. `CellReference`, `CellRange` and `CellRangeList` replace the loose
helpers and the bare row and column pairs that #1 shipped as its minimum, and a table can now
be addressed only through them or through the strings they parse from. Two things the fixtures
corrected along the way are in here as well: a reference carries its `$` locking as two
independent per-axis facts, and a table's size is declared by the archive rather than derived
from the cells that happen to hold something. Addressing a position that no cell occupies,
because it sits outside the declared grid or under a merge, now raises rather than quietly
creating one.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes

**CI / automation / build**: three permission grants narrowed because they read as read-only
and were not. `git branch:*` also covered `git branch -D` and `-m`, and `sed:*` also covered
`sed -i`. `find:*` also covered `-delete` and `-exec`, which no prefix can exclude because the
flags follow the path, so that grant is removed and Glob replaces it.

**Object model (public dataclass fields)**: substantial, and every change is deliberate rather
than incidental.

- `Table.cellAt(row, col)` is gone. `Table.cell(address)` takes a `CellReference` or an
  A1-style string and nothing else, so a bare pair is rejected by a static checker before
  anything runs.
- `Table.mergeCovering` takes an address rather than a row and column.
- An address swallowed by a merge raises. A merged region is one cell reached through its
  anchor, and handing back an empty cell for a covered position filed a record the archive
  never had, which a later save would have written out. `Table.range` skips covered
  positions, so a range across a merged block yields the anchor once. `Table.addressable`
  is the predicate behind both, for a caller who would rather test than catch.
- `Table.range` refuses a rectangle that reaches past the declared grid rather than
  clipping it, and the refusal names the range that was written rather than the first cell
  inside it that fell off the edge.
- `Table.cells` is keyed by `CellReference` rather than by a tuple. Keys are unlocked first,
  so `$A$1` and `A1` remain one cell rather than two entries.
- `Table` gains `rowCount` and `colCount`, and `Table.extent` reports that declared grid. An
  address outside it raises, because a Numbers table is a fixed number of rows and columns
  rather than an endless sheet. There is no way to grow a table yet. `rowAdd` and `colAdd`
  belong to a structural-edit ticket.
- `Cell.reference` is a `CellReference` rather than a string, and it is the first field.
  `Cell.row` and `Cell.col` are removed, so a cell reports one address rather than two
  representations of it.
- `MergeRange` carries a single `extent: CellRange` in place of its four numbers, and refuses
  an unbounded one.
- `columnLetter` and `columnNumber` moved to `pybers.model.reference`, which is now the only
  public conversion between a column letter and a column number. `parseReference` is removed and
  `CellReference.parse` replaces it.

**Archive round-trip**: None. The reader is the only archive-side change, and it reads two
fields it previously ignored.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

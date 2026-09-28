## Ticket
Link: https://github.com/rpulivella/pybers/issues/1
Closes #1

`pybers.open(path)` now returns a `Document` and walks it: sheets in document order with
the names Numbers shows, tables in the sheet's own drawable order, cells addressed by A1
reference or by row and column, values decoded to `Decimal`, `str`, `datetime`, `timedelta`
and `bool`, and merged regions read from the merge store. All 46 fixtures open and every
cell of every table reads.

The three ordering traps the fixtures established are handled rather than left to a caller,
because each one yields a plausible wrong answer instead of an error: sheets, drawables and
tiles resolve through their own lists rather than archive order, a document row is
`tileid * tile_size + tile_row_index` because the tile index is local to its tile, and
pooled strings are followed to their text rather than left as the integer keys they are
stored as.

Two commits here are tooling rather than library work, because opening this pull request is
what surfaced them. `scripts/pr.py` carried two calls passing a `ticket` argument their
signatures stopped taking when the module moved from injecting that dependency to importing
it. Neither had ever run. The first blocked this pull request outright; the second sat on
the merge path inside a handler that prints "whether it landed is unknown", so the first
merge would have reported an unknown outcome having sent nothing at all. `pr.py` also gained
an `edit` subcommand, without which a body cannot be corrected as a branch grows and a
waived preflight stage cannot be recorded where the review process requires it.

Acceptance criterion 7 of the ticket is struck through rather than met. Attaching a style to
a cell needs the cell record's flag bitmask decoded first, and `findings-01-values.md`
records that mapping as open work, so it is extracted to #8.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None. `scripts/pr.py` gains an `edit` subcommand and loses two
never-reachable call defects. Both are additive or corrective.

**Object model (public dataclass fields)**: **Rows and columns now count from one.** The
archive counts from zero and the model no longer does, so `Cell.row` and `Cell.col`, the
keys of `Table.cells`, and `MergeRange.anchorRow` and `anchorCol` are all one greater than
before. `Table.cellAt` rejects a row or column below one rather than accepting it, which is
what turns the zero-based instinct into an error instead of a neighboring cell. The two
existing tests that used `cellAt(0, 0)` were converted in the same commit that made the
change, so the suite is green at every commit. `Cell` gained a `reference` property and
`Table` gained `cell()` and `mergeCovering()`.

**Archive round-trip**: None. This branch adds a read path only. Nothing writes.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

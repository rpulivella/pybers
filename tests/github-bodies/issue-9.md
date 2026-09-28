As a Python developer I want to address cells the way Numbers does, by reference, so that
the code I write reads like the spreadsheet I am looking at rather than like arithmetic on
its storage.

1. `CellReference` addresses one cell. It is built from an A1-style string or from a row
   and column, carries both, and reports each: `asReference()` gives `"B2"` and
   `asRowColumn()` gives `(2, 2)`.
   1.a Parsing anything either type emits returns an equal value, for every reference in
   the fixture corpus and across the base-26 boundaries.
   1.b A row or column below one is rejected when the reference is constructed, so the
   zero-based instinct fails once at the reference rather than in every method that
   takes a coordinate.
2. The `$` markers survive as two independent facts. `$A1`, `A$1` and `$A$1` each parse,
   compare unequal to one another and to `A1`, and re-emit with the markers they were
   written with.
3. `CellRange` addresses a rectangle, built from `"A1:C3"` or from two `CellReference`
   values.
   3.a It reports `rowSpan` and `colSpan`, and whether it covers a given cell.
   3.b Iterating it yields every `CellReference` it covers, in row-major order.
4. A whole-column reference (`"A"`) and a whole-row reference (`"1"`) parse into a range
   that is unbounded on the other axis, and an unbounded range is distinguishable from one
   that happens to span the same cells.
5. A comma-separated list (`"A1:B2,D4:E5"`) parses into the ranges it names, in the order
   written, and re-emits in that order.
6. `Table` addresses cells through these types and through the strings they parse from,
   and through nothing else. A bare row and column pair is no longer an addressing path,
   so a static checker rejects it before anything runs.
   6.a `Table.range` returns the cells a range covers, and an unbounded range is bounded
   by the table's own extent there, which is the only place that extent is known.
7. `MergeRange` expresses its extent as a `CellRange` rather than repeating the span
   arithmetic, and `Table.mergeCovering` behaves exactly as it does now.
8. An invalid reference raises `ReferenceError` naming what was rejected, and there is
   exactly one public way to convert between a column letter and a column number.

## SPEC

Three things that produce a valid-looking wrong answer rather than an error.

- **Column labels are base-26 with no zero digit.** `Z` is 26 and `AA` is 27, so an
  ordinary base conversion is off by one at every 26 boundary and yields a real column,
  simply not the requested one. This was hit once already while writing `columnLetter`.
- **`$` is a per-axis boolean, not a property of the reference.** A single absolute flag
  cannot represent `$A1`, and mixed locking is real rather than hypothetical: `$B1+C$1`
  decodes to an absolute column beside a relative row, then the reverse, in one formula.
  See `findings-02-formulas.md`.
- **The model counts from one and the archive counts from zero.** A reference type must
  never hold an archive coordinate. That conversion lives at the reader and writer
  boundary and nowhere else. See `pybers.reader`.

This supersedes the addressing #1 shipped. `Table.cellAt(row, col)` and the loose
`columnLetter`, `columnNumber` and `parseReference` functions in `pybers.model.table` were
the minimum that ticket needed, and AC 6 and AC 8 retire them.

Cross-table references (`Table 1::A1`) and the relative offsets a formula stores are out
of this ticket.

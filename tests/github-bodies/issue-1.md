As a Python developer I want to open a `.numbers` file and walk its sheets, tables and
cells as typed objects so that I can read a real document without knowing anything about
the archive format.

1. `pybers.open(path)` returns a `Document` for every fixture under `tests/fixtures/`
   without raising.
2. `Document.sheets` yields each sheet in document order, carrying the sheet name Numbers
   shows in its tab bar.
3. `Sheet.tables` yields each table in the order the sheet itself gives.
4. `Table` exposes its cells by row and column, and a cell absent from the archive reads
   as an empty `Cell` rather than raising or shifting its neighbors.
5. `Cell.value` decodes every type the archive layer already reads: number, text, date,
   boolean, duration and currency.
   5.a Numbers are `Decimal`, never `float`, and a value round-trips through `str` with
   no digits gained or lost.
   5.b A cell carrying a formula exposes its cached result as `value`.
6. `Table.mergeRanges` reports every merged range read from the merge store, and a cell
   covered by a merge is distinguishable from an empty cell.
7. ~~A `Style` reached from two different cells that share one style archive is the
   identical object, and no caller can mutate it.~~ Extracted to #8. Attaching a style to
   a cell needs the cell record's flag bitmask decoded first, and
   `findings-01-values.md` records that mapping as open work.
8. Reading every cell of every table succeeds across the whole fixture suite, asserted
   against the contents each fixture labels in itself.

## SPEC

Three things the fixtures establish that a build would otherwise get wrong without
failing. Everything else is the ACs' business.

- Drawables and tiles resolve through their own lists, never through archive order. See
  `findings-03-structure.md`.
- Merges live in the merge store, where they are stored as formulas, and cannot be
  inferred from cell geometry. Same finding.
- Cell values come from `pybers.archive.cells`, which already decodes them. A type it
  cannot read is a separate ticket against that layer, not a second decoder here.

The write path is #2, and formula decoding, style resolution through the variation chain
and graphical objects each have their own ticket.

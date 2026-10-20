# Fixtures: the origins

A fixture is a document no other document here was made from: the control every measurement
starts from, or a document that came from outside, by import or from real use. A document made
from one of these by a single change is a measurement, in
[`tests/measurements/`](../measurements/README.md). What each established is indexed in
[FINDINGS.md](../../docs/findings/FINDINGS.md).

Tests name a document by its stem through `findDocumentPath` in `tests/conftest.py`, so a test
never depends on which directory holds it.

## Adding one

- Saved from the Numbers release `src/pybers/protos/README.md` records, or a later one pybers
  reads, which the catalog row then names.
- Label what each cell **displays**, in text beside it, so a decode can be checked rather
  than believed. What was typed cannot be recovered from the file.
- Keep what made it (a `.csv`, a generator script) beside it under the same stem.

## Catalog

| Document | Origin | What it holds |
| --- | --- | --- |
| `00-baseline` | a new document, re-made from `01-text-plain` with its cells cleared | the control: every star-derived measurement is this plus one change |
| `22c-merge-overpaints` | a new document | four merge and fill gestures, none of which leaves a record at a covered position ([structure](../../docs/findings/findings-03-structure.md)) |
| `22d-merge-multi-row` | imported from `22d-merge-multi-row.csv` | merges taller than one row over cells naming their own addresses ([structure](../../docs/findings/findings-03-structure.md)) |
| `22e-merge-imported` | imported from the `.xlsx` that `22e-merge-imported.py` writes | style-only records at covered positions, which only an import produces ([structure](../../docs/findings/findings-03-structure.md)) |
| `27-big-table` | imported from `27-big-table.csv` | 2001 rows split into 8 tiles ([structure](../../docs/findings/findings-03-structure.md)) |
| `45-columns-over-255` | imported from a generated CSV | 300 columns, past the fixed 255-slot offsets array ([values](../../docs/findings/findings-01-values.md)) |
| `47-formula-cell-attributes` | a new document | formula cells that also carry a style, a format, conditional highlighting and a comment ([cell records](../../docs/findings/findings-09-cell-records.md)) |
| `48-table-inserted` | a new document | the origin of the table and sheet creation measurements ([creation](../../docs/findings/findings-10-creation.md)) |
| `52-table-reset-styled` | a new document | the pybers reset applied through the interface ([creation](../../docs/findings/findings-10-creation.md)) |
| `53-paragraph-style-named` | a new document | the reset's text style saved as the named style `pybers-base` ([creation](../../docs/findings/findings-10-creation.md)) |
| `72-date-time-zones` | a new document, saved by Numbers 15.4 | `2026-10-20 09:00` typed on a Mac in New York and again in Los Angeles, and the same time typed with `PST`, each labeled ([values](../../docs/findings/findings-01-values.md)) |

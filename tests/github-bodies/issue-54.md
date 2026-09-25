As a Python developer I want pybers to read a merge that spans more than one row so that a real spreadsheet's merged headers and grouped rows survive a round trip.

## Acceptance criteria

1. `tests/fixtures/22d-merge-multi-row.numbers` exists, holding a two-row vertical merge, a two-by-two rectangular merge and a three-row merge, each labeling its own contents as every other fixture does.
2. Every cell immediately beside a merge holds a labeled value, so an extent read a row too tall or a column too wide lands on real content rather than on empty space.
3. That fixture opens, and each merge reports the extent Numbers displays.
4. Reading it and writing it back leaves the archives identical.
5. A position covered by a multi-row merge is refused through the public API and reachable through its anchor, exactly as a single-row merge already is.

## Constraints

- **Every merge in the corpus is single-row.** Measured 2026-09-06 across all 35: thirty-four are one row by two columns and one is one row by three. The vertical axis of a merge extent has therefore never been read, while the example documents hold twenty-seven vertical merges in a single table.

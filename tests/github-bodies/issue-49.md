As a Python developer I want pybers to open a document whose merged cells carry records so that a merge written by Numbers does not make the whole document unreadable.

## Acceptance criteria

1. `tests/fixtures/22e-merge-imported.numbers` exists, saved by Numbers from an Excel workbook whose merged ranges keep a styled cell at every covered position, labeling its own cells as every other fixture does.
2. That fixture opens, and the merge anchor reports the value Numbers displays.
3. A covered position's record survives a round trip, so writing the document back leaves the archives identical.
4. Creating a cell at a covered position through the public API still refuses, so the phantom-anchor defect stays fixed.
5. `tests/fixtures/22c-merge-overpaints.numbers` exists, recording that no gesture in Numbers itself produces a covered record, so the import path is not mistaken for the general case.

## Constraints

- **Only an import produces this shape, and the ticket was filed believing a merge did.** Measured 2026-09-07 against `22c-merge-overpaints`: content then merge, style then merge, a row-header fill after merging and a column-header fill after merging all leave every covered position empty. Excel writes a cell for every position of a merged range, a covered one carrying a style and no value, and Numbers keeps each one on import and across every later edit while never creating one itself.
- **The guard is right and its placement is wrong.** Refusing to create a covered cell is what stopped the phantom-anchor defect recorded in findings-03; refusing to record one already on disk is a different question with the opposite answer.
- **A covered record never carries a value.** All 37 in the example documents are style-only, and Numbers discards a covered cell that Excel gave both a style and a value, so nothing the object model represents is lost by declining to expose one.

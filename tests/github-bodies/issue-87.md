As a Python developer I want to place any item on a sheet by a named anchor and set the row heights and column widths it is built from, so that a script lays out a printed page exactly rather than leaving items to be nudged by hand afterward.

## Acceptance criteria

1. Any item on a sheet, a table or anything else, is placed by one of nine anchors, named as CSS `background-position` names them:
   1. each of its four corners,
   1. the middle of each of its four edges,
   1. its center.
1. An item placed by an anchor opens in Numbers with that anchor at the requested point on the sheet.
1. A single row's height and a single column's width are each set on their own, and Numbers shows the size that was set.
1. The size pybers reports for a table equals the size Numbers draws it at, including a row Numbers grows to fit its text.
1. Placing an item or resizing a row or column leaves every value, formula and merge in the document as it was.

## Constraints

- A table's stored `geometry.size` is stale and never updated after creation (findings-03-structure.md). Numbers also draws a row at its fitted height when that exceeds the stored one: a 24 pt row of 11 pt text on exact 15.5 pt spacing draws at about 24.43 pt (findings-10-creation.md).
- Whether a cell border adds to a row's drawn height was unmeasured as of 2026-09-14.
- Open decision: whether a point on the sheet is measured from the sheet's origin or from its print margins.

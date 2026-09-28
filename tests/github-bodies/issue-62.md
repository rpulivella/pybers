As a Python developer driving this library from a script, I want to walk a table's cells and reach one by number, so that a batch over a grid reads as a loop rather than as a string-building exercise.

## Acceptance criteria

1. A table walks its declared grid and yields each cell once, a merged block appearing at its anchor and nowhere else.
2. A table walks row by row, and the rows and the cells in a row each support `len`, indexing and slicing.
3. Measuring or slicing a walk creates no cell. Only reaching one does.
4. A table that declares no grid walks as nothing rather than raising.
5. A cell is reached by number with its axes named, so `row=3, col=5` names the cell that `E3` names.
6. A cell a walk yields is the cell `Table.cell` returns for that address, so a loop and a lookup cannot disagree and a write through either reaches the file.
7. A cell says which merged block it anchors, and says nothing when it anchors none, so a loop that has to act on a merge needs no second lookup.

## Constraints

- `Table.cell` creates a cell on first access and keeps it, which is what makes a write through a walk reach the file. A walk yielding a cell the table does not hold would swallow every write made through it.
- Measured 2026-09-08: walking the declared grid of `20-formula-shapes` takes its stored cells from 26 to 96 and changes nothing in the saved file, so the cost of a walk is in the model rather than on disk.
- `Table.range` already skips a position a merge swallowed and `Table.cell` already refuses one, so a walk carries that knowledge rather than a second copy of it.

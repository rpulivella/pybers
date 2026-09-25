As a Python developer I want to add a sheet to a document and a table to a sheet, so that a script can put its output somewhere new rather than only over something that was already there.

## Acceptance criteria

1. A sheet added to a document opens in Numbers as a new tab, carrying the name it was given, at the position it was added.
2. A table added to a sheet opens with the rows and columns it was asked for.
3. A cell in a table this library created takes a value, and that value is what Numbers shows when the document is opened.
4. A document that gained a sheet or a table still opens with every sheet, table, formula and merge it already had, untouched.
5. A table added under a name its sheet already carries takes the name Numbers itself would give it.

## Constraints

- Every write this library performs today mutates archives that were read. A new table needs archives Numbers writes and this library has never created, among them a table model, a tile, a data store and an entry in the calculation engine.
- A table's identity for formulas lives on the engine's dependency entry rather than on the table, so a table without one cannot be named by a formula.
- Numbers enforces table names per sheet, case-insensitively, and enforces nothing about sheet names, so the two are not one rule.

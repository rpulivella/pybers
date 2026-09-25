As a Python developer I want to write a formula into a table pybers created so that a script can build a table and its calculations in one pass rather than only filling in tables that were already there.

## Acceptance criteria

1. A formula written into a table pybers created opens in Numbers showing its result, and the formula bar shows the formula as written.
2. A formula in a created table that reads a value in the same table recalculates when that value changes in Numbers.
3. A formula in a created table that reads another table, created or already present, resolves to that table.
4. Writing a formula into a created table leaves every other table, formula and merge in the document as it was.
5. Saving that document again with no edit writes every archive unchanged, and it still opens showing the formula's result.

## Constraints

- Saving refuses today because a created table's calculation-engine owner holds no dependency tile, and a formula cell has to be registered in both of the engine's registers or it is never evaluated. See findings-02-formulas.md.
- What Numbers writes for the first formula in a table was unmeasured as of 2026-09-14. A fixture typing one formula into the inserted table of `48-table-inserted` is the pair that settles it.

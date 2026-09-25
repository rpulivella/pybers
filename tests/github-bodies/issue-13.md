As a Python developer I want a formula that points at another table or sheet to survive reading, writing and scripted rewriting so that a document built on cross-references can be edited by script without breaking the links a person depends on.

## Acceptance criteria

1. A formula that references a cell in another table reads back with its target identified, and that target resolves to the `Table` object it names.
   1. A reference into another sheet resolves the same way, since the archive draws no distinction between the two cases.
   1. Addressing stays table-local. A `CellReference` never names a table, and another table's cell is reached by holding that `Table` and asking it.
2. Every reference in every formula in a document is enumerable in one call, so a script can walk all of them without knowing in advance which cells hold formulas.
3. A document carrying cross-table formulas reads and writes back unchanged, and the result opens in Numbers with every link intact.
4. A scripted retarget works end to end: every reference pointing at one named table moves down one row and right seven columns, and no reference pointing anywhere else moves.
   1. A locked axis does not move. `B$1` shifted down one row is still `B$1`.
   1. A reference that was already broken stays broken rather than being repaired into a real cell.
   1. A range moves both ends together, so `C3:C25` shifted down one becomes `C4:C26`. Moving one end is what a retarget must not do.
5. A cross-table reference survives renaming the table it points at, because the archive names its target by identity rather than by name.

## Constraints

- **PYB-45 already satisfies criteria 1, 3 and 5 and half of 2.** A reference carries its target's identity, `Table.identifier` holds the other side of it, and a written reference now carries it too. What is missing is a lookup from identity to `Table`, one call that walks every reference, and the whole of criterion 4.
- **Retargeting is the reverse of moving.** A reference is a signed offset from the cell holding the formula, so a formula that moves needs no rewriting and a formula whose target moves does.
- Anchoring is recorded in two places for a range and in one for a single-cell reference, so a reader taking the sticky bits as authoritative reports every reference unlocked. That and the rest of what the format does here are in `findings-02-formulas.md`.

As a Python developer I want to insert and delete rows and columns so that a table can grow and shrink under script without breaking the formulas that point into it.

## Acceptance criteria

1. Adding and deleting a row or a column changes the table's declared row and column count and moves the cells beyond the insertion point.
2. Every formula reference that pointed past the insertion point still names the same cell afterward.
   1. A range whose far end lies past the insertion point moves only that end. `C3:C25` with a row inserted at 10 becomes `C3:C26` and never `C4:C26`.
   1. A reference wholly before the insertion point does not move at all.
3. Merges are carried: one spanning the insertion point grows, one wholly beyond it moves, and one wholly before it stays.
4. Deleting a row that a formula references leaves that reference broken the way Numbers leaves it, rather than silently repointing it at a neighbor.
5. Rows and columns hidden by the user keep their hidden state across the edit.
6. Each of the four operations is locked in by a golden file opened once in Numbers and confirmed correct.

## Constraints

- **A range moves one end and a retarget moves both**, which is the difference between this ticket and PYB-13. CLAUDE.md records a reference-shift regex that moved both ends of `C3:C25`, dropping rows from the start of every `SUMIFS` range it touched, and AC 2.i exists to catch exactly that.
- **Rows and columns are identified by UUID and the index map is a permutation.** `base_column_row_uids` gives a `TST.ColumnRowUIDMapArchive` whose `*_uid_for_index` is a permutation into `sorted_*_uids`, so reading the sorted list positionally names the wrong row.
- **`HeaderStorageBucket.hidingState` is not user hiding.** It reads 0 on hidden and visible alike across the whole corpus, and the hidden state lives in `TableModelArchive.hidden_states_owner`, keyed by those same UUIDs. See `findings-03-structure.md`.

As a Python developer I want to merge and unmerge a block of cells so that a table built by script carries the same merges it would have if a person had made them in Numbers.

1. Merging a range makes that block one cell anchored at its top-left, and `mergeCovering` reports the merge for every position the block occupies.
   1. The cells the merge swallows are removed from the table. A covered cell has no record in the file, so one left behind is written out as a cell Numbers never had.
   1. The anchor keeps its value and the covered cells lose theirs, permanently.
2. Unmerging returns the block to ordinary cells, and every position the merge covered reads as empty rather than as whatever it held before the merge.
3. Merging a range that overlaps an existing merge raises, rather than leaving two merges claiming the same cell.
4. Merging is refused for a range that is unbounded or that reaches outside the table's declared row and column count.
5. A document read, merged, saved and reopened shows the merge in Numbers, locked in by a golden file that was opened once in Numbers and confirmed correct.
6. A table with every merge removed reads back reporting no merges, and Numbers opens the saved file showing no merge and no repair prompt.

## SPEC

- **A merge is stored as a formula**, not as a flag on a cell. Each region is a complete `TSCE.FormulaArchive` in `TableModelArchive.merge_owner.formula_store.formulas[]`, structurally `SUM($A$1:$B$1)`: a colon-tract node with all four sticky bits true and a function node at index 168. Writing a merge means writing one of those.
- **Unmerging empties the store and keeps it.** Measured across `22-merge-2x2` and its unmerged twin `22b`: the merged table holds five formulas and the unmerged one holds zero, with `merge_owner` still present in both. Deleting `merge_owner` itself would produce something Numbers does not write.
- **Merging and unmerging do not change the declared grid.** Both twins report 2 rows by 13 columns.
- **Covered values do not come back.** Both twins hold the same 18 cells, and row 1 holds `A1`, `C1`, `E1`, `G1`, `I1`, `K1`, `L1` in each. `B1` and its fellows are absent from the unmerged file too, so the merge discarded them and unmerging restored nothing. AC 1.ii and AC 2 are that measurement rather than a choice.

As a Python developer I want to move a block of cells to another place in a table so that laying out a sheet by script does not mean rewriting every cell one at a time.

## Acceptance criteria

1. A range moves to a new anchor with its values, formulas and styles intact, and the positions it vacated read as empty afterward.
2. The caller names a `FormulaReferenceRelocation` for every reference the move touches, and a move naming none raises rather than choosing one.
   1. With `PRESERVE_NAMED_CELL`, each reference names the cell it named before, at that cell's new address when the cell moved with the block.
   1. With `PRESERVE_RELATIVE_POSITION`, each reference keeps its offset from the formula, and a `$` axis keeps its row or column.
3. Under `PRESERVE_NAMED_CELL`, a formula elsewhere in the document that pointed wholly into the moved block follows it. Under `PRESERVE_RELATIVE_POSITION`, it keeps naming the address it named.
4. Moving onto occupied cells raises rather than overwriting them silently.
5. A block containing whole merges carries them under either rule, leaving no merge behind, and one that would cut a merge in half is refused.
6. A destination reaching outside the table's declared row and column count is refused.
7. Each rule is locked in by its own golden file, opened once in Numbers and confirmed correct.
8. The move returns each cell whose formula names a position the block vacated, or covers only part of the block, so a value lost that way is reported rather than silent.

## Constraints

- **Preserving the named cell means rewriting offsets.** A reference is a signed offset from the cell holding the formula, so every reference leaving the block is rewritten. A `$` axis stores an index, so preserving the relative position rewrites nothing.
- **A covered cell has no record**, so a block overlapping a merge has holes in it that are not empty cells, which is why criterion 5 refuses a cut rather than moving what it finds.
- **Numbers performs both rules, measured in `60-move-*`.** Dragging a block is `PRESERVE_NAMED_CELL`, and cut and paste is `PRESERVE_RELATIVE_POSITION`, except that cut and paste leaves an empty merge behind. A range covering only part of the block stays put under both.
- PYB-118 follows this ticket and gives `formulaFill` the same argument.

As a Python developer I want to say, each time I fill a formula across a range, whether its references keep the cells they name or their position relative to the formula, so that a fill does what I meant rather than what a default assumed.

## Acceptance criteria

1. `formulaFill` requires a `FormulaReferenceRelocation`, and a call naming none raises rather than choosing one.
1. With `PRESERVE_RELATIVE_POSITION`, each filled cell names the cells at the offset from it that the source formula names from the source, and a `$` axis names the same row or column as the source.
1. With `PRESERVE_NAMED_CELL`, each filled cell names exactly the cells the source formula names.
1. Under either rule, positions a merge covers are skipped, and the count returned matches the cells filled.
1. Under either rule, a source holding no formula is refused and the table is left unchanged.
1. Each rule is locked in by its own golden file, opened once in Numbers and confirmed correct.

## Constraints

- **Blocked by PYB-18**, which introduces `FormulaReferenceRelocation`.
- A fill stores one formula that every filled cell points at, which is why preserving the relative position costs nothing. Preserving the named cell cannot share it, so each filled cell needs a formula of its own, and editing the shared one would retarget every cell at once.
- Row and column insertion and removal do not take the argument, because they relocate no block the caller chose.

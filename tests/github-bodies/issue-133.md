[PYB-18](https://github.com/rpulivella/pybers/issues/18)

`Table.cellsMove(source, anchor, references=...)` moves a block of cells to a new anchor with its values, formulas, styles, borders, highlighting and merges, and refuses an occupied destination, a cut merge or a destination outside the table. `references` takes a `FormulaReferenceRelocation` and has no default: `PRESERVE_NAMED_CELL` is Numbers' drag, and `PRESERVE_RELATIVE_POSITION` is its cut and paste, each measured in `60` to `62` and locked in by a golden confirmed in Numbers. The move returns every cell whose formula now reads a position it emptied.

## Detail your changes

- [x] Known issues remain (described below)
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Known issues

- Charts and table filters naming moved cells are not rewritten, since pybers models neither and no fixture holds one, with no ticket yet

## Preconditions / setup for testing
None

## Breaking Changes

**CI / automation / build**: None
**Object model (public dataclass fields)**: None. `Cell` gains two private fields, `_origin` and `_conditions`, excluded from equality and `repr`.
**Archive round-trip**: a range a formula reads past its table's edge is now registered with the engine up to that edge, as Numbers registers it, whether or not anything moved.

## Checklist (before requesting review)

- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change
- [x] I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

## Screenshot(s) / video(s)
None

_Closes #18_

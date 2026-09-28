[PYB-111](https://github.com/rpulivella/pybers/issues/111)

An expected-values file can now state a table's row and column count, the ranges it merges, and that a cell is empty, and golden-confirm checks each against Numbers. A closed Numbers is reported as not running rather than as a missing Automation grant. The nine goldens whose QA lines named merges, sizes or empty cells now check those lines, and only what needs eyes stays for QA.

## Detail your changes
- [x] Known issues remain (described below)
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
- The Data Format and capture-stream waits are unproven, as neither failure recurred in 24 runs
- A run that loses Numbers midway is untested

## Preconditions / setup for testing
1. `python3 scripts/golden-confirm.py helper-build`, since the helper source changed
2. Quit Numbers, then `python3 scripts/golden-confirm.py permissions` reports `numbersNotRunning`

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change
- NA I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

Nothing under `tests/` may import golden-confirm and no archive changed, so the three NA items cannot apply. Every changed golden passed a golden-confirm run in Numbers 15.3.1.

## Screenshot(s) / video(s)
None

_Closes #111_

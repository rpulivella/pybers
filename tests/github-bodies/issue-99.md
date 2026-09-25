[PYB-98](https://github.com/rpulivella/pybers/issues/98)

Every module-level function in `src/`, `tests/` and `scripts/` now opens its name with a verb, so a name reads as an action rather than as the value it returns. A new test fails the suite, and so the preflight, on any module-level function whose first word is not in its verb list, naming the file, line and function. `main` and pytest fixtures are exempt, since each is found by its name.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
None

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None
**Object model (public dataclass fields)**: None. Six public functions are renamed with no alias: `findFunction`, `findFunctionName`, `findFunctionNamed`, `findFunctionIndex`, `toColumnLetter` and `toColumnNumber`.
**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #98_

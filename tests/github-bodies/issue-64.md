[PYB-58](https://github.com/rpulivella/pybers/issues/58)

The package is laid out by concern: a directory per feature holding its model types and both of its archive halves, what more than one feature needs beneath them, and a leading underscore on anything a caller has no business reaching. Adding charting or pivot tables now adds a directory rather than editing four.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

Three fixes came out of measuring rather than reading.

**A caller could not write a correct `try` around `pybers.open`.** `ContainerError` escaped it on four failure modes out of five, from a package this branch made private, and was never exported. `PybersError` now roots all fifteen errors, each keeping the builtin base it had, so `except ValueError` still catches `ReferenceError`.

**The formula parser discarded the reason an address was refused**, saying `A0` "addresses nothing" where the addressing layer had said "names row 0, and rows count from 1". Row zero and column zero are the two mistakes a zero-based instinct makes, so the message has to name which.

**`_persistence/index.py` re-exported `ReadError` and `WriteError` by accident** after they moved out. Mypy caught it.

`pybers.model` is deleted rather than left forwarding names, since a shim that only re-exports is the compatibility layer CLAUDE.md rules out.

Two early commits do not pass alone: `716520d` staged renames without the import rewrites and `9d4a503` sits on it, with `7bec3a1` repairing both. Left as they happened. Every other commit was verified green individually.

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: None. The 53 exported names are unchanged apart from `PybersError`, `ReadError` and `WriteError` being added. **Archive round-trip**: None. Every golden file and every round trip passes untouched.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None. Nothing about a written document changed.

_Closes #58_

[PYB-48](https://github.com/rpulivella/pybers/issues/48)

A table wider than 255 columns did not open at all. Numbers stores such a row with one offset slot per column, counted in four-byte words rather than bytes, and pybers read `has_wide_offsets` as selecting a `uint32` instead. Reading the offsets that way put every one of them past the end of its own buffer, so the first row of the first tile raised.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: None **Archive round-trip**: None. `45-columns-over-255` writes back byte for byte, and the 46 earlier fixtures are unaffected.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #48_

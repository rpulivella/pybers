[PYB-53](https://github.com/rpulivella/pybers/issues/53)

A table of more than 255 columns counts its row offsets in four-byte words, and until now nothing had rewritten such a row from a real document: the two direct tests passed hand-built bytes, and the round trip never reached `rewriteRow` at all because it had no edits to write. This exercises the path end to end on `45-columns-over-255` and locks the result in as a golden file confirmed in Numbers.

The ticket asked which edit is even possible on that document, and the answer is a merge. A value write refuses because every cell is text, and a formula attach refuses because no dependency tile covers those columns, the second of which is now a test so that the day tile creation exists, it says so. Adding a merge drops the covered record, and the write then re-emits an offset in the wide unit for every one of the 295 records that remain, the three stored after column 295 having moved. The ticket's own SPEC has been corrected, because it claimed no edit was possible and PYB-49 had already made one possible.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: None **Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #53_

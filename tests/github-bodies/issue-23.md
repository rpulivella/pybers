## Ticket
Link: https://github.com/rpulivella/pybers/issues/2
Closes #2

Saving a document now writes back to a `.numbers` package, and setting a cell to a `Decimal` reaches the tile it came from. All six acceptance criteria are met, including the golden file, which was opened in Numbers 15.3.1 on 2026-09-01 and confirmed correct by eye.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: `Document` gained `_package` and `_sourcePath`. Both are private, defaulted, and excluded from equality and `repr`, so positional construction and comparison are unaffected. No public field changed, and `Document` gained `save`.

**Archive round-trip**: `pybers.archive` is now `pybers.numbersfile`. The word carried three meanings at once: one IWA object, which is 154 of its uses, the zip file itself, and the layer, so `pybers.archive.Archive` named the layer and the object with one word. `Archive`, `ArchiveInfo`, `ArchiveIndex` and `ArchiveMessage` keep their names, because those are Apple's own term for that object and renaming them would break the mapping to the protobuf schema. An unchanged document still writes back with every archive equivalent; a document with one numeric edit differs in exactly the tile holding it.

Reading a number also changed, and this one is a fix rather than a rename. `decodeDecimal128` used `scaleb`, which is an arithmetic operation and so obeyed the caller's thread-local `decimal` context. Under the default precision of 28 that rounded away the 34 digits decimal128 holds, and a caller who had set `prec=6` for their own arithmetic read 1234567.891 out of a file as 1.23457E+6, with nothing raising. No fixture caught it because the most precise value in the whole corpus has 15 digits. Values are now built from their digit tuple, which is exact and context-free, so a file's contents no longer depend on what the calling program happens to be doing.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

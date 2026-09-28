[PYB-109](https://github.com/rpulivella/pybers/issues/109)

Within one save, every archive now reads as it was last written, so a second pass over an archive keeps what the first pass wrote. One `ArchiveIndex` serves the whole save, creation included, and every write, addition and removal passes through it. Each archive resolves to one parsed message, and a read of an archive this save removed raises an error naming it.

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
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change
- NA I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

No golden is earned, since the change alters no file format and every existing golden passes unchanged.

## Screenshot(s) / video(s)
None

_Closes #109_

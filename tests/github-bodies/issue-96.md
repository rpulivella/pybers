[PYB-90](https://github.com/rpulivella/pybers/issues/90)

Sorts the 62 Numbers documents by origin: `tests/fixtures/` holds the control and the documents that came from outside, and `tests/measurements/` holds each document made from one of them by a single change. The findings move to `docs/findings/`. Tests reach any document through one lookup by stem, which fails where the old per-file helpers skipped, and every test helper now names a verb and a noun.

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
- NA Round-trip / golden-file tests pass for any archive-layer change

No archive-layer code changed. Some test names changed with the vocabulary, and the count is unchanged apart from two new lookup tests. Removing `measurements/` from the lookup stops the suite at collection, and 380 tests fail when collection continues, so a sweep cannot quietly check fewer documents.

## Screenshot(s) / video(s)
None

_Closes #90_

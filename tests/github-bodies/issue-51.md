[PYB-50](https://github.com/rpulivella/pybers/issues/50)

`pr.py` now checks a pull request body against the template before writing it. Six comparisons, all set differences on the template file itself, so nothing about a body's shape is hard-coded here. Ported from the same author's strikeglass repository rather than invented.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

Refused: an invented heading, a missing one, headings out of order, a line that is entirely bold and so reads as a heading while hiding from a `##` scan, a reworded checkbox label, and a body over twice the template's length. Ticking or deleting a checkbox is allowed, because the state is the author's and the label is the template's.

The word count strips HTML comments from both files first. Doing so revealed that every body merged into this repository has been over its real ceiling, PR #47 at 522 words against 386.

## Preconditions / setup for testing
None. `bodyFindings` is pure, so its thirteen tests need no token and no network.

## Breaking Changes
**CI / automation / build**: `.github/pull_request_template.md` becomes required to open a pull request. A missing template refuses rather than passing a body unchecked. **Object model (public dataclass fields)**: None **Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #50_

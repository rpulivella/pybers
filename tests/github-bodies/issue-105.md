[PYB-76](https://github.com/rpulivella/pybers/issues/76)

The last pull request on this ticket. `/pr-review-code` described CI as one preflight and told a reviewer to check the body against its template by hand, both of which the readiness check now does, so it points at the comment instead. This pull request is also where that comment is read in its finished form, rendered by the code on develop.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
None

## Preconditions / setup for testing
1. Read this pull request's comment: headings per check, a sentence naming each miss, and the commit it was checked against.
2. `preflight` and `readiness` both appear in the Checks view, each with its own verdict.

## Breaking Changes
**CI / automation / build**: None beyond the checks already on develop.
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change
- NA I created the goldens this change earns and confirmed each in Numbers (`/golden-confirm`)

The CHANGELOG entry landed in PR #101 and reaches this branch through develop. This change is one skill document, so no test covers it and no archive is touched.

## Screenshot(s) / video(s)
None.

_Closes #76._

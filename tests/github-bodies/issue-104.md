[PYB-76](https://github.com/rpulivella/pybers/issues/76)

`CONTRIBUTING.md` now names the two checks as GitHub shows them, `preflight` and `readiness`, and says what each one asks. This pull request was also the failure test: a checklist item left unticked sent the readiness check red while the preflight stayed green, and the annotation named the checklist. It also caught a real defect, a posting half that still ran every check and so asked GitHub for a permission it does not hold.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
None

## Preconditions / setup for testing
1. Read the Checks view: `preflight` green, `readiness` red, with an annotation naming the check that missed.
2. Read the comment, which should carry the new headings and sentences.

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

The CHANGELOG entry for this ticket landed in PR #101 and reaches this branch through develop. This change is documentation and a workflow fix, so no test covers it.

## Screenshot(s) / video(s)
None.

_Closes #76._

_Partial closure of PYB-76. Further pull requests will follow._

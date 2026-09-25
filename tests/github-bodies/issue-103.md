[PYB-76](https://github.com/rpulivella/pybers/issues/76)

The last pull request on this ticket, and the one that watches the whole cycle run. It renames every check so each reads as a heading, reports the CHANGELOG plainly, adds a check that every checklist item is ticked or marked NA, and asks the template for confirmed goldens. A deliberate failure on this branch proves that red blocks a merge, which is the one criterion no run has shown yet.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
None

## Preconditions / setup for testing
1. Read this pull request's own report comment, which is the first rendered as headings and sentences rather than a table.
2. `pr.py checks` should list a `merge readiness` check beside the preflight, on the head commit.

## Breaking Changes
**CI / automation / build**: None beyond the two checks PR #101 and PR #102 added.
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

The CHANGELOG entry for this ticket landed in PR #101 and reaches this branch through develop. This change reaches no archive and earns no golden.

## Screenshot(s) / video(s)
None.

_Closes #76._

_Partial closure of PYB-76. Further pull requests will follow._

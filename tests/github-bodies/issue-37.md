## Ticket
Link: https://github.com/rpulivella/pybers/issues/36
Closes #36

Adds `pr.py checks`, which reads the check runs on a pull request's head commit, and makes `pr.py merge` refuse any state other than passed. Until now nothing in this workflow read CI at all, so the run #5 added was a signal a human had to remember to look at. The refusal lives in the tool rather than in a skill, so it cannot be skipped by skipping a skill.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: `pr.py merge` gains a refusal. A pull request with a failing, pending, absent or unreadable CI state can no longer be merged through the tool. **Object model (public dataclass fields)**: None **Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

Both are NA because `scripts/` is repository tooling that pytest does not cover, and every path here is one live GitHub call. All four were exercised against real pull requests instead: a passing one, one whose head predates any workflow, a run still in progress, and the merge gate under `--dry-run`.

## Screenshot(s) / video(s)
None

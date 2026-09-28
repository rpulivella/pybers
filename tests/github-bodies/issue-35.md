## Ticket
Link: https://github.com/rpulivella/pybers/issues/5
Closes #5

Adds `.github/workflows/preflight.yml`, which installs the project on a runner and calls `scripts/pr-preflight-check.py` from #3, so the gate list stays in one place and this file names no gate of its own. A draft pull request skips the job and `ready_for_review` fires it at promotion, which keeps a branch covered without ever running on a commit that cannot merge. One job on one interpreter, read from `requires-python`, so #34 raises the floor without editing this file.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: new. Pull requests to `develop` run the four gates once they leave draft, and pushes to `develop` run them too. **Object model (public dataclass fields)**: None **Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

Both are NA because the deliverable is a workflow definition. Nothing here is importable, so pytest has no surface to cover, and what the workflow calls is already covered by #3.

## Screenshot(s) / video(s)
None

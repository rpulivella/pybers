[PYB-76](https://github.com/rpulivella/pybers/issues/76)

The second pull request on this ticket, and the first whose preflight can fire the readiness report, since a workflow_run workflow only runs from the copy on the default branch. It brings `README.md` and `CONTRIBUTING.md` current: what the two checks are, when they run, what a verdict means, and how a ticket carried by more than one pull request is closed. It carries whatever the first real report gets wrong.

## Detail your changes
- [x] Known issues remain (described below)
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
- The comment's wording is unproven until this pull request's own report appears, and refinements land here

## Preconditions / setup for testing
1. Read the report comment this pull request receives once it leaves draft, and confirm each check reads as its name promises.
2. `README.md` and `CONTRIBUTING.md` describe only what is built today, name no comment wording and no workflow internal, so nothing in them goes stale against the code that renders the report.

## Breaking Changes
**CI / automation / build**: None beyond PR #101, which added both checks.
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

## Checklist (before requesting review)
- [ ] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [ ] I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

The CHANGELOG entry for this ticket landed in PR #101 and reaches this branch through develop. The archive layer is untouched, so no golden applies.

## Screenshot(s) / video(s)
None.

_Closes #76._

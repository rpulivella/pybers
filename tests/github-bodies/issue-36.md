As a maintainer I want a merge refused while CI is not green, so that the workflow #5 added is read by the process rather than left for someone to remember to check.

1. `scripts/pr.py` gains one command reporting the CI state of a pull request's head commit, over the same explicit PAT and `urllib` path every other command there uses, with no `gh`, no `curl`, and no new dependency.
2. Three outcomes are distinguishable, the contract `find` already carries: every check passed, at least one has not, and the question could not be asked at all. Those are different facts and only the first means a merge is safe.
3. A pull request carrying no checks at all reports as not passed. An absent answer is never read as a green one.
4. It names each check and its conclusion, so a reader learns which check blocked a merge without opening the Actions tab.
5. `/pr-merge` refuses when the state is anything other than passed, alongside the dirty-tree and unpushed-commit refusals it already makes, and says which check blocked it.
6. `/pr-review-code` reports the state without gating on it, because it runs before promotion, when the run that matters has not started.
7. `scripts/README.md` lists the new command and the skills that call it, in the table that already maps every other one.

## SPEC

- **Actions runs live in the check-runs API, not in the legacy commit statuses API.** `GET /repos/{owner}/{repo}/commits/{ref}/check-runs` is the endpoint. The `/status` one returns an empty success for a repository whose only CI is Actions, which reads as passing and is the exact silent green AC 3 exists to prevent.
- **A skipped conclusion must count as passing.** Corrected 2026-09-03, having been written the other way round: promotion fires `ready_for_review` on the same commit the draft `synchronize` already ran, so the skipped run and the real run attach to one SHA. Reading skipped as a failure therefore leaves every promoted pull request permanently red, which the original claim that it "costs nothing" got exactly backwards.
- **Keep this small.** One command and two edits of a line or two each. The skills describe process and must not grow a second copy of the logic.

As a maintainer I want every deterministic check to run on GitHub and report one verdict on the pull request so that whether a change is ready for a person to test is visible without anyone running anything locally.

## Acceptance criteria

1. Both checks run on a pull request that has left draft, and neither runs nor comments while it is still a draft.
2. The first check runs the four preflight checks against the merge commit, and runs again on every push while the pull request is not a draft.
3. The second check waits for the first, reads its result, and adds the checks that exist only at pull request level:
   1. the body matches the template.
   2. the CHANGELOG carries an entry for this ticket.
   3. the ticket number agrees across the branch name, the commit subjects, the CHANGELOG line and the pull request title.
   4. the branch is current with `develop`.
   5. every dependency the change adds or alters carries no published advisory and is not yanked, checked against the version a fresh install resolves rather than the one declared, since this project declares floors and never pins.
   6. every golden file the change touches carries a confirmation date in `tests/golden/README.md`.
4. The second check posts one comment and replaces that same comment on every later run, finding it by a marker in its own body.
5. The comment carries one verdict. Red when any check failed, yellow when a person has to decide something, green otherwise. Green says a change is ready to be tested by a person and never says it is ready to merge.
6. A comment is posted when everything passes, because a report that appears only on failure cannot be told apart from a check that never ran.
7. Every check is named with its own result, and one that was skipped says so rather than being left out.
8. The comment records when it ran, because an advisory that does not exist today may exist next week against the same commit.
9. Red fails a required status check, so `pr.py merge` refuses on it without needing anything new.
10. The comment's structure is rendered by this repository's own code rather than composed freely at the time of writing.
11. The half that reads the branch has no write access, and the half that posts the comment runs no code from the branch.
12. All of it costs nothing beyond the minutes GitHub already includes.
13. `README.md` and `CONTRIBUTING.md` say that these checks exist, when they run, what each one asks and what a verdict means, and name no comment wording, marker or workflow internal, since a document that repeats what code renders goes stale against it.
14. Both files describe only what is built the day this lands: every claim either file makes about what the library and its gates do is true then, and one that has stopped being true is corrected rather than left standing.
15. A pull request body always carries its closing keyword, and one that is not the last for its ticket says so on its own line beneath it, since the keyword is what links a pull request to its ticket while it is open.
16. Whether a merge completes its ticket is decided at merge time and completes it by default. A merge that does not complete it leaves the ticket open at the Status it held, which is what a ticket spanning more than one pull request needs.
17. The two checks are two workflows, each reported under its own name, so a failing readiness never reads as a failing preflight.
18. Each check shows its phases where GitHub shows them: the preflight reports one step per gate, and the readiness check names every failure and every decision as an annotation, so which one missed is visible without opening a log.
19. A check that does not run says so where it would have reported, since a check absent from the list and a check that passed look identical.
20. The report's verdict is the readiness check's own result rather than anything written onto the commit afterward, and the posting half decides nothing.

## Constraints

Two facts from `home-assistant/core`, read on 2026-09-13 along with their pull request
181754. Each rules out the approach that looks obvious.

- **A workflow triggered by `pull_request` from a fork cannot post a comment**, having no write access by design. Theirs is two workflows for exactly this reason: a read-only one that runs the checks and writes `results.json` as an artifact while posting nothing, and a second triggered by `workflow_run` that reads that artifact and posts. Posting from the first is the obvious approach and it cannot work.
- **Their comment is rendered by their own code**, by `script/check_requirements/render.py`, which emits the whole thing carrying `{{CHECK_CELL:<package>:<kind>}}`, `{{CHECK_DETAIL:<package>:<kind>}}` and `{{SUMMARY}}` for something else to fill. That is what keeps a failure from producing a malformed report, and it is why AC 10 is worth its own line.

## Context / notes

Their marker is `<!-- requirements-check -->` in the comment body, under the heading `## Check requirements`, with verdicts as `✅`, `⚠️`, `❌` and `—` for skipped. Stage one triggers on `pull_request` types `opened`, `synchronize` and `reopened`, filtered by `paths`, and declares `permissions: {}`.

Their second stage runs a model, and this one does not. Nothing on the GitHub side of pybers runs one, because the review that needs judgment is interactive and belongs in the session. That is PYB-12, which waits on this ticket rather than the other way round, so this one lands first.

PYB-33 asks AC 3.v on a timer rather than at merge time. The two have to agree on one implementation rather than growing a second.

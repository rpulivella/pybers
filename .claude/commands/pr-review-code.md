---
description: Review an open pull request — run the deterministic preflight first, then review the changed files against the rubric, and take the PR out of draft only if everything is clean.
argument-hint: <optional PR number; inferred from the branch if omitted>
---

# /pr-review-code

The review half of the workflow, and **the only thing in this repository that takes a
pull request out of draft**. `/pr-draft` opens every PR as a draft and forbids any other
state, so draft-versus-ready stays a real signal.

This skill carries **process only**. The laws are in `CLAUDE.md`, and the review mindset
is in `.github/code-review-rubric.md`. Never restate either here.

**INERT until the GitHub repo exists, and `scripts/pr-preflight-check.py` still needs
authoring** (via `/script-write`) before step 2 below is real — see `CLAUDE.md` / the
handoff doc.

## Steps

1. Get the PR number from `$ARGUMENTS`, or from the current branch
   (`gh pr view --json number --jq .number`). If there is no PR, stop and say so.
2. **Run the preflight and stop if it fails:**
   ```
   python3 scripts/pr-preflight-check.py --pr <N>
   ```
   At minimum this runs `pytest` and checks the PR body against its template. Non-zero
   means **do not review**: report every failing stage and its reason verbatim, invoke no
   agent, and stop. Do not soften a machine reason into something friendlier. The one
   exception is a waiver — see below.
3. **Establish the scope**, which is the changed files and nothing else:
   ```
   git diff develop...HEAD --stat
   git diff develop...HEAD
   python3 scripts/ticket.py show <ticket>
   ```
4. **Review against the rubric.** Read `.github/code-review-rubric.md` and answer its six
   questions for this change. Delegate the parts that suit an agent, launched
   concurrently in one message, each given the file list from step 3 and told that
   anything outside it is out of scope.

   **Every agent is conditional — spend one only where the diff gives it something to
   find.** An agent costs roughly 50k tokens whatever it is handed, and one launched
   against a diff with nothing in its subject returns a confident "no issues" for that
   price. Read the diff first, then pick:
   - `pr-review-toolkit:pr-test-analyzer` — the rubric's Tests question. Always.
   - `pr-review-toolkit:code-reviewer` — house laws, checked against `CLAUDE.md`. Skip
     when the diff is predominantly comments or configuration.
   - `pr-review-toolkit:comment-analyzer` — only when the diff adds substantial
     documentation, and especially when a comment asserts something empirical.
   - `pr-review-toolkit:silent-failure-hunter` — only when the diff contains error
     handling, a fallback, a `catch`, or a broad `except`.
   - `pr-review-toolkit:type-design-analyzer` — only when the diff introduces a
     dataclass or other new type.

   One agent that fits beats four that overlap. Report the token cost of the ones you ran.
5. **Report**, separating what you verified by execution from what you only read. Name
   the commands you ran. State what could not be checked, rather than omitting it.
6. **Only on a green preflight with no unresolved finding**, promote it: `gh pr ready <N>`.

## Waiving a stage

A failing stage may be **waived**, and only when all three hold:

1. The failure is **provably outside the diff** — `git diff develop...HEAD --name-only`
   shows the change could not have caused it.
2. It is **already tracked by a ticket**, named in the waiver.
3. The waiver is **written into the pull request body**, so it is on the record rather
   than in someone's memory.

Never waive silently, never waive a stage the diff could have caused, and never waive
more than the one stage in question.

## Hard rules

- **Never review on a red preflight**, unless the failing stage is waived above.
- **The preflight is repository-wide; the review is diff-wide.** Never narrow the
  preflight to changed files, and never let the review wander outside them.
- **A recurring violation earns a lint rule, not a longer rubric.**
- Never reimplement what a `pr-review-toolkit` agent already does.
- Never merge from this skill.

## Merging

One command, watched, needing no ceremony. After a clean review:

```
gh pr merge <N> --merge --delete-branch --subject "[<N>] <prefix>: <summary>"
```

**Never `--squash`.** A branch carries genuinely separate concerns and each earned its
own commit on purpose; squashing destroys which change was which.

Pass `--subject` so the merge commit follows the house format rather than GitHub's
default. `Closes #<N>` in the body closes the issue.

$ARGUMENTS

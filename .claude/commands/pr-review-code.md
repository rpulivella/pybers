---
description: Review an open pull request. Run the gates first, then review the changed files against the rubric, and take the PR out of draft only if everything is clean.
argument-hint: <optional PR number; inferred from the branch if omitted>
---

# /pr-review-code

The review half of the workflow, and **the only thing in this repository that takes a
pull request out of draft**. `/pr-draft` opens every PR as a draft and forbids any other
state, so draft-versus-ready stays a real signal.

This skill carries **process only**. The laws are in `CLAUDE.md`, and the review mindset
is in `docs/code-review-rubric.md`. Never restate either here.

## What a review is today

**The four gates the preflight runs, and nothing else.** Agent delegation is suspended
until PYB-12 decides what replaces it, because this repository is going public and hosting
agentic review means the diff leaves this machine and every run bills. Step 5 below stands
as the shape to return to, not as an instruction to follow now.

`scripts/pr-preflight-check.py` runs pytest, the prose gate, ruff and mypy in one pass and
reports all four, so a failing run lists everything to fix rather than the first thing.

**It does not check the pull request body against its template.** That is a read you
perform yourself, and the report says so rather than implying the machine did it.

## Steps

1. Get the pull request from `$ARGUMENTS` (`PR #42`, `#42`, `42`, URL) or the branch
   (`python3 scripts/pr.py find --number-only`). **Read what it printed.** One of three
   things:
   - a bare number. That is the PR;
   - `no-open-pull-request`, there genuinely is none for this branch and base; stop and
     say so;
   - anything else, the question could not be asked at all (no credential, a 401, GitHub
     unreachable). Report *that*. It is a different claim from "there is no pull request",
     and reporting it as one states a fact you do not have.

   Exit codes carry the same three cases (`0`, `1`, `2`) for anything scripting this, but
   the printed output is the contract here. Do not depend on `$?`.
2. **Run the preflight and stop if it fails:**
   ```
   .venv/bin/python3 scripts/pr-preflight-check.py
   ```
   With the project venv, not the system interpreter, because pytest, ruff and mypy live
   there. Non-zero means **do not review**: report every failing gate and its reason
   verbatim, invoke no agent, and stop. Do not soften a machine reason into something
   friendlier. The one exception is a waiver. See below.
3. **Move the card, before reviewing anything:**
   ```
   python3 scripts/ticket.py status <ticket> --set "Code Review"
   ```
   Set when a review starts, not when it passes, so a review that stops on a finding
   still leaves the board saying what is happening. Re-setting it is harmless.

4. **Establish the scope**, which is the changed files and nothing else:
   ```
   git diff develop...HEAD --stat
   git diff develop...HEAD
   python3 scripts/ticket.py show <ticket>
   ```
5. **Review against the rubric.** Read `docs/code-review-rubric.md` and answer its six
   questions for this change, yourself. **The delegation below is suspended pending PYB-12**,
   and is kept because the selection rule it encodes is the part worth preserving, not
   because it should be run. Do not launch these agents without the user asking.

   Delegate the parts that suit an agent, launched
   concurrently in one message, each given the file list from step 4 and told that
   anything outside it is out of scope.

   **Every agent is conditional, spend one only where the diff gives it something to
   find.** An agent costs roughly 50k tokens whatever it is handed, and one launched
   against a diff with nothing in its subject returns a confident "no issues" for that
   price. Read the diff first, then pick:
   - `pr-review-toolkit:pr-test-analyzer`, the rubric's Tests question. Always.
   - `pr-review-toolkit:code-reviewer`, house laws, checked against `CLAUDE.md`. Skip
     when the diff is predominantly comments or configuration.
   - `pr-review-toolkit:comment-analyzer`, only when the diff adds substantial
     documentation, and especially when a comment asserts something empirical.
   - `pr-review-toolkit:silent-failure-hunter`, only when the diff contains error
     handling, a fallback, a `catch`, or a broad `except`.
   - `pr-review-toolkit:type-design-analyzer`, only when the diff introduces a
     dataclass or other new type.

   One agent that fits beats four that overlap. Report the token cost of the ones you ran.
6. **Read CI and report it, without gating on it:** `python3 scripts/pr.py checks <N>`.
   A review runs before promotion, so `checks-not-passed` is the ordinary answer here
   and is never a finding. `/pr-merge` is where it becomes a refusal.
7. **Report**, separating what you verified by execution from what you only read. Name
   the commands you ran. State what could not be checked, rather than omitting it.
8. **Only on green gates with no unresolved finding**, promote it:
   `python3 scripts/pr.py ready <N>`. Until PYB-3 lands, "green gates" means the two
   commands above run clean, and the report says that is what was run.

   Promotion is the review's outcome; step 3 is its beginning. What draft should mean
   once CI exists is unsettled and belongs to PYB-12.

## Waiving a stage

A failing stage may be **waived**, and only when all three hold:

1. The failure is **provably outside the diff**, `git diff develop...HEAD --name-only`
   shows the change could not have caused it.
2. It is **already tracked by a ticket**, named in the waiver.
3. The waiver is **written into the pull request body**, so it is on the record rather
   than in someone's memory. Write it with `/pr-draft edit <N>`, which owns the
   mechanism.

Never waive silently, never waive a stage the diff could have caused, and never waive
more than the one stage in question.

## Hard rules

- **Never review on a red gate**, unless the failing stage is waived above. A gate that
  does not exist yet is not a green one, and saying so in the report is the whole duty.
- **Never launch a review agent unless the user asks for one.** See PYB-12.
- **Never edit a body to make a finding go away.** Recording a waiver puts a fact on the
  record; rewriting a description until a gate reads green removes one.
- **The preflight is repository-wide; the review is diff-wide.** Never narrow the
  preflight to changed files, and never let the review wander outside them.
- **A recurring violation earns a lint rule, not a longer rubric.**
- Never reimplement what a `pr-review-toolkit` agent already does.
- Never merge from this skill.

## Merging

`/pr-merge`, which owns the command and the reasons behind it. This skill promotes a pull
request out of draft and stops there, and `pr.py` refuses to merge a draft, so step 8
cannot be skipped.

$ARGUMENTS

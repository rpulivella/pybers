As a maintainer I want the review in the session to stand in for a human code review so that a pull request reaches a person already read, and so that the reading is recorded where anyone can find it rather than living in a terminal.

## Acceptance criteria

1. `/pr-review-code` promotes the pull request out of draft as its first step, and refuses to promote when the local preflight is red.
2. Nothing comments on a draft. Leaving draft is the single act that permits automation to act on a pull request at all.
3. The review waits for the deterministic checks and reads their verdict. Red means it reports that and stops without reviewing, since reading code that does not pass is wasted.
4. The review reads the changed files against the ticket's acceptance criteria, `CLAUDE.md` and `.github/code-review-rubric.md`, which is the part no linter reaches.
5. A finding whose fix is unambiguous is fixed without asking, which pushes and runs the deterministic checks again. Anything else is raised in the session, because a review standing in for a human one is a conversation.
6. The review posts one comment on the pull request, in a format this repository defines, and replaces that same comment on a later run.
7. The comment states the depth the review ran at and how much of the change it read, both as values a reader can check rather than claims the tool makes about itself.
8. The comment separates what was verified by execution from what was only read, and names what could not be checked at all.
9. The review never runs anywhere but the machine the session is on.
10. What a review costs is knowable before it runs rather than after.
11. `/pr-review-code` describes only steps that exist. The suspended `pr-review-toolkit` delegation is either restored or removed, and no step remains that cannot be performed.
12. `CONTRIBUTING.md` describes the phases a change passes through, including that a golden file is confirmed by a person and by nothing else.

## Constraints

- **GitHub already posts an AI code review without the repository configuring anything.** Read on 2026-09-13: `home-assistant/core` has no `.github/skills/` directory, so the Copilot review on their pull request 181754 is the platform's rather than theirs, and they spend their own engineering on their dependency checks instead. Ours earns its place only by doing what that one cannot, which is reading a change against this ticket's acceptance criteria and against `CLAUDE.md`.
- **This review cannot be a workflow.** It fixes what it finds and discusses what it cannot, so it is interactive by nature. AC 9 follows from that rather than from privacy, and it survives the repository going public.

## Context / notes

Written for the phases agreed on 2026-09-13. Promotion, then the deterministic checks, then this review, then a person. PYB-76 owns those checks and lands first, since AC 3 waits on them.

Two decisions this replaces, recorded rather than dropped, since a line that was removed and a line that was considered and rejected look identical afterward.

The original asked whether the preflight script was the deterministic gate this sits on top of. PYB-3 settled it by shipping `scripts/pr-preflight-check.py`, which the first of the two checks now runs.

The original also asked that an external contributor be able to run the local half after `pip install -e ".[dev]"` and nothing more. That is no longer reachable and no longer wanted: this review is a Claude Code skill, so an outside contributor cannot run it at all. The deterministic checks serve them instead, and GitHub's own review is the free second opinion on an outside change.

Whether the outcome moves the Project board, and to what, is deliberately not specified here. A status meaning a change is ready for a person to test is wanted and is not being designed today.

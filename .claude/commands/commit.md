---
description: Stage and commit changes following pybers's mandatory commit format.
argument-hint: <optional message hint>
---

# /commit

Stage and commit following this repo's mandatory format. Grounded in the commit
convention shared across this developer's repos.

## Steps

1. Run `git branch --show-current`. **If the branch is `develop`**, the only thing that
   belongs there is a `[hotfix]`. Every ticket lands through a pull request from its own
   `<type>/<id>-slug` branch. If ticketed work is sitting on `develop`, ask before
   proceeding.
2. Run `git status` and `git diff` (staged + unstaged) to understand what changed. If
   there is nothing to commit, say so and stop.
3. Compose the message:
   - **`[<N>] <prefix>: <summary>`**, the ticket number first, in brackets, read from
     the branch name (`<label>/<N>-...`). The normal form. See `CONTRIBUTING.md`.
   - **`[hotfix]`** when there is genuinely no ticket, which in practice means a commit
     landing directly on `develop`: `[hotfix] <prefix>: …`. Use sparingly.
     **Being on a ticket branch settles it.** Work the ticket surfaced along the way is
     the ticket's, even when it touches tooling, a skill, CI or docs, and even when it
     was not in the acceptance criteria. It was discovered doing that work and belongs
     with it.
   - **`[init]`** for pre-ticket bootstrap (scaffolding, architecture de-risking, before
     the ticket workflow begins and before anything ships). **The default for this
     phase**, and it retires the day the first ticket-numbered commit lands. Filing a
     ticket does not retire it; landing work under one does.
   - **Single line only**, no body, no footer, nothing after the first line.
   - **A Conventional-Commits inspired prefix always:** `feat` `fix` `perf` `refactor`
     `style` `docs` `chore`. Those seven are the closed set, and **`test` is deliberately
     not among them**: it does not say whether a test was written or a test was run, and
     a prefix that needs the body to disambiguate it has failed at its one job. Writing,
     changing or deleting tests is `chore`. Chosen per commit, from what that commit did, never from
     the branch. A `feature/14-...` branch normally carries `feat:` several times and
     then `docs:`, `fix:` and `refactor:` as the work turns; that is correct, not drift.
     The branch prefix and the commit prefix are two different axes.
   - **≤ 60 characters** (aim 50), bracket included. Imperative mood ("add", "fix").
   - **No "Co-Authored-By", no footer, no second line.**
4. **STOP. Present the plan and wait for explicit approval.**
   ```
   Proposed commit message:
     <message>

   Files to stage:
     <list>
   ```
   Do not stage or commit until the user says yes. If they suggest a different message,
   update and re-present.
   **This gate is permanent.** Present the plan and get explicit approval every time,
   no branch, ticket, prior "always allow", or standing consent ever authorizes
   committing without asking.
5. Stage the relevant files **by name**. Never `git add -A` or `git add .` unless every
   untracked file is clearly intentional.
   **Never stage:**
   - `.env`, `.dev.vars`, `.claude/settings.local.json`, or anything with secrets
   - `.venv/`, `__pycache__/`, `*.egg-info/`, `dist/`, `build/`, `.pytest_cache/`
   - anything under `workarea/`, scratch space
   - (Note: `CLAUDE.md` **is** committed in this repo. Do commit it when it changes.)
6. Commit with inline `-m` only, **never a heredoc** (heredocs introduce
   Co-Authored-By footers):
   ```
   git commit -m "[<N>] prefix: description"
   ```
7. Run `git status` to confirm.
8. **Do not push automatically.** Ask first.

## Choosing the boundary

- **One acceptance criterion, one commit, at a minimum.** A hard criterion usually earns
  several: the type it needed, the behavior it added, a fix found while exercising it.
  One commit for a whole ticket is always wrong.
- **Small related changes may combine.** A message with "and" in it is fine; the
  one-line sixty-character limit already stops that going far.
- **Every commit's test suite is green.** No exceptions. "It passes once the next one
  lands" is not two commits, it is one.
- **Tests may trail the code they cover by a commit**, which is often the right shape
  after a large one. They may not trail the pull request.
- **Work a ticket surfaces gets its own commit, under that ticket's number.** It is not
  the ticket's deliverable and should not be buried inside a commit that is, but it is
  not ticketless either, and `[hotfix]` on a ticket branch is always wrong.

## Correct examples

```
[14] feat: decode merged cell ranges from the merge store
[27] perf: drop the per-tile allocation from the cell reader
[31] fix: keep run indices aligned across astral characters
[hotfix] docs: correct the install instructions
```

## Hard rules

- NEVER omit the bracketed id (except the literal `[hotfix]`).
- NEVER produce a multi-line message. NEVER add Co-Authored-By or any AI attribution.
- NEVER use `--no-verify`. NEVER push without asking.
- NEVER stage secrets, build artifacts, or `workarea/`.

$ARGUMENTS

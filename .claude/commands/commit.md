---
description: Stage and commit changes following pybers's mandatory commit format.
argument-hint: <optional message hint>
---

# /commit

Stage and commit following this repo's mandatory format. Grounded in the commit
convention shared across this developer's repos.

## Steps

1. Run `git branch --show-current`. **If the branch is `develop`**, routine work may
   commit directly there. Ticketed feature work should be on its own `<type>/<id>-slug`
   branch — if it is not, ask before proceeding.
2. Run `git status` and `git diff` (staged + unstaged) to understand what changed. If
   there is nothing to commit, say so and stop.
3. Compose the message:
   - **`[<N>] <prefix>: <summary>`** — the ticket number first, in brackets, read from
     the branch name (`<label>/<N>-...`). Only usable once GitHub Issues + `scripts/
     ticket.py` are wired up — see `CONTRIBUTING.md`.
   - **`[init]`** for pre-ticket bootstrap (scaffolding, architecture de-risking, before
     shipping): `[init] <prefix>: …`. **The default for this phase** — nothing has
     shipped, so nothing is a "fix".
   - **`[hotfix]`** for a ticketless fix **after shipping**, once the ticket workflow
     exists (tooling, a skill, CI). Not used during bootstrap.
   - **`[workarea]`** for a ticketless change confined to `workarea/`: `[workarea]
     chore: …`.
   - **Single line only** — no body, no footer, nothing after the first line.
   - **Conventional-Commits prefix required:** `feat` `fix` `perf` `refactor` `style`
     `docs` `chore`. Always include it, even when it matches the branch label.
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
   **This gate is permanent.** Present the plan and get explicit approval every time —
   no branch, ticket, prior "always allow", or standing consent ever authorizes
   committing without asking.
5. Stage the relevant files **by name**. Never `git add -A` or `git add .` unless every
   untracked file is clearly intentional.
   **Never stage:**
   - `.env`, `.dev.vars`, `.claude/settings.local.json`, or anything with secrets
   - `.venv/`, `__pycache__/`, `*.egg-info/`, `dist/`, `build/`, `.pytest_cache/`
   - anything under `workarea/` — scratch space
   - (Note: `CLAUDE.md` **is** committed in this repo — do commit it when it changes.)
6. Commit with inline `-m` only — **never a heredoc** (heredocs introduce
   Co-Authored-By footers):
   ```
   git commit -m "[<N>] prefix: description"
   ```
7. Run `git status` to confirm.
8. **Do not push automatically.** Ask first.

## Choosing the boundary

- **One acceptance criterion, one commit, at a minimum**, once tickets exist.
- **Small related changes may combine.** A message with "and" in it is fine; the
  one-line sixty-character limit already stops that going far.
- **Every commit's test suite is green.** No exceptions. "It passes once the next one
  lands" is not two commits, it is one.
- **Tests may trail the code they cover by a commit**, which is often the right shape
  after a large one.
- **Ticketless work interleaved with a ticket gets its own commit** — `[hotfix]` or
  `[workarea]` — even mid-branch.

## Correct examples

```
[init] chore: scaffold the project, package graph, and pytest gate
[init] feat: add the dataclass object model
[hotfix] docs: correct the install instructions
[workarea] chore: capture archive-format research
```

## Hard rules

- NEVER omit the bracketed id (except the literal `[hotfix]` / `[workarea]`).
- NEVER produce a multi-line message. NEVER add Co-Authored-By or any AI attribution.
- NEVER use `--no-verify`. NEVER push without asking.
- NEVER stage secrets, build artifacts, or `workarea/`.

$ARGUMENTS

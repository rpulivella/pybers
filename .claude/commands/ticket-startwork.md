---
description: Begin work on a ticket, fetch it, surface ACs + SPEC, branch, set Status In Progress, and load the acceptance criteria into the task list. No code written.
argument-hint: <issue number, #number, or issue URL>
---

# /ticket-startwork

Preparation only, **write no code in this skill.** It fetches the ticket, surfaces the
contract, opens the working branch, moves the Project card, and turns the ticket's
acceptance criteria into tasks.

## Steps

1. Get the issue number from `$ARGUMENTS` (`42`, `#42`, or the URL). If missing, ask.
2. Fetch it: `python3 scripts/ticket.py show <N>`.
3. Display to the user, exactly as written (do not paraphrase): title + label,
   acceptance criteria (preserve numbering/nesting), SPEC. Sub-criteria are an
   indented list of `1.` markers that GitHub renders `i.`, `ii.`, so cite `4.ii`.
   Tickets filed before 2026-09-02 carry the superseded `4.a` form; cite those as
   written.
4. **Branch.** Every ticket gets its own branch. First check for an existing one
   (`git branch -a | grep -E "/<N>-"`); if one exists, stop and tell the user.

   **Get current with `develop` before branching:**
   ```
   git checkout develop
   git pull origin develop
   ```
   The remote and branch are named rather than left to tracking configuration, which is
   how the same author's other start skill does it and why that one does not break. A
   bare `git pull` on a branch with no upstream prints an error, changes nothing, and
   leaves a stale base behind. **Read what the pull printed** rather than assuming it
   worked; branching from a stale `develop` earns a branch conflicts it never caused.

   Only then create `<type>/<N>-<kebab-title>` from it.

   **`<type>` is mapped from the ticket's label, not copied from it.** Two of the six
   read badly as a branch prefix, so:

   | label      | branch `<type>` |
   | ---------- | --------------- |
   | `feat`     | `feature`       |
   | `fix`      | `bugfix`        |
   | `perf`     | `perf`          |
   | `refactor` | `refactor`      |
   | `docs`     | `docs`          |
   | `chore`    | `chore`         |

   The commit inside still carries the Conventional prefix, so a `feature/12-...` branch
   holds `feat:` commits. Those are two different axes; see `CONTRIBUTING.md`.
5. **Set Status In Progress and assign:**
   ```
   python3 scripts/ticket.py start <N>
   ```
6. **Load the acceptance criteria into the task list** with `TaskCreate`, one task per
   AC, in the ticket's own numbering. The ACs are the contract, so they are the work. The
   SPEC is read for its constraints and never becomes tasks. Check `TaskList` first so a
   resumed session extends the existing list rather than duplicating it. Move exactly one
   task to `in_progress` at a time with `TaskUpdate`, and use `addBlockedBy` for an AC
   that genuinely cannot start yet. If a task wants subtasks, that AC is a ticket in
   disguise.

## Hard rules

- Write no code. Always fetch before acting; never guess ACs or SPEC.
- Branch from a current `develop`. Never guess the branch name, and never use the raw
  label as `<type>`; run it through the mapping in step 4.
- One task `in_progress` at a time.
- **Never hand-build a progress file.** The task tool is the dashboard; a markdown
  checklist under `workarea/` is not a substitute and goes stale the moment it is
  written.

## Moving the card afterward

The tool is the only sanctioned path. Never hand-run the GitHub API.

```
python3 scripts/ticket.py status <N> --set "Code Review"   # PR opened, awaiting review
python3 scripts/ticket.py close <N> --reason not-planned   # abandoned; Status -> Done, closed unplanned
```

Every one of these accepts `--dry-run`.

**Done is not one of them.** The Project's own `Pull request merged` and `Item closed`
workflows set it, server-side, the moment the pull request lands. Running `close --reason
completed` after a merge only restates what already happened. The Project workflows are
configured in its Workflows screen and are invisible from the repository, which is worth
knowing before concluding that some board behavior is unautomated.

## Project Status values

`Concept` (a human still has to think) · `Todo` (specified well enough to drive) ·
`In Progress` · `Code Review` (agentic review of an open PR) · `Done`.

A ticket whose spec proves inadequate goes **back to `Concept`**, which is why the board
has no separate blocked state.

$ARGUMENTS

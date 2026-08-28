---
description: Begin work on a ticket, fetch it, surface ACs + SPEC, branch, set Status In Progress, and load the SPEC into the task list. No code written.
argument-hint: <issue number, #number, or issue URL>
---

# /ticket-startwork

Preparation only, **write no code in this skill.** It fetches the ticket, surfaces the
contract, opens the working branch, moves the Project card, and turns the ticket's SPEC
steps into tasks.

## Steps

1. Get the issue number from `$ARGUMENTS` (`42`, `#42`, or the URL). If missing, ask.
2. Fetch it: `python3 scripts/ticket.py show <N>`.
3. Display to the user, exactly as written (do not paraphrase): title + label,
   acceptance criteria (preserve numbering/nesting), SPEC.
4. **Branch.** Every ticket gets its own branch. First check for an existing one
   (`git branch -a | grep -E "/<N>-"`); if one exists, stop and tell the user. Otherwise
   create `<type>/<N>-<kebab-title>` from an up-to-date `develop`.

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
   python3 scripts/ticket.py start <N> --assignee rpulivella
   ```
6. **Load the SPEC into the task list** with `TaskCreate`, one task per ordered SPEC
   step, each naming the AC it satisfies. Check `TaskList` first so a resumed session
   extends the existing list rather than duplicating it. Move exactly one task to
   `in_progress` at a time with `TaskUpdate`, and use `addBlockedBy` for a task that
   genuinely cannot start yet. If a task wants subtasks, it is a ticket in disguise.

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
python3 scripts/ticket.py status <N> --set "Code Review"   # PR opened, awaiting agentic review
python3 scripts/ticket.py close <N> --reason completed     # delivered; Status -> Done
python3 scripts/ticket.py close <N> --reason not-planned   # abandoned; Status -> Done, closed unplanned
```

Every one of these accepts `--dry-run`.

## Project Status values

`Concept` (a human still has to think) · `Todo` (specified well enough to drive) ·
`In Progress` · `Code Review` (agentic review of an open PR) · `Done`.

A ticket whose spec proves inadequate goes **back to `Concept`**, which is why the board
has no separate blocked state.

$ARGUMENTS

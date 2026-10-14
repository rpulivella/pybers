---
description: Begin work on a ticket, fetch it, surface ACs + constraints, branch, set Status In Progress, and write the acceptance criteria into workarea/dashboard.md. No code written.
argument-hint: <issue number, #number, or issue URL>
---

# /ticket-startwork

Preparation only, **write no code in this skill.** It fetches the ticket, surfaces the
contract, opens the working branch, moves the Project card, and writes the acceptance criteria
into `workarea/dashboard.md`.

## Steps

1. Get the ticket from `$ARGUMENTS`: `PYB-42`, `42`, `#42` or the URL. If missing, ask.
2. Fetch it: `.venv/bin/python3 -m tools.workflow.ticket show <N> --comments`. **Always the flag.**
   A ticket carries in its comments what the body cannot: why it was closed, what a
   review found, what a previous attempt settled. Starting without reading them
   repeats work already done.
3. Display to the user, exactly as written (do not paraphrase): title + label,
   acceptance criteria (preserve numbering/nesting), constraints. Sub-criteria are an
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
   The remote and branch are named rather than left to tracking configuration. A
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
   .venv/bin/python3 -m tools.workflow.ticket start <N>
   ```
   Then read `.venv/bin/python3 --version`. The work must use what that version adds in
   any code the ticket touches.
6. **Update the dashboard through `/dashboard-update`.** Replace the Tasks section with the new
   ticket's tasks, one per AC or step, the first `◼` if work begins now, and keep the
   queue. `ticket start` in step 5 has already put the ticket in focus. Show the user
   the file.

## Hard rules

- Write no code. Always fetch before acting; never guess ACs or constraints.
- Branch from a current `develop`. Never guess the branch name, and never use the raw
  label as `<type>`; run it through the mapping in step 4.

## Moving the card afterward

The tool is the only sanctioned path. Never hand-run the GitHub API without the user's
permission.

```
.venv/bin/python3 -m tools.workflow.ticket close <N> --reason not-planned   # abandoned; Status -> Done, closed unplanned
```

`--dry-run` is accepted here and everywhere else the tool is used.

**`Code Review` is not set from this skill**, which has exited long before a pull request
exists. `/pr-review-code` owns it and sets it when a review starts.

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

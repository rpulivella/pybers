---
description: Begin work on a ticket, fetch it, surface ACs + constraints, branch, set Status In Progress, and write the acceptance criteria into workarea/session-tasks.md. No code written.
argument-hint: <issue number, #number, or issue URL>
---

# /ticket-startwork

Preparation only, **write no code in this skill.** It fetches the ticket, surfaces the
contract, opens the working branch, moves the Project card, and writes the acceptance criteria
into `workarea/session-tasks.md`.

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
6. **Update `workarea/session-tasks.md` for the new ticket.** This file is the **literal
   replacement** for the removed Claude Code Task/Todo tool. Same purpose, same shape, only
   externalized to a text file so it survives `/clear` and window swaps. It holds what is active
   now and the queue of tickets that follows it. Tickets hold the full scope of work; this file
   is the current-moment slice.

   Read the current `workarea/session-tasks.md` (if it does not exist, treat it as empty). Then
   decide what carries forward into the new ticket's work:
   - **Compound, chained or epic case.** The new ticket references or blocks on current tasks
     (or belongs to the same epic). Carry those specific tasks forward by leaving their entries
     in the file.
   - **The queue stays.** Tickets the maintainer has lined up stay below the new ticket's
     tasks, in the maintainer's order, never cleared or reordered.

   Then REWRITE `workarea/session-tasks.md` (replace the file wholesale, never append). **The
   format is a flat dashboard: one line per task, no indentation, no headers, no dates, no
   notes, no prose.** It matches the visual language of the removed Task/Todo tool sidebar:

   ```
   ◼ <in-progress task subject>
   ◻ <pending task subject> › blocked by <blocker>
   ◻ <pending task subject> › blocked by <blocker>
   ◻ <pending task subject> › deferred
   ✔ <completed task subject>
   ✔ <completed task subject>
   ```

   Symbols (Unicode, single character each):
   - `◼` in progress (exactly one at a time)
   - `◻` pending
   - `✔` completed
   - `› blocked by X` inline notation, tail of the line
   - `› deferred` inline notation for a pending task not in the immediate chain

   **Flat only. No hierarchy, no indentation, ever.** Every task sits at column zero. There is
   no "parent" task that owns others. Order is natural priority: the `◼` at the top, pendings
   next, completed at the bottom. If a task feels like it needs subtasks, it is really a ticket
   in disguise, so file it as one and reference it by `PYB-` key.

   **Never multi-line an entry.** No status notes, no descriptions, no "as of" dates, no
   completed-earlier-this-session sections. Task subjects are terse, like commit messages. If a
   task needs context beyond one line, it belongs in its ticket, not in this file.

   `.vscode/settings.json` colors each status through the Highlight extension
   (`fabiospampinato.vscode-highlight`), so keep the symbols and the `›` notations exact.

7. Build the initial task list for the new ticket by writing entries to
   `workarea/session-tasks.md`. Each entry maps to a concrete AC or implementation step, cited
   in the ticket's own numbering (`PYB-52 AC 9.ii`, not `9.2`). Mark the first entry `◼` (in
   progress) if work begins immediately.
8. Display the resulting `workarea/session-tasks.md` contents to the user.

## Hard rules

- Write no code. Always fetch before acting; never guess ACs or constraints.
- Branch from a current `develop`. Never guess the branch name, and never use the raw
  label as `<type>`; run it through the mapping in step 4.
- One task `◼` at a time.
- **`workarea/session-tasks.md` is the only task dashboard.** Rewrite it the moment a task
  starts, finishes or becomes blocked, so it never trails the work.

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

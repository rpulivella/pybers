---
description: Keep the session dashboard, workarea/dashboard.md, current. Add, start, finish or block a task, set the ticket in focus, and sync the status line with its stage.
argument-hint: <add | start | finish | block | focus | sync> [task or ticket]
---

# /dashboard-update

`workarea/dashboard.md` is the only task dashboard. It survives `/clear` and a window swap, holds the current moment, and leaves the full scope to the tickets. Rewrite it the moment a task starts, finishes or becomes blocked, so it never trails the work.

## The shape

```
WiP · PYB-211: Give session tasks a status line, sections and a skill

## Tasks
◼ PYB-211 AC 2 tasks run in state order
◻ PYB-211 AC 3 the queue persists › blocked by PYB-157
✔ PYB-211 AC 1 status line and sections

## Tickets Queue
PYB-156 make the repository public
PYB-164 accept pull requests from anyone › blocked by PYB-156

## Tickets Recently Completed
PYB-193 merged as PR #210
```

- **The first line** is the ticket in focus, its stage code first, or `None`. `WiP` is in progress, `dPR` a draft pull request, `REV` a pull request in review, and `---` done or any other state. A ticket can be in focus before work starts.
- **Tasks** are the focused ticket's, one line each, citing its ACs in its own numbering (`PYB-52 AC 9.ii`). `◼` is in progress, exactly one at a time, `◻` is pending and `✔` is done, and they run in that order.
- **The queue** holds the maintainer's next tickets, in the maintainer's order, and persists across tickets and sessions. Never clear or reorder it.
- **Recently completed** holds the last twenty merges, newest first.
- `› blocked by X` and `› deferred` end a task or queue line. Only `› deferred` is typed; the blockers come from GitHub.
- One line per entry, at column zero, with no notes or dates. A task needing more than a line is a ticket.

The editor's highlighting keys on these markers, so keep them exact. Never type the first line or a `› blocked by` note: the commands below write both.

## What writes it

Only the command `.venv/bin/python3 -m tools.workflow.dashboard` writes the file, and only when a person or a skill runs it. No other command touches the dashboard. The workflow skills run it at the step where a ticket's stage changes:

- `sync` rewrites the first line for the ticket in focus, and rebuilds every queue line's `› blocked by` note from the blockers still open. Run it after editing the file, or whenever the first line names a ticket other than the checked-out branch's.
- `focus PYB-<N>` puts a ticket in focus off its branch, and `focus none` clears it.
- `merged PYB-<N> <pull request>` records a merge that completed its ticket, and clears the ticket's tasks and focus. A merge that leaves its ticket open is a `sync`, never a `merged`.

## Steps

1. **Edit the Tasks and Queue sections** for what changed: add a task, mark one `◼` or `✔`, or add `› deferred`.
2. **Run `sync`**, or `focus` when the ticket in focus changes off its branch.
3. Show the user the resulting file.

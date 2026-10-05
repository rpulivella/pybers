---
description: Revise a filed ticket's title, body, or label in this repo's exact format, without disturbing its Status or the AC numbering already referenced elsewhere.
argument-hint: <issue number> <what to change>
---

# /ticket-edit

Revise a ticket that is already filed. The body format is identical to `/ticket-create`.
Read that skill's [Body, exact order](ticket-create.md) section rather than restating it
here. This skill exists because a revision can break things a fresh filing cannot.

`edit` replaces the **whole** body. There is no partial update, so a revision always
means fetching the current body, changing part of it, and writing the whole thing back.

## Steps

1. Get the ticket from `$ARGUMENTS`: `PYB-42`, `42`, `#42` or the URL. If missing, ask.
2. **Pull the ticket fresh, immediately before drafting, every time, no exceptions.**
   `edit` replaces the WHOLE body and GitHub offers no conflict detection, so a revision
   drafted against a copy fetched earlier silently discards anything that changed in
   between. There is no error and no conflict marker; the other edit is simply gone. Never
   reuse an export from earlier in the session, and never work from a file you did not
   fetch in this step. "Pull first" as a habit is not enough, the window is small, and a
   rule that depends on a small window eventually loses.

   Three different reads, and using the wrong one is a silent corruption rather than an
   error:
   - `.venv/bin/python3 scripts/ticket.py show <N>`, to **read** it yourself. Rendered, wrapped,
     prefixed.
   - `.venv/bin/python3 scripts/ticket.py export-as-source <N> --body > "$TMPDIR/ticket-<N>-body.md"`
, to **edit**. The body as GitHub stores it, save a backslash ending each line GitHub
     shows as a break, which is what gets revised and written back.
   - `.venv/bin/python3 scripts/ticket.py export-as-source <N> --title`, whenever the revision
     keeps any part of the existing title. `show` prints it as `PYB-<N> <title>` and wraps
     at eighty columns, so a long title taken from there comes back with the number glued
     on and split across lines.

   **Never draft the revision from `show`.** It hard-wraps to the terminal width, expands
   tabs, and substitutes emoji shortcodes (`:warning:` becomes a glyph), so writing its
   output back silently reformats the whole ticket. No flag turns those off, which is why
   `export-as-source` exists as a separate command rather than a flag on this one.

   It does **not** eat `[bracketed]` words, `showTicket` escapes the title and prints the
   body with `markup=False`, so brackets survive. That fault was real once and was fixed;
   the warning about it outlived it. Corrected here so nobody re-derives a bug that is
   already gone.
3. Draft the revision. Preserve everything not being changed, **verbatim**, a revision
   that silently reflows the constraints or drops a section is a regression, not an
   edit.
4. **Run `/standards` on the revised draft, both passes, and fix what it finds.** `edit`
   replaces the WHOLE body, so an unproofread revision overwrites a clean one.
5. **Show the user what changes and wait for explicit approval.** This is the same
   spec-in touchpoint `/ticket-create` has; a revision re-opens it.
6. On approval, apply it:
   ```
   .venv/bin/python3 scripts/ticket.py edit <N> --body-file <draft>
   .venv/bin/python3 scripts/ticket.py edit <N> --title "<new title>"
   .venv/bin/python3 scripts/ticket.py edit <N> --label <label>
   ```
   Flags combine, and `--dry-run` previews any of them. `edit` reads the ticket back and
   verifies what landed against what was sent, so a write that lost a concurrent change
   fails loudly instead of passing silently.
7. **Delete the local copy as soon as the edit reports the write verified.** A ticket's
   contents live in the Project, never on disk. The lingering export is the actual hazard.
   It is a second source of truth that goes stale in minutes and is exactly what a later
   revision gets drafted against. Draft in `$TMPDIR`, never in the repository and not even
   under `workarea/`, and remove it once the verification line appears. Once step 5
   confirms the write landed, the local copy is provably redundant.
8. Report what changed.

## What a revision can break

- **Whether numbering is frozen depends on the ticket's Status, and nothing else.**
  Check the Status first; it decides which of these two applies.
  - **Concept or Todo, work has not begun.** Renumber, reorder, rewrite, split and
    delete freely. Nothing references these ACs yet, so the only goal is the clearest
    possible spec, and fixing a bad structure now beats carrying it forever.
  - **In Progress or later.** The number is the address. ACs are referenced from
    conversation, commits, and PR bodies ("AC 3 fails because…"), and that reference has
    to keep landing on the same requirement. **Rewriting an AC in place stays fine**,
    sharpening it, correcting it, folding a decision into it, as long as its number does
    not move and it still concerns the same thing. **Renumbering and reordering are
    forbidden**, because they silently redirect every reference that already exists. New
    ACs append at the end, even when the ordering comes out unnatural.
- **Inserting an AC mid-list renumbers everything after it**, which surprises people:
  markdown numbers an ordered list sequentially regardless of the literal digits written.
  Harmless before work starts. After it starts, that *is* the renumbering forbidden above.
- **Comments cite ACs by number, and renumbering silently redirects them.** An edit
  cannot damage a comment's content, so this matters only when the numbering moves.
  Read `ticket.py show <N> --comments` first when it will, and reword any citation
  the move breaks.
- **A dropped AC is struck through, never deleted.** Wrap it in `~~` and leave it where
  it is: `4. ~~The old requirement.~~` A deleted AC leaves every existing reference
  pointing at nothing, or worse, at whatever slid into its place.
- **Nesting is one level deep and labels never repeat.** `4.i` and `4.ii` under `4` are
  fine; a third level means the parent was really two tickets. A ticket already carrying
  the superseded `4.a` form keeps it, since renumbering orphans every reference to it.
- **The title is the branch slug, the PR title, and the CHANGELOG entry.** Retitling a
  ticket that is already `In Progress` orphans its branch name.
- **Dropping scope is a status change, not an edit.** A ticket whose spec turns out to be
  inadequate goes back to `Concept`, `.venv/bin/python3 scripts/ticket.py status <N> --set
  Concept`, and that is a deliberate signal that a human is needed again.

## Hard rules

- Never `edit` to move a ticket between statuses; that is `status` and `close`.
- Never draft from an export fetched before this invocation, and never keep one on disk
  after the edit verifies.
- **Once a ticket is `In Progress` or later:** never renumber or reorder existing
  acceptance criteria, and never delete one, strike it through and leave the number in
  place. Rewriting one in place is always allowed. Before work begins, none of this
  applies; see the Status gate above.
- Never use `[ ]` checkbox syntax in the ACs, numbered lists only.
- One label per issue.
- Never hand-run the GitHub API outside `scripts/ticket.py` without the user's permission.

$ARGUMENTS

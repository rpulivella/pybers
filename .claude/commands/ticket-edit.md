---
description: Revise a filed ticket's title, body, or label in this repo's exact format, without disturbing its Status or the AC numbering already referenced elsewhere.
argument-hint: <issue number> <what to change>
---

# /ticket-edit

Revise a ticket that is already filed. The body format is identical to `/ticket-create` —
read that skill's [Body — exact order](ticket-create.md) section rather than restating it
here. This skill exists because a revision can break things a fresh filing cannot.

**INERT until the GitHub repo and Project board exist** — see `CLAUDE.md` / the handoff
doc.

`edit` replaces the **whole** body. There is no partial update, so a revision always
means fetching the current body, changing part of it, and writing the whole thing back.

## Steps

1. Get the issue number from `$ARGUMENTS`. If missing, ask.
2. Fetch the current state. Two different reads, for two different purposes:
   - `python3 scripts/ticket.py show <N>` to *read* it yourself.
   - `python3 scripts/ticket.py export-as-source <N> --body > "$TMPDIR/ticket-<N>-body.md"` to get the
     body you will edit. **Never edit from `show`'s output** — it renders through rich,
     which reflows long lines, expands tabs, and substitutes emoji shortcodes, so writing
     it back silently reformats the whole ticket.
3. Draft the revision. Preserve everything not being changed, **verbatim** — a revision
   that silently reflows the SPEC or drops a section is a regression, not an edit.
4. **Show the user what changes and wait for explicit approval.** This is the same
   spec-in touchpoint `/ticket-create` has; a revision re-opens it.
5. On approval, apply it:
   ```
   python3 scripts/ticket.py edit <N> --body-file <draft>
   python3 scripts/ticket.py edit <N> --title "<new title>"
   python3 scripts/ticket.py edit <N> --label <label>
   ```
   Flags combine, and `--dry-run` previews any of them.
6. Report what changed.

## What a revision can break

- **The number is the address; the text is not.** ACs are referenced from conversation,
  commits, and PR bodies ("AC 3 fails because…"), and that reference has to keep landing
  on the same requirement. So **rewriting an AC in place is fine** — sharpening it,
  correcting it, folding a decision into it — as long as its number does not move and it
  still concerns the same thing. What is forbidden is **renumbering or reordering**,
  which silently redirects every reference that already exists. New ACs append at the
  end, even when the ordering comes out unnatural.
- **A dropped AC is struck through, never deleted.** Wrap it in `~~` and leave it where
  it is: `4. ~~The old requirement.~~` A deleted AC leaves every existing reference
  pointing at nothing, or worse, at whatever slid into its place.
- **Nesting is one level deep and labels never repeat.** `4.a` and `4.b` under `4` are
  fine; a third level means the parent was really two tickets.
- **The title is the branch slug, the PR title, and the CHANGELOG entry.** Retitling a
  ticket that is already `In Progress` orphans its branch name.
- **Dropping scope is a status change, not an edit.** A ticket whose spec turns out to be
  inadequate goes back to `Concept` — `python3 scripts/ticket.py status <N> --set
  Concept` — and that is a deliberate signal that a human is needed again.

## Hard rules

- Never `edit` to move a ticket between statuses; that is `status` and `close`.
- Never renumber or reorder existing acceptance criteria. Rewriting one in place is
  allowed.
- Never delete an acceptance criterion — strike it through and leave the number in
  place.
- Never use `[ ]` checkbox syntax in the ACs — numbered lists only.
- One label per issue.
- Never hand-run the GitHub API outside `scripts/ticket.py`.

$ARGUMENTS

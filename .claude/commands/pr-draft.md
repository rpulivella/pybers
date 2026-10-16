---
description: Create a draft pull request for the current ticket branch, or revise a filed one's body, filling the repo's mandatory PR template.
argument-hint: [edit] <optional issue number; inferred from the branch if omitted>
---

# /pr-draft

Create a **draft** pull request following this repo's mandatory PR format, or revise a
filed one. The PR is the **PR-out** touchpoint, both directions of it.

## Steps

1. `git branch --show-current`. Read the ticket number `<N>` from the branch
   (`<label>/<N>-...`).
2. `git log develop..HEAD --oneline` and `git diff develop...HEAD --stat` to understand
   the branch.
3. **Put the CHANGELOG entry in the PR, then push.** If the `## Unreleased` list has no
   line for this work, run `/changelog-add` and commit it. Then push (`git push`). The
   entry is `- [PYB-<N>] <title>` for ticketed work; `/changelog-add` also handles the
   ticketless case with `[init]` or `[hotfix]`, and a bare bullet is never correct.

   A golden row this branch confirms records the Numbers version, never asked for:
   `mdls -raw -name kMDItemVersion "$(mdfind 'kMDItemCFBundleIdentifier == com.apple.Numbers' | head -1)"`
4. Fetch the issue. The title is used **verbatim** in step 5, so read it verbatim:
   - `.venv/bin/python3 -m tools.workflow.ticket export-as-source <N> --title` for the title.
   - `.venv/bin/python3 -m tools.workflow.ticket show <N>` for the ACs, which you are reading, not copying.
5. **Read `.github/pull_request_template.md`** and fill it, writing the result to
   `$TMPDIR/pybers-pr-body-<N>.md`, the OS temp directory, which is per-user and cleaned
   by the system. **Never write a PR body inside the repository**, not even into
   `workarea/`; it is transient tool input, not scratch worth keeping. Rules:
   - **Title**: `[PYB-<N>] <issue title verbatim>`. Do not paraphrase.
   - **Ticket**: the body opens with `[PYB-<N>](url)` and ends with `_Closes #<N>_` in
     italic, the one place a `#` is correct since GitHub parses no other form.
   - **Intro**: 2-3 sentences on what the PR achieves.
   - **Detail your changes**: keep only the checkboxes that apply; remove the rest.
   - **Breaking Changes**: `None` after each heading, or a short list.
   - **Checklist**: check what is genuinely true. Unchecked means **not done**, so an
     item that cannot apply moves to the end of the list with `NA` in place of its
     checkbox. That records it as considered rather than skipped, which deleting it
     would lose. Say in the body why, when the reason is worth knowing.
     **Detail your changes** keeps its own rule and deletes instead, because its boxes
     are paired alternatives rather than obligations. One of each pair is asserted and
     the other is not a gap, so `NA` would be noise there.
6. **Run `/standards` on the body file, both passes, and fix what it finds.** A PR
   description is the durable record of why a change was made, and reviewers read it
   before they read the diff.
7. Create the PR as **draft**:
   ```
   .venv/bin/python3 -m tools.workflow.pr create --title "[PYB-<N>] <title>" --body-file "$TMPDIR/pybers-pr-body-<N>.md"
   ```
   Head is the checked-out branch and base is `develop`, both by default. `--dry-run`
   first prints the body without opening anything. Pass the body as a **file**. Never
   through a shell heredoc, which would mangle the backticks in every code span.
8. Run `.venv/bin/python3 -m tools.workflow.dashboard sync`, so the dashboard shows the draft.
9. Output the PR URL, which `pr.py` prints.

## Hard rules

- ALWAYS `--draft`. Never open a non-draft PR.
- NEVER add a section that is not in the template.
- **The finished body must not exceed twice the word count of the template it fills**
  (`wc -w` on both), because a reviewer needs what changed and what will bite them
  rather than an account of how it was found.
- **Never restate what the pull request page already displays**: GitHub lists every
  commit and its message alongside the body, so re-narrating them as prose or bullets
  duplicates data that then goes stale against the branch.
- **NEVER add "Co-Authored-By", "Generated with Claude Code", or any AI attribution in
  the PR body.**
- Base branch is always `develop`. Do not guess the description, fetch the issue first.
- **A draft may be opened at any point, including mid-work.** Green is required to
  *leave* draft, not to enter it, `/pr-review-code` enforces that. Being feature complete
  with tests still being written is exactly what draft is for. See
  [Open a Pull Request](../../CONTRIBUTING.md#3-open-a-pull-request) in `CONTRIBUTING.md` for the three conditions.

## `edit`: revising a filed body

`/pr-draft edit [<N>]` swaps steps 1 to 4 and 7 for the two commands below. **Steps 5 and 6
still govern**, so the template still decides what a body may say and `/standards` still
gates it.

```
.venv/bin/python3 -m tools.workflow.pr export-as-source <N> --body > "$TMPDIR/pybers-pr-body-<N>.md"
.venv/bin/python3 -m tools.workflow.pr edit <N> --body-file "$TMPDIR/pybers-pr-body-<N>.md"
```

Fetch immediately before drafting and never from memory: `edit` replaces the WHOLE body and
GitHub has no conflict detection, so anything that changed in between is discarded
silently. Same rule and same reasoning as `/ticket-edit`, which spells it out. Delete the
copy once the write reports verified.

## After approval

Review belongs to `/pr-review-code` and merging to `/pr-merge`. Do not do either from
here, and do not restate their instructions.

$ARGUMENTS

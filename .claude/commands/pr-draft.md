---
description: Create a draft pull request for the current ticket branch, filling the repo's mandatory PR template.
argument-hint: <optional issue number; inferred from the branch if omitted>
---

# /pr-draft

Create a **draft** pull request following this repo's mandatory PR format. The PR is the
**PR-out** touchpoint.

**INERT until the GitHub repo exists.**

## Steps

1. `git branch --show-current`. Read the ticket number `<N>` from the branch
   (`<label>/<N>-...`).
2. `git log develop..HEAD --oneline` and `git diff develop...HEAD --stat` to understand
   the branch.
3. **Put the CHANGELOG entry in the PR, then push.** If the `## Unreleased` list has no
   line for this work, run `/changelog-add` and commit it. Then push (`git push`). The
   entry is `- [#<N>] <title>` for ticketed work; `/changelog-add` also handles the
   ticketless case with `[init]` or `[hotfix]`, and a bare bullet is never correct.
4. Fetch the issue. The title is used **verbatim** in step 5, so read it verbatim:
   - `python3 scripts/ticket.py export-as-source <N> --title` for the title.
   - `python3 scripts/ticket.py show <N>` for the ACs, which you are reading, not copying.
5. **Read `.github/pull_request_template.md`** and fill it, writing the result to
   `$TMPDIR/pybers-pr-body-<N>.md`, the OS temp directory, which is per-user and cleaned
   by the system. **Never write a PR body inside the repository**, not even into
   `workarea/`; it is transient tool input, not scratch worth keeping. Rules:
   - **Title**: `[#<N>] <issue title verbatim>`. Do not paraphrase.
   - **Ticket**: the `Link:` line carries the issue URL, and `Closes #<N>` stays on its
     own line, that keyword is what closes the issue on merge.
   - **Intro**: 2-3 sentences on what the PR achieves.
   - **Detail your changes**: keep only the checkboxes that apply; remove the rest.
   - **Breaking Changes**: `None` after each heading, or a short list.
   - **Checklist**: check what is genuinely true.
6. **Run `/standards` on the body file, both passes, and fix what it finds.** A PR
   description is the durable record of why a change was made, and reviewers read it
   before they read the diff.
7. Create the PR as **draft**:
   ```
   python3 scripts/pr.py create --title "[#<N>] <title>" --body-file "$TMPDIR/pybers-pr-body-<N>.md"
   ```
   Head is the checked-out branch and base is `develop`, both by default. `--dry-run`
   first prints the body without opening anything. Pass the body as a **file**. Never
   through a shell heredoc, which would mangle the backticks in every code span.
8. Output the PR URL, which `pr.py` prints.

## Hard rules

- ALWAYS `--draft`. Never open a non-draft PR.
- NEVER add a section that is not in the template.
- **NEVER add "Co-Authored-By", "Generated with Claude Code", or any AI attribution in
  the PR body.**
- Base branch is always `develop`. Do not guess the description, fetch the issue first.
- **A draft may be opened at any point, including mid-work.** Green is required to
  *leave* draft, not to enter it, `/pr-review-code` enforces that.

## After approval

Merging belongs to `/pr-review-code`, which owns the command and the reasons behind it.
Do not merge from here, and do not restate its instruction.

$ARGUMENTS

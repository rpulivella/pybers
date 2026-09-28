As a developer finishing a ticket I want one skill that performs the merge so that the last
step of the workflow is owned rather than done by hand from instructions that forbid it.

1. `/pr-merge` exists and is the only skill that runs `scripts/pr.py merge`.
   1.a `/pr-review-code` keeps its prohibition on merging and loses its Merging section,
   which points at the new skill instead of holding the command it may not use.
   1.b `/pr-draft` points at `/pr-merge` rather than at `/pr-review-code`.
2. The skill refuses to merge when the branch has commits that are not pushed, or when the
   working tree is dirty, because either one merges a tree that differs from the one the
   author reviewed.
3. The merge subject is composed in the house format from the ticket, and GitHub's
   generated default is never accepted.
4. A real merge is what happens unless a squash is asked for, and a squash is reported with
   the reason it was chosen.
5. After the merge the skill gets `develop` current, naming the remote and the branch
   rather than relying on tracking configuration, and reads what the pull printed rather
   than assuming it worked.
6. The skill states that the board moves itself and runs no command to move it.
7. The skill adds no script: every action in it is `pr.py merge` or plain git.

## SPEC

- **The three lines that make this a defect rather than a wish.** `pr-draft.md:61` sends
  merging to `/pr-review-code`, `pr-review-code.md:114` says never merge from that skill,
  and `pr-review-code.md:121` holds the only `pr.py merge` invocation in the repository. No
  skill performs a merge, and the instructions for doing it sit inside the file forbidden
  to follow them.
- **Deleting the prohibition was the alternative and it is the worse one.** Merging is
  irreversible and outward-facing, and a review that can also merge is a review with a
  trigger on it. Keeping assessment and action in separate skills means a review can be
  re-run at any time without risk.
- **AC 5 exists because this failed for real on 2026-09-01.** A `git pull --ff-only` ran on
  a branch with no upstream, printed an error, was piped through `tail` and chained with
  `&&`, and the merge was reported complete while `develop` still sat at the commit before
  it. `/ticket-startwork` took the same correction the same day.
- **AC 6 exists because the opposite instruction was live until 2026-09-01.** The Project's
  `Pull request merged` workflow sets Status to Done server-side. Those workflows are
  configured in the Project and are invisible from the repository, which is what makes a
  stale `close --reason completed` easy to re-add.
- **No new script, and the reason is not laziness.** `pr.py merge` already carries
  `--subject`, `--method`, `--keep-branch` and `--dry-run`. The repository runs ten skills
  against four scripts, three ticket skills sharing `ticket.py`, and `/commit`,
  `/changelog-add` and `/script-write` correctly have none. The rule that holds is that
  anything touching an external system goes through a deterministic tool, not that each
  skill owns one.
- This is the complement of #3. That ticket is a skill whose script is missing; this one is
  a script capability with no skill to reach it.

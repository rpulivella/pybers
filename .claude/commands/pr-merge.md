---
description: Merge a reviewed pull request and get develop current. The only skill that runs pr.py merge.
argument-hint: <optional PR number; resolved from the current branch if omitted>
---

# /pr-merge

The last step of the workflow. `/pr-review-code` assesses and is forbidden to merge, and
this one acts. Keeping the two apart means a review can be re-run at any time without a
trigger sitting on it.

## Steps

1. **Resolve the pull request** from `$ARGUMENTS` (`PR #42`, `#42`, `42`, URL), or with
   `python3 scripts/pr.py find --number-only`. **Read what it printed.** A bare number
   is the PR, `no-open-pull-request` means there is none, and anything else means the
   question could not be asked at all. Those are three different facts, and only one of
   them is "no pull request".
2. **Refuse on an unclean state.** Run `git status --short --branch` and stop if either is
   true, saying which:
   - the working tree is dirty;
   - the branch is `ahead` of its remote.

   Both merge a tree that differs from the one that was reviewed. Neither is waivable:
   commit or push first, and re-run the review if the code changed.
3. **Compose the subject** in the house format from the ticket,
   `[<N>] <prefix>: <summary>`, by the same rules `/commit` states. `--subject` is
   required exactly so that GitHub's generated default never lands.
4. **Ask whether this merge completes the ticket**, and merge with the answer.
   ```
   python3 scripts/pr.py merge <N> --subject "[<N>] <prefix>: <summary>"
   python3 scripts/pr.py merge <N> --subject "..." --ticket-stays-open
   ```
   **Completing it is the default**, and the first form is the ordinary one. A ticket
   carried by more than one pull request takes the second: the body's closing keyword
   still closes the ticket, because that keyword is what links a pull request to its
   ticket, and the tool then reopens it and restores the Status it held. Ask the user
   rather than inferring it, because only they know whether more pull requests are coming.
   The source branch is deleted unless `--keep-branch` is passed. `pr.py` refuses a draft,
   so a pull request that never went through `/pr-review-code` cannot arrive here, and it
   refuses any CI state other than passed, including a state it could not read. Neither
   refusal is restated as a step here, because a check a skill performs is a check a
   skimmed skill skips.
5. **Get `develop` current, and read what the pull printed.**
   ```
   git checkout develop
   git pull origin develop
   ```
   The remote and the branch are named rather than left to tracking configuration. A pull
   that fails prints an error, changes nothing, and leaves a stale `develop` behind, so
   the merge looks complete when it is not. Confirm the merge commit is in `git log`
   rather than assuming it arrived.
6. **Purge that ticket's golden screenshots**, and only that ticket's:
   ```
   rm -rf workarea/golden-confirm/PYB-<N>
   ```
   `/golden-confirm` writes every report, screenshot and log for a ticket into that one
   folder, so a folder still present for a merged ticket is stale. Leave every other
   `PYB-` folder alone, because it belongs to work still open.
7. **Report** the merge commit, whether the branch was deleted, the state of `develop`,
   and whether a golden-confirm folder was purged.

## A real merge is the default

A branch usually carries genuinely separate concerns and each commit earned its place, so
squashing destroys which change was which. **`--method squash` is the exception**, and
it fits only when the branch is one logical change whose history is fixup churn rather
than separable steps. Say in the report why it was chosen.

## The board follows the ticket

The Project's `Item closed` workflow sets Status to Done server-side when the ticket
closes, so **run no command to move it**. `close --reason completed` after a merge only
restates what the keyword already did. The `Pull request merged` workflow is disabled
deliberately, because it moved a ticket to Done on the first of its pull requests.

Those workflows are configured in the Project and are invisible from the repository,
which is what makes a stale instruction here easy to re-add.

## Hard rules

- **Never merge a draft.** `/pr-review-code` promotes out of draft, and this skill merges.
- **Never merge with a dirty tree or unpushed commits.**
- **Never hand-run the GitHub API.** `pr.py merge` is the only sanctioned path.
- **Never move the board by hand after a merge.**
- Nothing here needs a script of its own. Every action is `pr.py merge` or plain git.

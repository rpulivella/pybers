As a maintainer I want every file carrying prose to reach the standards gate so that the pull request template and the review rubric are held to the rules they exist to state.

## Acceptance criteria

1. `.github` and `tools` are inside the default scope of `scripts/standards-check.py`.
2. Everything they hold passes the gate, or what does not is corrected in the same change.
3. A directory still excluded carries the reason beside its exclusion.

## Constraints

- `allRoots` omits both today, so `.github/pull_request_template.md` and `.github/code-review-rubric.md` have never been checked, and both are prose a contributor reads before anything else.

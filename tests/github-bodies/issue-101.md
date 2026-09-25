[PYB-76](https://github.com/rpulivella/pybers/issues/76)

Every deterministic check now runs on GitHub and reports one verdict as a single comment on the pull request, so whether a change is ready for a person to test is visible without anyone running anything locally. The preflight half runs on the branch with no write access and hands its facts over as an artifact. The reporting half runs this repository's own code, adds the checks only the API and the network can answer, and posts the comment.

## Detail your changes
- [x] Known issues remain (described below)
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
- The reporting half has never run on GitHub: a workflow_run workflow only fires from the copy on the default branch, and the dispatch endpoint refuses one that is not there either
- `README.md` and `CONTRIBUTING.md` are not updated yet, which AC 13 and AC 14 require before review

## Preconditions / setup for testing
1. `.venv/bin/python3 -m pytest tests/test_merge_readiness.py` covers the checks and the rendering without a token or a network.
2. `python3 scripts/merge-readiness.py collect --pull-request <N> --preflight-log <log> --output facts.json`, then `report --results facts.json --dry-run`, renders a report locally and posts nothing.
3. On GitHub, the comment appears once this pull request leaves draft, and is replaced rather than repeated on every later push.

## Breaking Changes
**CI / automation / build**: The preflight workflow now collects facts and uploads them, and a second workflow posts the report. Both run only on a pull request that has left draft.
**Object model (public dataclass fields)**: None
**Archive round-trip**: None

## Checklist (before requesting review)
- [ ] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

The archive layer is untouched, so no golden applies.

## Screenshot(s) / video(s)
None.

_Closes #76._
_The reporting half can only run once this lands on develop, so a second pull request on the same ticket exercises it and carries the documentation._

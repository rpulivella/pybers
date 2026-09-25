[PYB-70](https://github.com/rpulivella/pybers/issues/70)

Both repository tools gain commenting: add, read rendered or byte for byte, edit in place, and delete. Until now the only durable record a ticket could carry was its body and its Status, so a reason for closing, or what a review found, lived in a session nobody could read afterward.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None. Every command is new, and `show` gains an optional `--comments` flag that changes nothing when it is absent.

**Object model (public dataclass fields)**: None

**Archive round-trip**: None. Nothing here reads or writes a `.numbers` file.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] Round-trip / golden-file tests pass for any archive-layer change
- NA I added or updated pytest tests covering the change

**Why that item is NA.** Nothing under `scripts/` has tests, and inventing a pattern here would pre-empt PYB-11, which exists to decide what testing repo scripts should look like. Every criterion was instead exercised against live GitHub on this branch, including the failure paths: a missing body file, an id in no repository, and both dry runs. The first real use was closing PYB-66 with a comment pointing at the merge that fixed it, and that comment was later corrected in place.

## Screenshot(s) / video(s)
None

_Closes #70_

## Ticket
Link: https://github.com/rpulivella/pybers/issues/20
Closes #20

`/pr-merge` exists, and it is the only skill that runs `pr.py merge`. Until now no skill
performed a merge at all: `/pr-draft` sent merging to `/pr-review-code`, `/pr-review-code`
forbade itself from merging, and it held the repository's only `pr.py merge` invocation
inside the file that may not follow it. The step was done by hand from instructions that
said not to, twice in one day.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes

**CI / automation / build**: the workflow gains a step. A finished review no longer ends in
a merge command inside `/pr-review-code`, which loses that section and keeps its
prohibition, dropping from 140 lines to 125. `scripts/README.md`'s `pr.py` table is
corrected for three commands, one of which had been wrong since #19 merged.

**Object model (public dataclass fields)**: None.

**Archive round-trip**: None. This pull request does not touch `src/pybers`.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

The last two carry `NA` and sit at the end. An unchecked box would claim "not done", and
neither is able to apply: nothing here touches the archive layer, and this repository has
no test harness for its own scripts, which is #11, and a skill is markdown besides. What was verified instead was
run rather than read. `pr.py merge` appears in exactly one file now, the new skill invokes
only `pr.py find`, `pr.py merge` and four plain git commands, and the claim that `pr.py`
refuses a draft was checked against `cmdMerge` rather than repeated from the old text.

One fix rides along, in `scripts/standards-check.py`. The `UPDATES` entry added by #19 put
`\s+` inside a plain docstring, so every run of the gate emitted a `SyntaxWarning`. The
sentence is reworded rather than escaped, because it reads better without the regex in it.

## Screenshot(s) / video(s)
None

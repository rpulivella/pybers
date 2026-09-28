[PYB-61](https://github.com/rpulivella/pybers/issues/61)

A text cell holds a four-byte key into its table's pooled string list where a number holds sixteen bytes of decimal128, so writing text meant pooling it and changing a cell's type meant moving every reference behind it. Measuring what those references are turned out to be most of the work, and it answered the question `findings-09` left open on 2026-09-10. **AC 5 was rewritten on the ticket**, struck rather than replaced, because it asked that every reference survive and that turned out to render a sentence as a star rating.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: None. `Cell.value` already accepted a `str`,
and saving one no longer refuses.

**Archive round-trip**: a save now writes the pooled string list, and a cell whose type
changes has its format moved to the slot that kind uses, its control dropped, and its style kept. A record built for an empty cell borrows a sibling's shape and takes neither its control nor its chosen format. Reading a file and writing it back unedited is unchanged, and every existing golden still matches.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None. Confirmed in Numbers 15.3.1 on 2026-09-14 across four rounds, each of which found a defect no test here could: a pooled entry clobbered in a cell nobody wrote to, an inherited pop-up menu, a retained star rating, and an inherited format choice.

_Closes #61_

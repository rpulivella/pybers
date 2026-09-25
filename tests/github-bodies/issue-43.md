[PYB-41](https://github.com/rpulivella/pybers/issues/41)

A formula is now the postfix node array the file actually stores, rather than the string placeholder `Cell.formula` carried before. Reading resolves every reference against the cell holding it, writing a changed formula splits a pooled entry instead of overwriting it, and both goldens were confirmed in Numbers 15.3.1. Two facts underneath this were measured rather than read off the schema, and both would have failed silently: the formula key is trailing reference slot 0, established by reproducing every declared refcount in all nine tables that declare formulas, and `ASTStickyBits` never accompanies a single-cell reference, 0 of 21 in the corpus. The second corrected this ticket's SPEC and `findings-02-formulas.md`, which each stated a range-only rule as a general one, and AC 3 was rewritten in place for the reason given on the ticket.

## Detail your changes
- [x] No regressions / known issues found
- [x] Object-model shape changed (compatibility note in Breaking Changes below)
- [x] Archive round-trip behavior changed (new golden-file test attached)

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None

**Object model (public dataclass fields)**: `Cell.formula` changes from `str | None` to `Formula | None`. Nothing could have been reading a formula string, because nothing ever set one: the field was a placeholder for a text form this format does not have. `Cell` also gains `errored: bool`.

**Archive round-trip**: unchanged when nothing is edited, asserted at the archive bytes across all four formula fixtures. A changed formula rewrites its table's FORMULA list and marks the cell in `refs_to_dirty`, reusing what PYB-25 built. Editing one cell of a formula shared at refcount 2 splits the entry, so the sibling keeps what it had.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #41_

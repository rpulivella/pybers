## Ticket
Link: https://github.com/rpulivella/pybers/issues/19
Closes #19

`pr.py` gains `export-as-source`, matching `ticket.py`'s command of the same name down to
its flags, its handler and its emitters. `edit` replaces a whole pull request body and
GitHub offers no conflict detection, so revising one meant drafting from memory and
silently discarding whatever had changed in between. That hazard was hit twice in one day
while revising the body of pull request 15.

`/pr-draft` grows an `edit` argument to go with it, so filing a body and revising one are
two directions of a single skill rather than two skills. `/pr-review-code` points at it,
because a review is when a body gets edited and a waiver is only one of the reasons.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes

**CI / automation / build**: one read-only permission grant added,
`pr.py export-as-source`, matching the invocation as literal text the way the surrounding
grants require. Nothing removed.

**Object model (public dataclass fields)**: None.

**Archive round-trip**: None. This pull request does not touch `src/pybers`.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

The last two carry `NA` rather than an empty box, and sit at the end for it. An unchecked
box means not done, which would be the wrong claim: nothing here touches the archive layer,
so no round trip exists to run, and this repository has no test harness for its own
scripts, which is #11, so a pytest test of `pr.py` has nowhere to live. Marking them keeps
the record that both were considered, which deleting them would lose.

AC 2 was proved by running the round trip against pull request 15 instead: the body was
exported, sent straight back through `edit`, exported again and compared, and came back
identical at 3821 bytes. That is evidence rather than a test, and the body says which of
the two it is rather than hiding the difference behind a checkbox.

Two defects surfaced while writing this description, and both are fixed here. The template
had no rule at all for a checklist item that cannot apply, so one sat unchecked and read as
undone. It now moves to the end of its list carrying `NA`. And the standards gate
matched every banned phrase with literal spaces between the words, so any phrase a line
wrap fell inside passed in silence. At this repository's wrap width that is close to a coin
flip per occurrence, and a banned phrase reached an earlier draft of this body through it.

## Screenshot(s) / video(s)
None

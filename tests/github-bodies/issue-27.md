## Ticket
Link: https://github.com/rpulivella/pybers/issues/16
Closes #16

`Table.mergeAdd` and `Table.mergeRemove` merge a block of cells into one and take it apart again, and a document saved after either opens in Numbers showing what a person would have got by doing it by hand. A merge is written as the formula Numbers writes, the cells it swallows lose their records rather than being left behind as records Numbers never had, and unmerging empties the merge store rather than removing it.

Two things here were settled by measurement rather than by design. Merging is destructive and unmerging restores nothing, which is what the twin fixtures `22-merge-2x2` and `22b` show by holding the same eighteen cells. And merging changes what a formula reference means, so it is a recalculation event.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] Archive round-trip behavior changed (new golden-file test attached)

### A merge is a recalculation event, and the goldens are what found it

`findings-03-structure.md` already recorded that a reference to a covered cell is an error and recovers on unmerge: `L1` holds `=J1`, which is a type 8 error in `22` and a type 2 cell holding 0 in `22b`. What nobody had drawn from that is the consequence for a writer. The first pair of candidates wrote the merge store correctly and left `L1` holding the result it had before, so the merged file displayed 0 where an error belonged and the unmerged one displayed the error where 0 belonged.

Numbers does not notice on its own, for the same reason it does not notice an edited operand. The fix is the mechanism #25 built last: every position whose merge state changed goes into `refs_to_dirty`, and Numbers recomputes on open. Both directions are now confirmed on screen.

The strongest check available without Numbers had already passed at that point. Writing `22b`'s five merges reproduces `22`'s merge store exactly, and the document was still wrong, because the defect was in a cell the merge store says nothing about.

### The goldens keep a stale cell type on purpose

`22b-merged-by-pybers` holds `L1` as type 2 and `22-unmerged-by-pybers` holds it as type 8, which is the opposite of the fixture each was built from. That is correct: this library evaluates nothing, so each file carries the result Numbers last computed plus a dirty set asking for a fresh one. Reading a golden back through pybers shows the stale type; opening it in Numbers shows the right value. A test asserts the stale type so that nobody later "corrects" it.

### Renamed the writer's functions

Nine module-level functions in `writer.py` used a noun-plus-past-participle form, `rowRewritten`, `mergesApplied` and so on, which names a variable rather than a call and which CLAUDE.md does not license: module-level functions keep ordinary verb-first names. `reader.py` never had the problem. They are now `rewriteRow`, `applyMerges` and the rest, in a commit of their own so the rename is not mixed into the merge logic. `writer.py` also gained `__all__ = ["WriteError", "writeDocument"]`, since those are the only two names anything outside the module has ever imported.

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None.

**Object model (public dataclass fields)**: None. `Table` gained three methods and no type changed a field.

**Archive round-trip**: A save whose merges changed now rewrites the table model and drops the records of swallowed cells. A save whose merges did not change reaches none of it and stays byte-for-byte identical, which is its own test. The nine renamed functions were internal to `writer.py` and imported by nothing outside it.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

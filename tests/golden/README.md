# Golden files

A golden file is a `.numbers` package this library produced, **opened once in real
Numbers and confirmed correct by eye**, then committed so that any later change to the
writer that alters the output fails a test instead of shipping.

That confirmation step is what makes these worth having. Every other test in this
repository checks pybers against pybers, which can agree with itself while both halves
are wrong. Only Numbers itself can say that a file this library wrote is a file Numbers
considers valid.

## What is here

A golden lives here rather than under `tests/fixtures/` because it is not a fixture.
A fixture is input this library reads and was made by Numbers; a golden is output this
library wrote and Numbers accepted. Keeping them apart means nobody mistakes one for the
other when reaching for something to test against.

| File | Source fixture | Mutation | Confirmed |
| --- | --- | --- | --- |
| `11-value-types-noformats-A1-edited.numbers` | `11-value-types-noformats.numbers` | `A1` set to `Decimal("98765.4321")` | 2026-09-01, re-confirmed 2026-09-02 after PYB-25, Numbers 15.3.1 |
| `20-formula-shapes-multisheet-edited.numbers` | `20-formula-shapes.numbers` | every typed number in rows 1 to 10 raised by 1000, across three tables on two sheets | 2026-09-02, re-confirmed the same day after PYB-25, Numbers 15.3.1 |
| `22b-merged-by-pybers.numbers` | `22b-merge-2x2-unmerged.numbers` | five merges added across row 1 | 2026-09-02, Numbers 15.3.1 |
| `22-unmerged-by-pybers.numbers` | `22-merge-2x2.numbers` | all five merges removed | 2026-09-02, Numbers 15.3.1 |
| `18-formula-literals-A1-changed.numbers` | `18-formula-literals.numbers` | `A1` changed from `=1+1` to `=1+5` | 2026-09-03, Numbers 15.3.1 |
| `19-formula-dragged-F2-narrowed.numbers` | `19-formula-dragged.numbers` | `F2` narrowed from `SUM($B$1:$D$1)` to `SUM($B$1:$C$1)`, leaving `F3` on the archive they shared | 2026-09-03, Numbers 15.3.1 |

The multi-sheet golden exists because every other golden and every other edit test
covers one table on one sheet, which left `applyDocumentEdits` walking sheets and
filtering tables out of each drawable list with no confirmed file behind it. The
2026-09-02 confirmation settled that: both tabs are present, `Sheet 1 / Table 1` reads
1001 down to 1010, `Table 2` on that sheet reads 1042, `Sheet 2 / Table 1` reads 1053,
and the file opened with no warning and no repair prompt. Twelve edits across three
tables and two sheets each landed in the table they were addressed to. The copy that
was opened is not the copy committed here: autosave rewrote it on open, growing it by
1,574 bytes and renaming `Index/ViewState.iwa`, so it was discarded and the untouched
output was committed in its place.

**Both goldens were regenerated and re-confirmed on 2026-09-02 for PYB-25**, because the
writer's output changed: it now also marks the edited cells in the calculation engine.

That change came out of what the first multi-sheet confirmation found. Row 11 of
`Table 1` displayed 55, 56, 40, `big`, 110, 110, 42 and 53, the results those formulas
had cached BEFORE the edit, because **Numbers does not recalculate on open** and
patching a cell's value bytes leaves the calculation engine with no reason to know a
dependency moved. The regenerated file populates `refs_to_dirty`, and the second
confirmation shows row 11 reading 10055, 10056, 10055, `big`, 20110, 20110, 1042 and
1053.

**The value stored on disk for `A11` is still 55, and that is correct.** This library
never evaluates a formula. It names the cells that moved and Numbers does the
arithmetic, so reading the golden back through pybers shows 55 while opening it in
Numbers shows 10055. A test asserting the recalculated number against the file would be
asserting something the file does not contain.

The single-cell golden matters for the opposite reason: `11-value-types-noformats` has
no user formulas, and its re-confirmation checked that the checkbox, the three-star
rating, the slider at 50, the stepper at 1 and the popup menu all still render and still
work. That is where a too-eager dirty set would show as damage.

The 2026-09-01 confirmation checked more than the edited cell. Every interactive control
in the row survived: the checkbox, the three-star rating, the slider at 50, the stepper at
1 and the popup menu all render as they did before. Those are carried by the trailing
references on each cell record, so their survival is what proves the writer patched only
the sixteen value bytes rather than rebuilding the record.

The source fixture labels itself: row 2 describes what each cell of row 1 holds. After
the mutation `A2` still reads "plain number 1234.5" while `A1` holds 98765.4321, which is
deliberate. The stale label is how a reader confirms at a glance that the edit landed in
the right cell and that nothing else moved.

## The merge pair, and what it caught

`22b-merged-by-pybers` and `22-unmerged-by-pybers` run the twin fixtures through this
library in both directions: merges added to the file that had none, and every merge
removed from the file that had five. Each should end up looking like the twin it was
built from.

**The first attempt was wrong, and only Numbers could say so.** `L1` holds `=J1`, and
row 2 labels it "produces cell ref error". Merging `I1:J1` covers `J1` and makes that
reference invalid; unmerging makes it valid again. So a merge changes what a reference
means, which changes a result, and the first candidates carried the result from before
the change: the merged one displayed 0 where an error belonged and the unmerged one
displayed the error where 0 belonged. `findings-03-structure.md` had recorded that a
reference to a covered cell is an error and recovers on unmerge; what nobody had drawn
from it was that merging is therefore a recalculation event. The fix was the mechanism
PYB-25 had already built.

**Their stored cell types deliberately differ from the twins.** `L1` is type 2 in
`22-merge-2x2` and type 8 in `22b`, and these two hold the opposite, because this
library never evaluates a formula. Each carries the result Numbers last computed plus a
dirty set asking for a fresh one, so reading them back through pybers shows the stale
type while opening them in Numbers shows the right value. Do not "fix" that.

**They also carry a stale selection.** Numbers saves the last selected range in its view
state and pybers does not touch it, so each opens with whatever was selected when its
fixture was made. Cosmetic, and not a statement about anything.

## The formula pair, and what each one is for

Added 2026-09-03 for PYB-41, the first goldens covering a changed FORMULA rather
than a changed value.

`18-formula-literals-A1-changed` is the simple case: one literal inside an
unshared formula, with row 2's labels deliberately left stale so the edit is
visible by eye.

`19-formula-dragged-F2-narrowed` is the case that could fail silently. `F2` and
`F3` both hold `SUM($B$1:$D$1)` and, in the fixture, both display 6, because
Numbers stores ONE archive at refcount 2 and points both cells at it. Narrowing
`F2` alone therefore has to split that entry rather than overwrite it. Had it been
overwritten, one edit would have reached two cells, which is the same aliasing
defect the frozen model closes on the read side.

Neither cached value on disk changes, and that is correct: this library never
evaluates a formula. Each file names its changed cell in `refs_to_dirty` and
Numbers does the arithmetic, so reading them back through pybers shows the old
number while opening them in Numbers shows the new one.

**Both were confirmed on 2026-09-03 in Numbers 15.3.1**, and each showed more
than the edit itself.

`18` opened with no warning and no repair prompt. `A1` reads 6 against a label row
still saying `1+1`, and the rest of the row is untouched: `B1` 6, `C1` 6, `E1` 3,
`F1` 1 and `G1` `ab`. `D1` still shows the error triangle it always had, which
matters more than it looks. An error cell holds no value at all, so its formula
key sits at byte 12 where every other cell keeps a result, and a writer that
assumed a fixed offset would have corrupted exactly that cell and no other.

`19` confirmed the split from both sides, which the grid alone could not do.
Selecting `F2` shows `SUM($B$1:$C$1)` in the formula bar with two cells
highlighted and a result of 3; selecting `F3` shows `SUM($B$1:$D$1)` with three
cells highlighted and a result of 6. Every other cell is unmoved, including the
mixed-locking pair `G2` at 3 and `G3` at 2. Had the pooled entry been overwritten
instead of split, both would read 3 and both formula bars would say `$B$1:$C$1`.

## Confirming one

**Copy it somewhere else first, and open the copy.** Opening a `.numbers` file in
Numbers rewrites it. Confirmed on 2026-09-01: opening this golden renamed
`Index/ViewState-913882.iwa` to `Index/ViewState.iwa` and grew the package by 235 bytes,
because macOS document autosave saved it back with no edit and no prompt. Opening the
golden itself therefore destroys the very bytes being confirmed, and the file left behind
is Numbers' output rather than this library's.

Then open the copy. It must open with no warning and no repair prompt, the edited cell
must hold its new value, and every other cell must still match the description beneath it.
Record the date and the Numbers version in the table above.

Generation is deterministic, so a golden accidentally opened in place is restored by
regenerating it: the same source and the same edit produce byte-identical output, verified
on 2026-09-01.

**A golden file that has not been confirmed is not a golden file.** Until that row says
so, the test guarding it proves only that the writer is consistent with itself.

## Regenerating one

Deliberately not automated, because regenerating is how a bug gets locked in as the
expected answer. A golden is replaced only when the change to the output is intended, and
the replacement is confirmed in Numbers again before it lands.

```python
import shutil
from decimal import Decimal
from pathlib import Path
import pybers

source = Path("tests/fixtures/11-value-types-noformats.numbers")
golden = Path("tests/golden/11-value-types-noformats-A1-edited.numbers")
shutil.copy(source, golden)
document = pybers.open(golden)
document.sheets[0].tables[0].cell("A1").value = Decimal("98765.4321")
document.save()
```

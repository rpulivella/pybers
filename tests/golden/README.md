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
| `18-formula-attached-and-detached.numbers` | `18-formula-literals.numbers` | `=1+1` attached to `A2`, which held only the text label; `B1`'s `=2*3` detached | 2026-09-04, Numbers 15.3.1, re-confirmed the same day after the pool began sharing |
| `18-formula-created-in-empty-cell.numbers` | `18-formula-literals.numbers` | `=SUM(1,2,3)` written into `H1`, which had no cell record at all | 2026-09-04, Numbers 15.3.1, re-confirmed the same day after the pool began sharing |
| `20-formula-filled-across.numbers` | `20-formula-shapes.numbers` | `A11`'s `SUM(A1:A10)` filled across `A11:D11` | 2026-09-04, Numbers 15.3.1 |
| `22c-merged-by-pybers.numbers` | `22c-merge-overpaints.numbers` | `L3:M3` merged, dropping the style-only record `M3` carried | 2026-09-07, Numbers 15.3.1. **Superseded 2026-09-15**: regenerated for PYB-92, releasing the two styles the removed `M3` record named. Re-confirmed 2026-09-15, Numbers 15.3.1: `L3:M3` merged keeping row 3's fill, the other merges, row 5's overpaint and column D untouched, and `L1` still showing the reference error its label predicts |
| `45-merged-by-pybers.numbers` | `45-columns-over-255.numbers` | `KI7:KJ7` merged, rebuilding a 300-column row whose offsets count words | 2026-09-08, Numbers 15.3.1. **Superseded 2026-09-15**: regenerated for PYB-89, releasing the text format the removed `KJ7` record named. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers show `KI7:KJ7` merged holding `r6c295`, and every other cell of the 300 columns as before, `B7`, `E7` and `KM7` being empty in the fixture too. **Superseded again 2026-09-15**: regenerated for PYB-92, releasing the string `r6c296` the removed `KJ7` record named, and removing it. Re-confirmed 2026-09-15, Numbers 15.3.1: `KI7:KJ7` merged holding `r6c295`, row 7 otherwise as the fixture |
| `20-formula-authored-as-text.numbers` | `20-formula-shapes.numbers` | three formulas written as TEXT into `Sheet 1 / Table 2`: `B1` a cross-table reference with arithmetic, `C1` a nested lazy call, `D1` an anchored reference concatenated with a string | 2026-09-08, re-confirmed 2026-09-09 after the sticky-bits fix, Numbers 15.3.1 |
| `20-formula-brackets.numbers` | `20-formula-shapes.numbers` | four bracketed formulas written as text into `Sheet 1 / Table 2` row 1: `B1` a bracket precedence does not need, `C1` one it does, `D1` a bracket around a single value, `E1` one associativity alone forces | 2026-09-13, Numbers 15.3.1 |
| `11-text-written-and-retyped.numbers` | `11-value-types-noformats.numbers` | text written over a plain number at `A1` and again at `B1` so it pools once, text over a star-rating control at `F1` whose references were kept, a number over text at `A2`, and text into `J1` which had no record. The first golden to change a cell's type | 2026-09-14, Numbers 15.3.1, after four faults it caught: a clobbered pool entry, an inherited pop-up menu, a retained star rating, and an inherited format choice. **Superseded 2026-09-15**: regenerated for PYB-89, whose format list counts each cell, leaving the star-rating format at refcount 0. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers both show all ten cells, `J1` reads Automatic, and the checkbox, slider, stepper and pop-up menu keep their controls. **Superseded again 2026-09-15**: regenerated for PYB-89's AC 9, which removes the star-rating format entry rather than leaving it at 0. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers show all ten cells, and `F1` reads Automatic as text. **Superseded again 2026-09-15**: regenerated for PYB-92, removing the `plain number 1234.5` string once `A2` became a number. Re-confirmed 2026-09-15, Numbers 15.3.1: all ten cells as before, `A2` reading 98765.4321 Automatic, the slider and pop-up menu keeping their controls |
| `20-first-text-in-a-table.numbers` | `20-formula-shapes.numbers` | the first text in a table holding one number and no text at all, at `B1` and at `A3` in a row the file stored nothing for. A number record shapes it, since there is no string record to copy | 2026-09-14, Numbers 15.3.1, re-confirmed the same day once the text format entry reached the file. The first format entry this library created rather than found. **Superseded 2026-09-15**: regenerated for PYB-89, storing the displayed kind 5 where a key of 2 read as currency, and counting both text cells. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers show `B1` and `A3`, and both read Automatic |
| `20-formula-rows-created.numbers` | `20-formula-shapes.numbers` | four formulas written into `Sheet 1 / Table 2`, which stored one row of the ten it declares: `A3` and `C3` in one new row, `B7` in another, `E10` in the last row. The first golden whose tile rows this library built rather than edited | 2026-09-14, Numbers 15.3.1 |
| `20-formula-retargeted.numbers` | `20-formula-shapes.numbers` | eight anchored formulas written into row 10, then every reference into `Sheet 1 / Table 1` moved one row down and seven columns right, leaving the two that point elsewhere untouched | 2026-09-09, Numbers 15.3.1 |
| `20-sheets-added.numbers` | `20-formula-shapes.numbers` | an empty sheet `Inserted` added at position 2, between the sheet holding a cross-sheet formula and the sheet it reads, and `Appended` added last. The first golden whose archives this library created rather than edited | 2026-09-14, Numbers 15.3.1 |
| `20-tables-added.numbers` | `20-formula-shapes.numbers` | three tables created in the pybers reset: `Table 1` added beside a `Table 1` on `Sheet 1`, which becomes `Table 1-1`, with text at `A1` and 12.5 at `B2`; `table 2`, which becomes `table 2-1` because names clash regardless of case, with text at `C2`; and `Output` on a new sheet `Fresh`, with 1 at `A1` and text at `B5`. The first golden whose tables, styles and engine owners this library created | 2026-09-14, Numbers 15.3.1. **Superseded 2026-09-15**: regenerated for PYB-89, storing the displayed kind in four cells that held a format key instead. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers show all five created cells, and `A1` and `B2` of `Table 1-1`, `C2` of `table 2-1`, and `A1` and `B5` of `Output` all read Automatic |

`22c-merged-by-pybers` is the first golden where pybers REMOVED a record rather than
adding or changing one. A merge Numbers makes leaves nothing at a covered position, but a
merge imported from Excel leaves a style-only record at each, and pybers clears those when
it makes a merge of its own. That is a stricter cleanup than Numbers performs, so only
Numbers could say the result still opens. Confirmed 2026-09-07: no repair prompt, `L3:M3`
renders as one merged cell keeping row 3's fill, and the other thirteen merges, row 5's
overpaint and column D are all untouched. The copy that was opened is not the copy
committed here.

`20-formula-authored-as-text` is the first golden whose formulas were never read from a
file. Every earlier one copied, changed or moved a node array Numbers had written. These
three were built from text by `Cell.formulaText`, so none of them inherited archive bytes
to fall back on. That is what caught the cross-table identity being dropped:
`encodeFormulaReference` wrote the coordinates and left the table id to the bytes each node
was read with, which a node built from text does not have. `B1` read back as `A11*2+1`,
pointing at its own table, which is a plausible wrong answer rather than an error.

Confirmed 2026-09-08: no repair prompt, `Sheet 1 / Table 2` reads 42, **111**, **big** and
**42 units**, and the formula bar shows `Table 1::A11 x2+1`, `IF(SUM(A1:A10)>10,"big",
"small")` and `$A$1&" units"`. `Sheet 1 / Table 1` row 11 is untouched at 55, 56, 40, big,
110, 110, 42 and 53, and `Sheet 2 / Table 1` still reads 53. Quick Look shows the three
cells empty, which is the pair working as it should: Numbers recalculated on open because
the write named those cells as dirty, and Quick Look renders what is stored. The copy that
was opened is not the copy committed here.

**Numbers writes `Table 1::A11` where pybers writes `Sheet 1::Table 1::A11`.** Numbers
resolves a bare table name against the sheet the formula sits on; pybers qualifies because
two tables in this document are named `Table 1` and it has no notion of which sheet is
being read from. Both parse to the same nodes, and the file is identical either way, so
this is a difference in what the two choose to display rather than in what is stored.

`45-merged-by-pybers` is the only golden covering a row whose offsets count four-byte
words rather than bytes. Dropping the record at column 295 moves the three stored after it,
and the write re-emits an offset for every one of the 295 that remain. A unit confused for
a byte would place each of them a quarter of the way along the row, and raise nothing.
Confirmed 2026-09-08: no repair prompt, `KI7:KJ7` renders as one cell holding `r6c295`,
`KM7` is still the empty slot the fixture was built with, and rows 1 through 6 read
`col300` and `r5c300` at the far edge. The copy that was opened is not the copy committed
here.

`20-formula-retargeted` is the first golden that rewrote references rather than values,
merges or whole formulas. Eleven of the seventeen references in the document moved. Six
did not, and each of the six is a different reason: two point into other tables, and four
carry a locked axis.

**Row 10 was written for this golden because row 11 carries no anchored reference at
all.** The fixture's own row 11 is six formulas a person typed, none using a dollar sign,
so a retarget confirmed against row 11 alone would say nothing about locking. The eight
formulas below cover every combination of locked and free axis, once for a single cell and
once for a range, so which axis moved is legible in the result rather than inferred.

| cell | written as | after the retarget | should display | what it settles |
| --- | --- | --- | --- | --- |
| `A10` | `=$A$1*10` | `=$A$1*10` | 10 | both axes locked, nothing moves |
| `B10` | `=$A$3*2` | `=$A$3*2` | 6 | both axes locked, beside `C10` and `D10` |
| `C10` | `=A$3*2` | `=H$3*2` | 0 | free column moved, locked row did not |
| `D10` | `=$A3*2` | `=$A4*2` | 8 | locked column did not move, free row did |
| `E10` | `=SUM($A$1:$A$5)` | `=SUM($A$1:$A$5)` | 15 | a range locked on both axes |
| `F10` | `=SUM(A$1:A$5)` | `=SUM(H$1:H$5)` | 0 | a range whose columns move and whose rows do not |
| `G10` | `=SUM($A1:$A5)` | `=SUM($A2:$A6)` | 20 | a range whose rows move, both ends together |
| `H10` | `=$A$4` | `=$A$4` | 4 | locked, and it lands inside the ranges row 11 now covers |

`C10` and `D10` are the pair that matters most. They differ by one dollar sign, they
must disagree after the move, and an implementation that moved a locked axis would change
exactly one of them while the other three still passed.

Row 11 is the fixture's own six formulas plus the two cross-table ones. Column A holds 1
through 10, and column H is empty except for `H10`, which is now 4, `H11`, which holds 53
from its own cross-sheet formula, and `H12`, which holds the label text describing row 11.
So row 11 should read **57, 58, 53, small, an error, 57, 42 and 53**, where the fixture
read 55, 56, 40, big, 110, 110, 42 and 53. `SUM` ignores text, which is why `H12` leaves
`A11` and `F11` at 57 rather than failing them.

Quick Look should show the OLD numbers in row 11, and row 10 empty except for `A10` at 10.
Everything pybers wrote is a formula with no result, since this library evaluates nothing,
so the two views disagreeing is the pair working rather than a fault.

**The first 2026-09-09 confirmation of this file found a defect, and the file was rebuilt.**
All sixteen values matched, and every single-cell reference showed the dollar signs it
should: `$A$1`, `H$3`, `$A4`, `$A$4`. The three ranges did not. `E10`, `F10` and `G10`
displayed as `SUM(A1:A5)`, `SUM(H1:H5)` and `SUM(A2:A6)` where pybers renders
`$A$1:$A$5`, `H$1:H$5` and `$A2:$A6`.

That was first written up here as a Numbers display convention, which was wrong.

**A range records its anchoring twice, and Numbers believes the second copy.** The tract
field variant carries it, and an `ASTStickyBits` message beside the tract repeats it. All
9 ranges in the corpus carry those bits and none is without them. pybers patches the bytes
a node was read with, so a range read from a file kept its bits and a range built from
text had none at all, and absent bits read as unanchored. The tract said absolute, the
bits said relative, and Numbers showed what the bits said.

The single-cell references were unaffected, which is why nothing caught this earlier: a
single-cell reference carries anchoring only on its coordinates and never carries sticky
bits, measured across all 21 in the corpus. The first anchored range pybers ever authored
is the one written for this golden.

`encodeStickyBits` now writes them from the same `Span.absolute` the tract comes from, so
the two cannot disagree.

**Confirmed 2026-09-09 after the fix, and the before and after settle it.** The same three
cells that displayed as `SUM(A1:A5)` and `SUM(H1:H5)` now display as `SUM($A$1:$A$5)` and
`SUM(H$1:H$5)`, from files whose tracts never changed. Nothing but the sticky bits moved
between the two runs, so the bits are what Numbers reads. Row 10 reads 10, 6, 0, 8, 15, 0,
20 and 4, row 11 reads 57, 58, 53, small, an error, 57, 42 and 53, and Quick Look holds
row 11 at the fixture's old 55, 56, 40, big, 110, 110, 42 and 53. Thirteen views were
read: eight formula bars, the grid, the sheet list and Quick Look. `G10` was the one
anchored cell not photographed. The copy that was opened is not the copy committed here.

`20-formula-authored-as-text` was regenerated for the same reason and re-confirmed the
same day: `Sheet 1 / Table 2` reads 42, 111, big and 42 units, `C1` shows
`IF(SUM(A1:A10)>10,"big","small")` with column A highlighted, and `Table 1` row 11 is
untouched at 55, 56, 40, big, 110, 110, 42 and 53. Its `C1` holds a relative range, whose
missing bits happened to read correctly as relative, so the 2026-09-08 confirmation was
sound and only its bytes changed.

**`E11` evaluating to an error is the retarget being obeyed, not a fault.** `=A11*2`
became `=H12*2`, and `H12` is text, so multiplying it by two fails in Numbers as it would
anywhere. A reference landing somewhere awkward is what a caller asked for when they moved
it. Refusing would mean knowing the target grid, and refusing partway through a walk is
what leaves a document half retargeted.

**An earlier confirmation of this golden was discarded rather than kept.** The expectation
written here before it said `E11` would read zero, which assumed column H was empty below
row 11 without reading row 12. The file was correct and the prediction was not, and a
golden checked against a wrong expectation confirms nothing, so the file was remade from
the fixture and every number above was derived from the cells it depends on.

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

## The attach and detach golden, and the two-register finding

`A2` held the text `1+1` as a label and no formula; it now carries `=1+1` and displays
**2**. `B1` held `=2*3` and now holds a plain **6** with an empty formula bar.

**This golden took three attempts, and the first two are the reason it exists.** The
calculation engine keeps its own register of which cells hold formulas, and setting the
record's formula flag and pooling the archive is necessary but not sufficient.

- Attempt one updated neither register. `A2` stayed as text and Numbers never knew a
  formula was there.
- Attempt two updated `cell_dependencies` only. Selecting `A2` then showed
  `Formula 1+1` in the footer while the cell still displayed `1+1`, which is the most
  misleading state available: correct to anyone who clicks it, never evaluated.
- Attempt three updated `tiled_cell_dependencies` as well. The register is stored
  TWICE, and both copies have to agree.

`B1` also shows why a pass is not a pass. Attempt two rendered `B1` correctly while the
register still claimed it held a formula, so the detach half looked confirmed while
leaving the document lying about itself.

## The fill golden, and why two others were regenerated

Added 2026-09-04 for PYB-42's AC 4. `A11` holds `SUM(A1:A10)` and was filled across
`A11:D11`. Each cell must resolve against its own column, so `B11` reads `SUM(B1:B10)`
and `D11` reads `SUM(D1:D10)`, **and the file must hold ONE formula rather than four**.
It does: one entry at refcount 4, with the three entries those cells used before
released. That is what dragging does in Numbers, reproduced by doing the same thing
rather than by simulating it.

**Making that true changed the writer, which invalidated two confirmed goldens.** The
pool now shares an identical formula instead of storing a second copy, so attaching
`=1+1` to `A2` reuses `A1`'s entry and writing `SUM(1,2,3)` into `H1` reuses `C1`'s.
Both files became byte-different from the versions confirmed earlier the same day, so
neither confirmation carried over and both were opened again.

**Read the fill golden through its formula bars, not its numbers.** `B11`, `C11` and
`D11` all display 0, and 0 is right: columns B, C and D of that table are empty, so
`SUM(B1:B10)` is genuinely zero. What proves the fill is that selecting each cell shows a
DIFFERENT range, `SUM(B1:B10)` against `SUM(C1:C10)`, from one stored formula. `D11` is
worth a look too: it held a text result (`big`) before the fill and holds a number after,
a third independent confirmation that Numbers repairs a record type it disagrees with.
Every cell outside the filled range is untouched, including the cross-table `Table 2::A1`
and cross-sheet `Sheet 2::Table 1::A1` references.

## Confirming one

**Copy it somewhere else first, and open the copy.** Opening a `.numbers` file in
Numbers MAY rewrite it, and whether it does is not predictable. Observed on 2026-09-01:
opening a golden renamed `Index/ViewState-913882.iwa` to `Index/ViewState.iwa` and grew
the package by 235 bytes, because macOS document autosave saved it back with no edit and
no prompt. Observed on 2026-09-04, opening a workarea copy left its modification time
untouched, so autosave did not fire. **Both happened, and that is exactly why the copy is
not optional**: a rule that holds only sometimes cannot be relied on in the direction that
loses the bytes being confirmed.

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

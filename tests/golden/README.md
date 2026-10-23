# Golden files

A golden file is a `.numbers` package this library wrote, **confirmed in real Numbers**,
then committed so that any later change to the writer that alters the output fails a test
instead of shipping.

That confirmation is what makes these worth having. Every other test in this repository
checks pybers against pybers, which can agree with itself while both halves are wrong.
Only Numbers can say that a file this library wrote is a file Numbers considers valid.

## What is here

Numbers makes fixtures and measurements, and pybers makes goldens, so nothing Numbers
made lives here. A golden starts from a document Numbers made, a fixture or a measurement,
because pybers opens a document rather than creating one. Whatever pybers writes is a
golden and never a measurement, since a measurement is evidence of what Numbers does.

Every golden is built by its builder in [`builders.py`](builders.py), the one place its
construction is written down: the document it starts from and the mutation pybers writes.
A golden starting from a measurement laid out with each value in row 1 and its label in
row 2 has the label beneath every cell it changed rewritten to say what pybers wrote and
over what, and `test_goldens.py` fails when a label no longer says so.

| File | Built from | Mutation | Confirmed |
| --- | --- | --- | --- |
| `11-value-types-noformats-A1-edited.numbers` | `90f-number-for-an-edit` | `A1` set to `Decimal("98765.4321")` over the number 1234.5, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `A1` reading 98765.4321 |
| `20-formula-shapes-multisheet-edited.numbers` | `20-formula-shapes.numbers` | every typed number in rows 1 to 10 raised by 1000, across three tables on two sheets | 2026-09-02, re-confirmed the same day after PYB-25, Numbers 15.3.1 |
| `22b-merged-by-pybers.numbers` | `22b-merge-2x2-unmerged.numbers` | five merges added across row 1 | 2026-09-02, Numbers 15.3.1 |
| `22-unmerged-by-pybers.numbers` | `22-merge-2x2.numbers` | all five merges removed | 2026-09-02, Numbers 15.3.1 |
| `18-formula-literals-A1-changed.numbers` | `93c-formula-for-a-literal-change` | `A1` changed from `=1+1` to `=1+5` by replacing one literal node, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `A1` reading 6 |
| `19-formula-dragged-F2-narrowed.numbers` | `19-formula-dragged` | `F2` narrowed from `SUM($B$1:$D$1)` to `SUM($B$1:$C$1)`, leaving `F3` on the archive they shared, now with each formula's dependencies declared, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `F2` reading 3 and `F3` still reading 6, two and three cells highlighted |
| `18-formula-attached-and-detached.numbers` | `93-formulas-for-attaching` | `A1`'s `=1+1` attached to the text `1+1` at `B1`, and `C1`'s `=2*3` detached, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `B1` reading 2 from the attached formula and `C1` a plain 6 with no formula |
| `18-formula-created-in-empty-cell.numbers` | `93b-empty-for-a-formula` | `=SUM(1,2,3)` written into `A1`, which had no cell record at all, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `A1` reading 6 |
| `18-merged-over-a-formula.numbers` | `93d-formulas-for-a-merge` | `A1:B1` merged, covering `B1`'s `=2*3`, so the merge removes a formula record: its formula entry is released and the calculation engine no longer registers `B1`, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `A1:B1` as one cell reading 2 |
| `22c-merged-by-pybers.numbers` | `22c-merge-overpaints.numbers` | `L3:M3` merged, dropping the style-only record `M3` carried | 2026-09-07, Numbers 15.3.1. **Superseded 2026-09-15**: regenerated for PYB-92, releasing the two styles the removed `M3` record named. Re-confirmed 2026-09-15, Numbers 15.3.1: `L3:M3` merged keeping row 3's fill, the other merges, row 5's overpaint and column D untouched, and `L1` still showing the reference error its label predicts |
| `45-merged-by-pybers.numbers` | `45-columns-over-255.numbers` | `KI7:KJ7` merged, rebuilding a 300-column row whose offsets count words | 2026-09-08, Numbers 15.3.1. **Superseded 2026-09-15**: regenerated for PYB-89, releasing the text format the removed `KJ7` record named. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers show `KI7:KJ7` merged holding `r6c295`, and every other cell of the 300 columns as before, `B7`, `E7` and `KM7` being empty in the fixture too. **Superseded again 2026-09-15**: regenerated for PYB-92, releasing the string `r6c296` the removed `KJ7` record named, and removing it. Re-confirmed 2026-09-15, Numbers 15.3.1: `KI7:KJ7` merged holding `r6c295`, row 7 otherwise as the fixture |
| `20-formula-authored-as-text.numbers` | `20-formula-shapes.numbers` | three formulas written as TEXT into `Sheet 1 / Table 2`: `B1` a cross-table reference with arithmetic, `C1` a nested lazy call, `D1` an anchored reference concatenated with a string | 2026-09-08, re-confirmed 2026-09-09 after the sticky-bits fix, Numbers 15.3.1. Regenerated 2026-10-13 for PYB-200, every range now holding `preserve_rectangular`. Re-confirmed 2026-10-13, Numbers 15.4: `/golden-confirm` passed all 8 checks, and the maintainer read its screenshots and Quick Look previews |
| `20-formula-brackets.numbers` | `20-formula-shapes.numbers` | four bracketed formulas written as text into `Sheet 1 / Table 2` row 1: `B1` a bracket precedence does not need, `C1` one it does, `D1` a bracket around a single value, `E1` one associativity alone forces | 2026-09-13, Numbers 15.3.1 |
| `11-text-written-and-retyped.numbers` | `90e-values-for-text-and-retyping` | text written over the numbers at `A1` and `B1` so it pools once, text over the star rating at `C1`, a number over the text at `D1`, and text into `E1`, which had no record, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye each text and the number at `D1` |
| `11-text-literal-written.numbers` | `90d-values-for-literal-text` | literal text, whose Data Format is chosen as Text, written over the number at `A1` as `=SUM(B1:C1)` and into `C1`, which had no record, as `=A1+1`; the ordinary string `=1+1` written at `B1` beside them for contrast, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the two literals reading as Text and the ordinary string beside them |
| `20-first-text-in-a-table.numbers` | `20-formula-shapes.numbers` | the first text in a table holding one number and no text at all, at `B1` and at `A3` in a row the file stored nothing for. A number record shapes it, since there is no string record to copy | 2026-09-14, Numbers 15.3.1, re-confirmed the same day once the text format entry reached the file. The first format entry this library created rather than found. **Superseded 2026-09-15**: regenerated for PYB-89, storing the displayed kind 5 where a key of 2 read as currency, and counting both text cells. Re-confirmed 2026-09-15, Numbers 15.3.1: Quick Look and Numbers show `B1` and `A3`, and both read Automatic |
| `20-formula-rows-created.numbers` | `20-formula-shapes.numbers` | four formulas written into `Sheet 1 / Table 2`, which stored one row of the ten it declares: `A3` and `C3` in one new row, `B7` in another, `E10` in the last row. The first golden whose tile rows this library built rather than edited | 2026-09-14, Numbers 15.3.1. Regenerated 2026-10-13 for PYB-200, every range now holding `preserve_rectangular`. Re-confirmed 2026-10-13, Numbers 15.4: `/golden-confirm` passed all 10 checks, and the maintainer read its screenshots and Quick Look previews |
| `20-formula-retargeted.numbers` | `94c-references-for-a-retarget` | eight anchored formulas written into `E1:L1`, then every reference into `Sheet 1 / Table 1` moved one row down and seven columns right, leaving `C1` and `D1`, which point at `Table 2` and `Sheet 2 / Table 1`, untouched, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye row 1 following the moved references, with `C1` reading 7 and `D1` reading 5 unmoved |
| `20-sheets-added.numbers` | `20-formula-shapes.numbers` | an empty sheet `Inserted` added at position 2, between the sheet holding a cross-sheet formula and the sheet it reads, and `Appended` added last. The first golden whose archives this library created rather than edited | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the sheet list and each sheet's position |
| `20-tables-added.numbers` | `20-formula-shapes.numbers` | three tables created in the pybers reset: `Table 1` added beside a `Table 1` on `Sheet 1`, which becomes `Table 1-1`, with text at `A1` and 12.5 at `B2`; `table 2`, which becomes `table 2-1` because names clash regardless of case, with text at `C2`; and `Output` on a new sheet `Fresh`, with 1 at `A1` and text at `B5`. The first golden whose tables, styles and engine owners this library created | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the created tables' names and positions |
| `20-formulas-in-created-tables.numbers` | `20-formula-shapes.numbers` | two tables created on `Sheet 1`: `Inputs` holding 5 at `A1`, and `Calc` holding 2 at `A1` and four formulas, `B1` reading `A1`, `C1` reading the existing `Table 2`, `A2` reading `Inputs` and `A3` summing `A1:B1`. The first golden whose formulas sit in a table this library created, and the first declaring what each formula reads | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `Calc` reading 2, 6, 42, 6 and 8 |
| `20-formula-precedent-replaced.numbers` | `20-formula-shapes.numbers` | `Sheet 1 / Table 2` given 2 at `A1`, 7 at `A2` and `=A1*3` at `B1`, then saved again with `B1` reading `=A2*3` instead. The swap is the point: a formula that changes what it reads has to re-declare it | 2026-09-16, Numbers 15.3.1: `B1` opens at 21, `A2` set to 10 gives 30, and `A1` set to 100 leaves it at 30 while `Table 1 / G11`, which is Numbers' own formula reading `A1`, follows to 100 |
| `56-row-added-by-pybers.numbers` | `56-structure-base.numbers` | row 3 added with `rowAdd(3)`, inside the merge `C2:D3` | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the added row and the merge it crossed, as confirmed on 2026-09-21 |
| `56-row-removed-by-pybers.numbers` | `56-structure-base.numbers` | row 8 removed with `rowRemove(8)`, breaking three references, one from `Table 2` | 2026-09-21, Numbers 15.3.1: `B5`, `B6` and `Table 2 / A1` show the reference error, the merge `C8:D8` is gone with its row, `A8` holds 9 in the hidden row that followed, and `B1` reads 47 |
| `56-column-added-by-pybers.numbers` | `56-structure-base.numbers` | column E added with `columnAdd("E")`, inside the merge `D5:F5` | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the added column and the merges it widened, as confirmed on 2026-09-21 |
| `56-column-removed-by-pybers.numbers` | `56-structure-base.numbers` | column E removed with `columnRemove("E")`, breaking `B12` | 2026-09-18, Numbers 15.3.1: `B12` shows the reference error, `D5:F5` spans D to E, `F7:G7` sits at `E7:F7`, `E12` reads 28, and column G is hidden |
| `60-move-cut-pasted-by-pybers.numbers` | `60-move-base.numbers` | `B2:D5` moved to `F8` with `cellsMove` under `PRESERVE_RELATIVE_POSITION`, which Numbers performs as cut and paste | 2026-09-24, Numbers 15.3.1: no repair prompt, the block and its merge at `F8:H11`, `B2:D5` empty with nothing left merged, `E1:E9` reading 7, 0, 0, 0, 0, 100, 0, 2 and 0 on the old address, Table 2 reading 5, 0 and 0, and `H10` and `H11` showing the reference error, as Numbers' own `60b` does |
| `60-move-dragged-by-pybers.numbers` | `60-move-base.numbers` | `B2:D5` moved to `F8` with `cellsMove` under `PRESERVE_NAMED_CELL`, which Numbers performs as a drag | 2026-09-24, Numbers 15.3.1: no repair prompt, the block and its merge at `F8:H11`, `B2:D5` empty, `E1:E9` reading 7, 100, 307, 0, 200, 100, 0, 2 and 1097, Table 2 reading 5, 200 and 1092 through `Table 1::G8` and `SUM(Table 1::F8:H10)` |
| `64-cells-copied-relative-by-pybers.numbers` | `60-move-base.numbers` | `B2:D5` copied to `F8` with `cellsCopy` under `PRESERVE_RELATIVE_POSITION`, which Numbers performs as copy and paste | 2026-09-29, Numbers 15.3.1: Quick Look and Numbers agree, the copy and its merge at `F8:H11` reading 100, 200, 300, 1097, 4, 0, 300 and 1399, `H10` and `H11` showing the reference error as Numbers' own `64` does, `B2:D5` and its merge unchanged, `E6` reading 100, and Table 2 reading 5, 200 and 1092 |
| `64-cells-copied-named-by-pybers.numbers` | `60-move-base.numbers` | `B2:D5` copied to `F8` with `cellsCopy` under `PRESERVE_NAMED_CELL`, so each copied formula reads the cells its source reads | 2026-09-29, Numbers 15.3.1: Quick Look and Numbers agree, `F9:H11` reading 3, 4, 100, 300, 78, 7 and 5 as `B3:D5` do, the merge copied to `F11:G11`, and nothing outside the copy changed |
| `20-cells-filled-relative-by-pybers.numbers` | `94b-values-for-a-relative-fill` | `A1`'s `=SUM(A3:A5)` filled across `A1:D1` with `cellsFill` under `PRESERVE_RELATIVE_POSITION`, so each cell sums its own column, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `B1:D1` reading 60, 600 and 6000, each selecting its own column |
| `20-cells-filled-named-by-pybers.numbers` | `94-values-for-a-named-fill` | `A1`'s `=SUM(A3:A5)` filled across `A1:D1` with `cellsFill` under `PRESERVE_NAMED_CELL`, so each cell sums column A, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye `B1:D1` reading 6 each, every copy summing column A |
| `61-cells-filled-by-pybers.numbers` | `61-move-styles-base.numbers` | `B2:D3` filled across `B2:H7` with `cellsFill` under `PRESERVE_RELATIVE_POSITION`, each record duplicated with its fill, bold face and highlighting | 2026-09-29, Numbers 15.3.1: Quick Look and Numbers agree, the block repeating from `B2` so columns E and H repeat B and rows 4 to 7 repeat rows 2 and 3, every copy of 21 filled yellow, of 22 highlighted green by its rule and of 23 bold, and `C3`'s border left on `C3` alone |
| `61-lines-added-beside-no-border-by-pybers.numbers` | `61-move-styles-base.numbers` | a row added at 2 and a column at B with `rowAdd` and `columnAdd`, each beside a line holding no border, which raised before PYB-118 fixed it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the block's fill, highlighting and bold kept, the one border around `D4`, and none on the added row or column |
| `63-cells-filled-by-pybers.numbers` | `63d-fill-border-base.numbers` | `B2:D3` filled across `B2:D7` with `cellsFill` under `PRESERVE_RELATIVE_POSITION`, each copy of the rich-text `B3` given an entry, payload and storage of its own, and each copy of the checkbox at `D3` sharing its control | 2026-09-29, Numbers 15.3.1: Quick Look and Numbers agree, rows 4 to 7 repeating the block with every Hello keeping its mixed formatting and every checkbox checked, and the borders on `C3` and `D3` alone. In a copy, unchecking `D5` changed only `D5`, and editing `B5` left `B3` and `B7` as they were |
| `66-series-filled-down-by-pybers.numbers` | `66-series-vertical-base.numbers` | every case filled down to row 21 with `cellsFill` under `CONTINUE_SERIES`, through twenty kinds of seed | 2026-09-30, Numbers 15.3.1: Quick Look and Numbers agree, each expected value being the far end of what Numbers' own drag wrote in `66b-series-down` |
| `66-series-filled-up-by-pybers.numbers` | `66-series-vertical-base.numbers` | every case filled up to row 2 with `cellsFill` under `CONTINUE_SERIES`, each series running backward | 2026-09-30, Numbers 15.3.1: Quick Look and Numbers agree, each expected value being the far end of what Numbers' own drag wrote in `66c-series-up` |
| `66-series-filled-right-by-pybers.numbers` | `66-series-horizontal-base.numbers` | every case filled right to column U with `cellsFill` under `CONTINUE_SERIES` | 2026-09-30, Numbers 15.3.1: Quick Look and Numbers agree, each expected value being the far end of what Numbers' own drag wrote in `66d-series-right` |
| `66-series-filled-left-by-pybers.numbers` | `66-series-horizontal-base.numbers` | every case filled left to column B with `cellsFill` under `CONTINUE_SERIES` | 2026-09-30, Numbers 15.3.1: Quick Look and Numbers agree, each expected value being the far end of what Numbers' own drag wrote in `66e-series-left` |
| `67-series-filled-by-pybers.numbers` | `67-series-rich-base.numbers` | every column filled down to row 13 with `cellsFill` under `CONTINUE_SERIES`, the rich text repeated and three seeds continued | 2026-09-30, Numbers 15.3.1: Quick Look and Numbers agree, each expected value being the far end of what Numbers' own drag wrote in `67b-series-rich-dragged` |
| `68-series-filled-by-pybers.numbers` | `68-series-kinds-base.numbers` | every column filled down to row 13 with `cellsFill` under `CONTINUE_SERIES`: formatted numbers, times, abbreviated and re-cased names, quarters and durations continued, and ordinals and leading numbers repeated | 2026-09-30, Numbers 15.3.1: Quick Look and Numbers agree, each expected value being the last row of what Numbers' own drag wrote in `68b-series-kinds-dragged`, a duration read as 43200 seconds and shown as 12h |
| `20-functions-added-in-15-4-by-pybers.numbers` | `20-formula-shapes.numbers` | one call to each of the 18 functions Numbers 15.4 added, written by name into `Sheet 1 / Table 2` at `B1:C9`: eight trigonometric, `XOR`, seven statistical, `DAYS`, and `PEARSON` and `RSQ` reading `Table 1` | 2026-10-13, Numbers 15.4: Numbers shows each value it calculated in `69-functions-added-in-15-4`, `B1` holds `=ACOT(1)` and `C2` `=GAMMA(5)`, and Quick Look shows the 18 cells empty until Numbers recalculates. Regenerated 2026-10-13 for PYB-200, every range now holding `preserve_rectangular`. Re-confirmed 2026-10-13, Numbers 15.4: `/golden-confirm` passed all 22 checks, and the maintainer read its screenshots and Quick Look previews |
| `20-whole-axis-ranges-and-booleans-by-pybers.numbers` | `20-formula-shapes.numbers` | eight formulas written as text into `Sheet 1 / Table 2` at `B1:B8`: whole-column and whole-row ranges in the same table and in `Table 1`, two of them anchored, `TRUE` bare, and `FALSE` as an argument, as typed into Numbers for `71-whole-axis-ranges-and-booleans` | 2026-10-13, Numbers 15.4: Numbers shows 0, 2, 96, 5, TRUE, 2, 96 and 5, the values it calculated for its own typed copy, and selecting `B1` highlights the whole of columns C and D for `SUM(C:D)`. Regenerated 2026-10-13 for PYB-200, every range now holding `preserve_rectangular`. Re-confirmed 2026-10-13, Numbers 15.4: `/golden-confirm` passed all 13 checks, and the maintainer read its screenshots and Quick Look previews |
| `11-dates-written-by-pybers.numbers` | `90b-values-for-dates` | dates written with `cell.value`: Jan 31, 2027 and Oct 20, 2026 9:30 over the numbers at `A1` and `B1`, Jun 16, 2027 over the date at `C1`, and Dec 25, 2026 18:45 into `D1`, which had no record, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye each date and time as written |
| `11-durations-written-by-pybers.numbers` | `90c-values-for-durations` | durations written with `cell.value`: 90 minutes over the number at `A1`, 2 hours over the duration at `B1`, and 1 day 2 hours into `C1`, which had no record, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye each duration as written |
| `11-booleans-written-by-pybers.numbers` | `90-values-for-booleans` | booleans written with `cell.value`: TRUE and FALSE over the numbers at `A1` and `B1`, FALSE over the checkbox at `C1`, which keeps its checkbox, TRUE over the star rating at `D1`, which loses it, and TRUE into `E1`, which had no record, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye each boolean, the checkbox kept and the star rating gone |
| `11-controls-written-by-pybers.numbers` | `91-controls-for-values` | values written over each control with `cell.value`: FALSE over the checkbox at `A1` and 100 over the slider at `C1`, which keep their controls, and 7 over the star rating at `B1`, 500 over the stepper at `D1` and `Banana` over the pop-up menu at `E1`, which drop theirs with their formats, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye the checkbox and the slider still working when clicked |
| `12-currency-written-by-pybers.numbers` | `92-values-for-currency` | currency amounts written with `cell.value`: 99.5 CHF over the number at `A1`, the number 12.5 into the dollars at `B1`, which keep their currency, 7 EUR over the accounting-style dollars at `C1`, which keep accounting style and the separator, and 1000 GBP into `D1`, which had no record, each changed cell's label rewritten beneath it | 2026-10-23, Numbers 15.4: `/golden-confirm` passed every check, and a developer confirmed by eye each amount in its currency, accounting style kept at `C1` |

`20-formulas-in-created-tables` is the golden that found two defects no test could have.
A created table carried a `table_id` unrelated to its formula-owner identity, so Numbers
re-identified the table on open and dropped its dependency tiles, leaving every formula
unevaluated and a reference to it reading `The formula contains an invalid reference`.
A formula that declares no precedents computes once, in whatever order Numbers
chooses: the same file read 8 at `A3` on one open and `Cell "B1" contains an error` on
the next. Both are in findings-10-creation.md and findings-02-formulas.md.

Confirmed 2026-09-16: no repair prompt, `Calc` reads 2, 6, 42, 6 and 8, the formula bars
show `A1×3`, `Table 2::A1`, `Inputs::A1+1` and `SUM(A1:B1)`, and Quick Look shows only
the two typed numbers, since Numbers computes the rest on open. Then, in the document:
`Calc::A1` to 4 gives 12 and 16, `Inputs::A1` to 10 gives 11, and `Table 2::A1` to 50
gives 50 in both `Calc::C1` and `Table 1::G11`. Reopened, `A3` still reads its own sum.
The copy that was opened is not the copy committed here.

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

**pybers writes `Table 1::A11` as Numbers does.** A bare table name reaches the table of
that name on the formula's own sheet, even where another sheet holds one, which is what
`Sheet.tableIdentities` records.

`45-merged-by-pybers` is the only golden covering a row whose offsets count four-byte
words rather than bytes. Dropping the record at column 295 moves the three stored after it,
and the write re-emits an offset for every one of the 295 that remain. A unit confused for
a byte would place each of them a quarter of the way along the row, and raise nothing.
Confirmed 2026-09-08: no repair prompt, `KI7:KJ7` renders as one cell holding `r6c295`,
`KM7` is still the empty slot the fixture was built with, and rows 1 through 6 read
`col300` and `r5c300` at the far edge. The copy that was opened is not the copy committed
here.

`20-formula-retargeted` rewrites references rather than values. Its measurement holds
Numbers' own two references into `Table 1` and one each into `Table 2` and
`Sheet 2 / Table 1`, and pybers writes eight anchored formulas beside them, every
combination of locked and free axis, once for a single cell and once for a range. Six
references move, and the six that do not each have a reason: two point into other
tables, and four are locked on both axes.

| cell | written as | after the retarget | what it settles |
| --- | --- | --- | --- |
| `A1` | `=SUM(A3:A7)` | `=SUM(H4:H8)` | Numbers' own range moves on both axes |
| `B1` | `=A3*2` | `=H4*2` | Numbers' own reference moves on both axes |
| `C1` | `=Table 2::A1` | `=Table 2::A1` | a reference into another table stays |
| `D1` | `=Sheet 2::Table 1::A1` | `=Sheet 2::Table 1::A1` | a reference into another sheet stays |
| `E1` | `=$A$3*10` | `=$A$3*10` | both axes locked, nothing moves |
| `F1` | `=$A$5*2` | `=$A$5*2` | both axes locked, beside `G1` and `H1` |
| `G1` | `=A$5*2` | `=H$5*2` | free column moved, locked row did not |
| `H1` | `=$A5*2` | `=$A6*2` | locked column did not move, free row did |
| `I1` | `=SUM($A$3:$A$7)` | `=SUM($A$3:$A$7)` | a range locked on both axes |
| `J1` | `=SUM(A$3:A$7)` | `=SUM(H$3:H$7)` | a range whose columns move and whose rows do not |
| `K1` | `=SUM($A3:$A7)` | `=SUM($A4:$A8)` | a range whose rows move, both ends together |
| `L1` | `=$A$6` | `=$A$6` | locked, and it lands inside the ranges the others now cover |

`G1` and `H1` are the pair that matters most. They differ by one dollar sign, they must
disagree after the move, and an implementation that moved a locked axis would change
exactly one of them while the others still passed.

**A range records its anchoring twice, and Numbers believes the second copy.** The tract
field variant carries it, and an `ASTStickyBits` message beside the tract repeats it. All
9 ranges in the documents carry those bits and none is without them. A range built from
text had none, and absent bits read as unanchored, so Numbers showed a range pybers had
anchored as relative. A single-cell reference carries anchoring only on its coordinates
and never carries sticky bits, measured across all 21 in the documents.

`encodeStickyBits` now writes them from the same `Span.absolute` the tract comes from, so
the two cannot disagree.

`20-formula-authored-as-text` was regenerated once the sticky bits were written, and
re-confirmed the same day: `Sheet 1 / Table 2` reads 42, 111, big and 42 units, `C1` shows
`IF(SUM(A1:A10)>10,"big","small")` with column A highlighted, and `Table 1` row 11 is
untouched at 55, 56, 40, big, 110, 110, 42 and 53. Its `C1` holds a relative range, whose
missing bits happened to read correctly as relative, so the 2026-09-08 confirmation was
sound and only its bytes changed.

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

**The multi-sheet golden was regenerated and re-confirmed on 2026-09-02 for PYB-25**, because the
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

`11-value-types-noformats-A1-edited` writes one number over the only cell its
measurement holds, so `A1` and the label beneath it are all that change.

## The merge pair, and what it caught

`22b-merged-by-pybers` and `22-unmerged-by-pybers` run the twin fixtures through this
library in both directions: merges added to the file that had none, and every merge
removed from the file that had five. Each should end up looking like the twin it was
built from.

**The first attempt was wrong, and only Numbers could say so.** `L1` holds `=J1`, and
row 2 labels it "produces cell ref error". Merging `I1:J1` covers `J1` and makes that
reference invalid; unmerging makes it valid again. A merge changes what a reference
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
unshared formula, the only cell its measurement holds.

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

`19` was confirmed on 2026-09-03 in Numbers 15.3.1, before the save declared each
formula's dependencies.

That confirmation showed the split from both sides, which the grid alone could not do.
Selecting `F2` shows `SUM($B$1:$C$1)` in the formula bar with two cells
highlighted and a result of 3; selecting `F3` shows `SUM($B$1:$D$1)` with three
cells highlighted and a result of 6. Every other cell is unmoved, including the
mixed-locking pair `G2` at 3 and `G3` at 2. Had the pooled entry been overwritten
instead of split, both would read 3 and both formula bars would say `$B$1:$C$1`.

## The attach and detach golden, and the two-register finding

`B1` holds the text `1+1` in its measurement and now carries `A1`'s `=1+1`, displaying
**2**. `C1` held `=2*3` and now holds a plain **6** with an empty formula bar.

**This golden took three attempts, and the first two are the reason it exists.** The
calculation engine keeps its own register of which cells hold formulas, and setting the
record's formula flag and pooling the archive is necessary but not sufficient.

- Attempt one updated neither register. The attached cell stayed as text and Numbers never knew a
  formula was there.
- Attempt two updated `cell_dependencies` only. Selecting the attached cell then showed
  `Formula 1+1` in the footer while the cell still displayed `1+1`, which is the most
  misleading state available: correct to anyone who clicks it, never evaluated.
- Attempt three updated `tiled_cell_dependencies` as well. The register is stored
  TWICE, and both copies have to agree.

The detached cell also shows why a pass is not a pass. Attempt two rendered it correctly while the
register still claimed it held a formula, so the detach half looked confirmed while
leaving the document lying about itself.

## The fill goldens

`20-cells-filled-relative-by-pybers` fills `A1`'s `=SUM(A3:A5)` across `A1:D1`. Each cell
resolves against its own column, so `B1` reads `=SUM(B3:B5)` and `D1` reads `=SUM(D3:D5)`,
**and the file holds ONE formula rather than four**: one entry at refcount 4, which is what
dragging does in Numbers. Read it through its formula bars as well as its numbers: `B1`,
`C1` and `D1` read 60, 600 and 6000, each selecting a different range from one stored
formula. `20-cells-filled-named-by-pybers` fills the same cell keeping each copy reading
column A, so all four read 6.

## Confirming one

Run `/golden-confirm` on the golden. It opens a copy in Numbers, never the golden itself,
since opening a document in Numbers may rewrite it: on 2026-09-01 autosave renamed
`Index/ViewState-913882.iwa` and grew a golden by 235 bytes with no edit and no prompt. It
checks every cell of every table against what pybers reads from the golden, reads each
currency and control in the inspector, and leaves for a person each label, each formula
value Numbers recalculated, and the screenshots and Quick Look preview.

**A golden file that has not been confirmed is not a golden file.** A developer reads the
run's report, opens its copy beside its expectations, and records the date and the Numbers
version in the table above. Until that row says so, the test guarding it proves only that
the writer is consistent with itself.

## Regenerating one

A golden is written only by its builder:

```
.venv/bin/python3 -m pytest tests/test_goldens.py --golden-write -k <golden>
```

Written only when the change to the output is intended, since regenerating is how a bug gets
locked in as the expected answer, and confirmed in Numbers again before it lands. Every build
of a golden is identical, the identities pybers creates included, so a golden opened in place
by accident is restored by writing it again.

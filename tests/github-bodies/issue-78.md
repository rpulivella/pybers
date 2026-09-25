As a Python developer I want an edit written into any addressable cell to survive the save so that what I wrote is in the file I opened rather than gone without a word.

## Acceptance criteria

1. A formula written into a cell in a row the table stores no data for is present when the document is read back.
2. The row that write creates opens in Numbers with no repair prompt, confirmed by eye and recorded as a golden.
3. An edit that cannot be completed refuses and says why, rather than reporting success and losing the edit.
4. A regression test fails for the original defect.

## Constraints

- Measured 2026-09-13 on `develop` against `20-formula-shapes`, whose `Sheet 1 / Table 2` stores a row only for row 1. `=1+1` written into `B1`, which carries no record but sits in that stored row, reads back after `save()`. The identical write into `A2` or `A3` reads back as nothing.
- The same class as PYB-65: the save reports success and the work is gone, with nothing raised.
- PYB-61 AC 3 asks that text written into a cell with no record create one, the same way a formula already does. That holds only inside a row the table already stores, which is the gap here.

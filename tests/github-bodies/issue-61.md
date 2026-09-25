As a Python developer I want to write text into a cell and change what a cell holds, so that a script can put a label where a number was and read it back the same way Numbers would.

## Acceptance criteria

1. A string written to a cell is saved, opens in Numbers as that string, and reads back as it was written.
2. A cell holding a number becomes a text cell when text is written to it, and a cell holding text becomes a number cell when a number is written to it.
3. Text written into a cell that had no record at all creates one, the same way a formula already does.
4. The same text written into several cells is stored once, with the count Numbers keeps, so the pooled list matches one Numbers itself wrote.
5. ~~A cell's number format, style and every other trailing reference survive a value being written over it.~~ Rewritten 2026-09-14, having been measured wrong. A cell's style survives. Its format moves to the slot its new kind uses and follows into the slot naming the format in effect. Its control does not survive, because a control describes the value it was built for and leaving one in place made Numbers render a sentence as a star rating. A format a person chose is not inherited by a cell that borrowed its shape from another.
6. Writing a value over a cell that holds a formula is still refused, and says so.

## Constraints

- A text cell holds a key into the table's pooled STRING list rather than the text, so writing one means adding to that list and pointing at it. The record layout and the two key-bearing types are in findings-01-values.md.
- Changing a cell's type needs a new record rather than a patched one, because the value width differs, and the trailing references have to be carried across.

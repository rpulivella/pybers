As a Python developer I want to write a value that Numbers will not interpret so that a label reading like a formula stays the text I wrote rather than becoming a calculation the first time somebody clicks into the cell.

## Acceptance criteria

1. A value written as uninterpreted text opens in Numbers with a Data Format of Text rather than Automatic.
2. Clicking into such a cell in Numbers and pressing return leaves the text as it was rather than turning it into a formula.
3. Writing an ordinary string is unchanged and still opens as Automatic, which is what typing into Numbers produces.
4. A cell written this way reads back as the text it was given, and a round trip through the model and the file changes nothing about it.
5. The same request against a cell already holding a formula is refused, and says so, since the formula is what would be lost.

## Constraints

- Byte 6's `0x80` is the whole mechanism, measured in findings-01-values.md: 108 text records carry it against 4515 that leave it clear, and the inspector reads `Text` with it and `Automatic` without.
- `47-formula-cell-attributes` `C1` is the shape to match. It holds `=SUM(A1:A5)` as literal text, which is only possible because the format was chosen before the text was typed, and it is what separates this from a label that merely looks like one.
- Writing the string already works. pybers stores `=1+1` as text with no formula today, and Numbers displays it literally, because Numbers interprets on typing rather than on opening. What is missing is that the cell stays that way when somebody edits it.

As a Python developer I want to style part of a cell's text by character range, with a named character style or ad hoc formatting, so that one word in a label can carry emphasis as InDesign character styles allow.

## Acceptance criteria

1. A named character style applies to a range of a cell's text, and the rest keeps its paragraph style.
1. Ad hoc formatting applies to a range the same way, without creating a named style.
1. A range counts the characters a caller sees, so text holding emoji or other astral characters styles exactly the characters intended.
1. A range reaching outside the cell's text is refused.
1. A cell stays plain text until some range differs from the rest.
1. Each case is locked in by a golden file holding an astral character, opened once in Numbers and confirmed correct.

## Constraints

- **Blocked by PYB-8.**
- Run indices count UTF-16 code units, and character styles live only in rich-text storage, never in the table's style list (`findings-04-text.md`).
- Ad hoc formatting is an anonymous variation of the character style named `None`, while a saved named style is a root.

As a Python developer, or an agent driving this library, I want to write a formula the way I would type it in Numbers so that authoring a long expression does not mean assembling nodes by hand.

1. A formula given as text is stored as the AST that text describes, and the document opens in Numbers showing the formula that was written.
2. A formula in a document renders to the text Numbers itself displays for it, so a caller can read one without walking nodes.
3. Rendering and parsing are inverses over every formula in a real corpus: each one read from a document, rendered, and parsed again yields the AST it started as.
4. Precedence and nesting follow Numbers: arithmetic binds tighter than comparison, parentheses override, and a call nested inside another call is stored correctly.
5. Anchoring survives the text: `$B$1`, `$B1`, `B$1` and `B1` each produce the locking they are written with, on each axis independently.
6. A range, a whole column, and a reference into another table each parse to the node the archive uses for them.
7. Text that is not a valid formula is refused with the position that failed, rather than stored as something that opens wrong in Numbers.
8. A caller may pass a `CellRange` or `CellReference` as a named piece of the text rather than interpolating it, so an address this library validated stays validated.
9. A formula Numbers stores as its own node types rather than as an indexed call, `LET` and `LAMBDA` among them, round-trips through text like any other.
10. A function name Numbers does not accept is stored the way Numbers stores it, with the spelling preserved, rather than refused, so text Numbers takes is text this library takes.

## SPEC

- **Derive the operator table from Numbers' own node types**, which findings-02 records: 1 addition, 3 multiplication, 4 division, 6 concatenation, 7 comparison. Starting from a borrowed table and patching toward Numbers is what numbers-parser did, taking openpyxl's Excel tokenizer, and its precedence table then omitted every comparison operator. That failed only once a comparison followed other arithmetic, so `1<2` worked and `A+B<=10` raised. Deriving the table the other way makes a missing operator a missing node type.
- The text is a constructor and never reaches the file. Numbers stores no formula text at all, `TSCE.FormulaArchive` having one content field, so anything this ticket parses must end as nodes.
- **The renderer is not a convenience, it is how the parser gets tested.** Comparing hand-written node arrays does not scale past a dozen cases, and a corpus of real documents does: AC 3 runs both directions over every formula in one, and the AST it starts from came out of Numbers rather than out of this library, which is the anchor that keeps the two halves from agreeing while both are wrong. Running that over a corpus is also how syntax nobody has seen yet gets found, so treat a parse failure there as a finding rather than a bug.
- Corpus documents live in `workarea/`, which is git-ignored in full. A file only becomes a committed fixture when it is small, purpose-built and carries nothing real, since this repository is going public and a fixture is permanent.
- Naming functions is a separate prerequisite: the archive holds a numeric index and nothing else.

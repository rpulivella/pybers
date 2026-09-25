As a Python developer I want a formula already stored in a document to read back as a structure I can examine and change so that editing a spreadsheet by script never means rebuilding a formula Numbers already wrote.

1. Reading a cell that holds a formula yields a structured formula whose nodes can be examined, and `Cell.formula` no longer carries text.
2. Every reference in a formula reports anchoring separately for each axis, so `$B1`, `B$1` and `$A$1` are distinguishable, and a relative reference reports a signed offset from the cell holding it where an absolute one reports a plain coordinate.
   1. A whole-column reference reads back as having no row at all, rather than as row zero.
   1. A reference pointing nowhere reports as broken, rather than as a cell at column 32767.
3. Changing one cell's formula leaves untouched every other cell that shared the stored formula, on the read path and through a save alike.
4. A document carrying the formula shapes in fixtures 18 through 21 reads and writes back unchanged, and the result opens in Numbers with every formula intact.
   1. A node type the model does not recognize survives the round trip byte for byte.
   1. A function Numbers itself could not resolve keeps its spelling.
5. A formula changed through the model writes back, and the document opens in Numbers displaying the changed formula's result rather than the result cached before the edit.
6. A cell whose formula failed reports as errored, and no error kind is invented for it.

## SPEC

- Anchoring lives in a different place depending on the node. A RANGE records it twice, in the field variant (`absolute_column` against `relative_column`) and again in `ASTStickyBits`. A single-cell reference records it only as `absolute` on each coordinate and carries no sticky bits at all, 0 of 21 across the corpus, so reading the bits as authoritative for one finds nothing and reports it unlocked.
- A broken reference is node type 46 carrying column 32767 and row 2147483647. Both parse as ordinary coordinates and raise nothing.
- A formula-backed cell names its formula in the FIRST of its trailing references. Value matching cannot establish that, because keys and style indices are both small integers and several slots coincide. Reproducing every declared refcount can. An error cell is type 8 and consumes no value, so byte 12 is at once its value slot and that first slot, and one rule covers both.
- The node message has 45 fields, so an unrecognized node is carried through rather than interpreted. Function indices are numeric (168 is SUM) and deriving a name map for them is deliberately not part of this ticket.

See `tests/fixtures/findings-02-formulas.md`, which established all of the above.

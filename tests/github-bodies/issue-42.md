As a Python developer I want to write a formula once and fill it down a column so that a script builds a spreadsheet the way a person does, rather than emitting a different formula for every row.

1. A formula built in the model and attached to a cell that held no formula saves, and the document opens in Numbers with that formula in that cell.
2. Reading the saved document back returns a formula equal to the one that was built, so authoring and reading agree.
3. A newly written formula shows its correct computed result when the document is opened, without pybers evaluating anything.
4. One formula filled down a column resolves per row exactly as dragging it in Numbers does, and the saved document holds ONE formula rather than one per row.
   1. A relative reference follows each row, an absolute one stays put, and a reference locked on one axis moves on the other.
   1. Filling across cells that already hold values replaces those values.
5. A function call can be written and Numbers computes it, identified by the numeric index the archive stores. An operator needs no index and no lookup of any kind.
6. Attaching a formula to a cell that already held a plain value replaces that value, and the cell afterward reports as backed by a formula.
7. Removing a formula leaves an ordinary value cell holding the result it last computed, and Numbers opens the document without complaint.

## SPEC

- **Filling shares one stored formula rather than writing one per row**, which is what Numbers itself does: `19-formula-dragged` carries every formula at refcount 2, one archive serving a cell and the cell it was dragged into. Anchoring then needs no special cases, because a relative reference already resolves against whichever cell holds it. The obvious implementation, generating a formula per row with adjusted references, passes a naive test and diverges the moment an axis is locked. Ruling it out by making the shared archive the only path is the point, rather than validating the output afterward.
- A table that has never held a formula carries no formula-owner record at all, measured across all 74 tables in the corpus, so writing the first formula into such a table means creating what every other table already has.
- The cell record carries a formula flag at byte 9, bit `0x02`, beside the formula key in its first trailing reference. A formula written without that flag is stored and then never consulted, and filling into an empty cell means creating a record rather than patching one, which the writer cannot do yet.
- pybers cannot evaluate, so a new formula's cached result is a placeholder until Numbers recalculates. `refs_to_dirty` causes that on open, and PYB-25 established that naming only the changed cells is enough. **Any reasonable placeholder is safe**, measured 2026-09-04: two formulas were swapped between a number-typed and a text-typed record, and Numbers showed both correctly with no warning and no repair prompt, so it repairs the record type while recalculating. The caller therefore never has to declare what a formula will evaluate to.
- Confirm a written file with Quick Look AND with Numbers. Quick Look renders the STORED value and does not recalculate, so the pair separates what pybers wrote from what Numbers made of it.

Formulas are built here through the model, node by node. Writing them as text belongs to its own ticket, along with the function name map that makes a call readable.

See `tests/fixtures/findings-02-formulas.md`.

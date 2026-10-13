# Formulas

How formulas are stored, why references survive being moved, and what happens when one
fails. Reading this before designing anything formula-shaped will save a rewrite.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## Formulas are a postfix AST, not text: and this decides the object model

From `18-formula-literals`. A formula is stored in a `FORMULA` `TableDataList` as a
`TSCE.FormulaArchive`, whose whole content is a flat array of nodes in **postfix order**,
a stack machine, with no text anywhere:

```
=1+1         [NUMBER(1), NUMBER(1), ADDITION_NODE]
=2*3         [NUMBER(2), NUMBER(3), MULTIPLICATION_NODE]
=SUM(1,2,3)  [NUMBER(1), NUMBER(2), NUMBER(3), FUNCTION_NODE(index=168, numArgs=3)]
```

Operators are nodes with implied arity; functions carry a numeric `index` and an explicit
`numArgs`. Numeric literals are **decimal128** in `decimal_low`/`decimal_high`, the same
encoding as cell values, alongside a float64 convenience copy.

**`Cell.formula: str | None` is therefore wrong** and must become a structured type. A string
would mean emitting a language Numbers then has to re-parse, a lossy conversion in each
direction around a format that is already a tree.

### A formula cell stores its computed RESULT, typed by that result

`formulaCellType = 4` never appears. `=1+1` is an ordinary **type 2** cell holding `2`;
`="a"&"b"` is **type 3** holding `'ab'`. The formula is reached by a key in the cell's tail,
and the value slot caches what it evaluated to.

Two consequences. Reading a value never requires evaluating anything, because the answer is
already stored. And **writing a formula means writing a plausible cached result too**, a
stale or missing one would display the wrong number until Numbers recalculated.

**Opening the document is not when it recalculates**, measured 2026-09-02 against
`tests/golden/20-formula-shapes-multisheet-edited.numbers`. That file's `A1:A10` were
raised to 10055 while `A11`, holding `SUM(A1:A10)`, still displayed the cached 55 after
a clean open with no warning. So the staleness above is not a transient a writer can
count on Numbers resolving: it survives on screen, and it reaches every formula
depending on an edited cell, not only a formula the writer wrote itself.

**But a writer can ask for the recalculation, and marking the edited cells is enough.**
Measured 2026-09-02 for PYB-25. `TSCE.CalculationEngineArchive.refs_to_dirty` points at a
`TSCE.ReferencesToDirtyArchive` that every clean document carries and every clean
document serializes to zero bytes. Populating it with the cells that changed, and
nothing else, makes Numbers recalculate on open:

```
A11  SUM(A1:A10)                        55  ->  10055
B11  SUM(A1:A10)+1                      56  ->  10056
C11  SUMIFS(A1:A10,A1:A10,">5")         40  ->  10055
E11  =A11*2                            110  ->  20110
F11  =SUM(A)                           110  ->  20110
G11  reference into another table       42  ->   1042
H11  reference into another sheet       53  ->   1053
```

Two measurements, not one. A **broad** set naming the ten edited operands *and* the eight
dependent formula cells recalculated all eight. A **minimal** set naming only the twelve
edited cells across three tables, never mentioning row 11, produced byte-for-byte the same
eight results. **So Numbers walks its own dependency graph from the cells it is told
about**, and a writer needs to know only what it wrote. `E11` depends on `A11` rather than
on any edited cell, and `G11` and `H11` reach into another table and another sheet, so the
propagation is transitive and crosses owners.

The structure is `to_dirty_owner_ids` (an `IndexSetArchive` of internal owner ids) plus
`to_dirty_cells`, an `InternalCellRefSetArchive` of per-owner column entries each holding
a row `IndexSetArchive`. **A table's internal owner id is not stored on the table.** It is
read the other way round: the `FormulaOwnerDependenciesArchive` whose `owner_kind` is 1 and
whose `formula_owner` reference points at a `TST.TableInfoArchive` carries the
`internal_formula_owner_id` for that table.

A failing formula is different: `18` includes `=ROUND(2.5)`, invalid because ROUND needs two
arguments, and that cell is **type 8** (`formulaErrorCellType`) carrying its formula key in
the value slot rather than the tail.

### Reference locking is a per-axis flag, not a syntax

```
ASTLocalCellReferenceNodeArchive {
  row_handle
  column_handle
  row_is_sticky        the $ on the row
  column_is_sticky     the $ on the column
}
```

**`$` is not an escape hatch in this format. It is two booleans on a reference.** `$A1`,
`A$1` and `$A$1` are three combinations of the same two flags, which is why mixed locking
behaves correctly in Numbers and why dragging never needs a textual workaround. Anchoring is
a genuine property of a reference, and pybers should model it as one rather than as
punctuation inside a string.

A separate `AST_cross_table_cell_reference_node_reference` exists, so local and cross-table
references are distinct node kinds rather than one kind with an optional table.

### ANSWERED: references are relative offsets, and one formula is shared by many cells

`19-formula-dragged` settles it. Every formula there has **`refcount = 2`**, a single
stored archive shared by the original cell and its dragged copy, producing *different*
results in each. That is only possible if references resolve against the containing cell.

`SUM(B1:D3)`, unlocked, one archive serving both rows:

```
relative_column { range_begin: -3, range_end: -1 }
relative_row    { range_begin: -1 }
```

Signed offsets from the cell holding the formula. In row 1 it sums the numbers and gives 6;
the same archive in row 2 resolves one row lower, lands on the text row, and gives 0.

**Absolute is a different field, not merely a flag.** The locked version carries
`absolute_column` and `absolute_row` where the relative one carries `relative_column` and
`relative_row`, with plain coordinates instead of offsets:

```
absolute_column { range_begin: 1, range_end: 3 }
absolute_row    { range_begin: 0 }
```

`ASTStickyBits` records the same fact alongside, all four false for the relative form, all
four true for the locked one, so anchoring is expressed twice, in the field variant and in
the bits.

**That doubling belongs to RANGES only**, measured across the whole corpus on 2026-09-03
for PYB-41 and stated here because the paragraph above reads as a general rule and is not
one. A range node carries both records. A single-cell reference carries the `absolute`
flag on each coordinate and **no sticky bits at all**, 0 of 21 in the corpus. A reader
that took the bits as authoritative for a single-cell reference would find none and
report every such reference unlocked, which is a plausible wrong answer rather than an
error: the formula still resolves, simply to the wrong cell once it is moved.

**Mixed locking is per axis on one reference.** `$B1+C$1` decodes to two coordinate nodes
and an addition:

```
column={column: 1,  absolute: true }   row={row: -1, absolute: false}    ->  $B1
column={column: -4, absolute: false}   row={row: 0,  absolute: true }    ->  C$1
```

An absolute column beside a relative row, then the reverse, on the same formula.

### What this decides

**A relative reference is relative to wherever its cell sits**, so a copied formula is
correct by construction, which is why Numbers never needs `$` as a workaround. Locking is
then free to mean what it should: *this one stays put*.

For pybers this means the file holds no formula text to parse and nothing for a regex to
shift. The range-shifting defect recorded in `docs/decisions.md` came from treating as
text something the format never stored as text. What remains is a walk over nodes, and an
unrecognized node type is carried through untouched rather than interpreted, since a
formula is shared state that other cells depend on.

**A move rewrites references under one of two rules**, which the caller names, and neither
is a default. `PRESERVE_RELATIVE_POSITION` rewrites nothing but a range reaching past its
table, clamped to the edge, because a locked axis stores an index.
`PRESERVE_NAMED_CELL` rewrites every relative offset that leaves the block, and every
locked index that points into it. See [structure](findings-03-structure.md).

### Cross-table references are relative offsets plus a table UUID

From `20-formula-shapes`, which points one cell at a second table on the same sheet and
another at a table on a second sheet. Both produce the **same** node type as an ordinary
reference (`36`) with one extra field:

```
column: -6, absolute: false          an ordinary relative offset
row:   -10, absolute: false
cross_table_reference_extra_info { table_id: <128-bit UUID> }
```

**The table is named by identity, never by name or position.** Renaming a table, moving it,
or reordering sheets cannot break a formula pointing into it. Same principle as relative
offsets: address by identity, not by location.

Note that `ASTCrossTableCellReferenceNodeArchive` exists in the schema and is **not** used.
Numbers writes the compact form instead. A reader must handle what is written, not what the
schema permits.

### Multi-range functions carry each range as a separate node

`SUMIFS(A1:A10,A1:A10,">5")` decodes to two independent range tracts, each with its own
`sticky_bits`, then the criteria string, then the call:

```
67 (range, relative)   67 (range, relative)   19 (string ">5")   16 FUNCTION 231 numArgs=3
```

This is the exact shape of the range-shift bug in CLAUDE.md. Because each range is its own
node with its own anchoring, adjusting one cannot disturb the other, the structure makes
the correct behavior the default, which is precisely what a regex over formula text could
not do.

### A whole column or row: absent in a reference, a sentinel in a range

`SUM(A)` gives `column: -5, absolute: false` and **no row component at all**: a single-cell
reference expresses an unbounded axis by absence.

A range does not. Typed into Numbers 15.4 for `71-whole-axis-ranges-and-booleans`,
`SUM(C:D)` and `SUM(Table 1::B:C)` hold an **absolute row of 2147483647 with no end**, and
`SUM(5:6)` and `SUM(Table 1::2:3)` an **absolute column of 32767 with no end**. These are
the values a broken reference uses (node type 46), so the node type decides which they
mean. The sticky bits leave the unbounded axis unlocked though the tract holds it
absolute, and `$B:$C` locks only the bounded axis. Read as a line, the sentinel names one
far past any table and the range cannot be rendered, which is how the Retirement
template's `VLOOKUP(Life Plans::B1,Data::B:E,4,FALSE)` surfaced it.

### TRUE and FALSE typed bare are boolean nodes

`=TRUE` and the `FALSE` in `=IF(FALSE,1,2)` are node type 18 holding
`AST_boolean_node_boolean`, not calls. `TRUE()` with brackets stays a call to function 156.

### The engine keeps its own register of which cells hold formulas, stored TWICE

From PYB-42, measured 2026-09-04, and found only because a golden was opened in
Numbers. Setting a cell record's formula flag and pooling the archive is **necessary but
not sufficient**. `TSCE.FormulaOwnerDependenciesArchive` carries a register of the cells
that hold formulas, and a cell missing from it is never evaluated.

The register appears twice and both copies have to agree, the same doubling as anchoring
on a range:

```
cell_dependencies         CellDependenciesExpandedArchive, on the owner entry
tiled_cell_dependencies   references to CellRecordTileArchive (type 4009), 32 columns
                          per tile; every tile in the corpus begins at row 0, so the
                          row extent is NOT established
```

Three attempts, and the two failures are the useful part:

1. **Neither register updated.** The cell stays as it was and Numbers never knows a
   formula is there. Nothing warns.
2. **Only `cell_dependencies` updated.** Selecting the cell shows the formula in the
   formula bar while the cell still displays its old value. This is the most misleading
   state available, because the cell looks correct to anyone who clicks it.
3. **Both updated.** The formula evaluates.

**Removing a formula has the mirror hazard.** A detach that leaves the entry behind
renders correctly today while the document claims a formula that no longer exists, so
the half that looked confirmed was passing by luck.

`40-table-bands` is the only fixture with more than one tile: eight of them, at columns
0, 32, 64, 96, 128, 160, 192 and 224.

### A registered formula still has to say what it reads, or it computes once

Measured 2026-09-16 for PYB-86, and found the same way: a golden opened twice gave two
answers. `SUM(A1:B1)` read 8 on the first open and `Cell "B1" contains an error` on the
second, because Numbers evaluates in an order of its own and a formula reading a cell
computed later caches whatever that cell still held. Nothing warns, and the second
answer survives every reselection.

**The engine stores what each formula reads, in three registers, each kept twice.**

```
a cell       expanded_edges on the formula's own record, in BOTH copies of the
             register above: edge_without_owner_rows/columns inside the table,
             edge_with_owner_* plus internal_owner_id_for_edge across tables
a rectangle  range_dependencies.back_dependency on the owner, and a
             RangePrecedentsTileArchive (type 4010) per owner the ranges belong
             to, referenced from tiled_range_dependencies
whole lines  spanning_column_dependencies.coord_refers_to_spans, or the row
             counterpart, which is where `SUM(A)` lands rather than in a rectangle
```

Coordinates are absolute and count from zero, never the offsets the formula itself
stores. A call naming one range twice, as `SUMIFS` does in `20-formula-shapes`, is one
entry. A rectangle of one line omits that axis of its size, as the default is 1.

**A formula swapped for another has to re-declare what it reads**, which is a third
state beside attaching and detaching one. Confirmed 2026-09-16 in
`20-formula-precedent-replaced`: a cell moved from `=A1*3` to `=A2*3` follows `A2` and
ignores `A1`, where the register left alone had it the other way round.

The check that settles it: strip the eight formulas of `20-formula-shapes` and write
them back with pybers. All three registers, and the range tile, come back identical to
what Numbers wrote. `tests/test_table_formula.py` holds that as a test.

### Broken references, unknown functions, and what errors do NOT store

From `21-formula-errors`.

A **deleted reference** becomes node type `46` (not the usual `36`) carrying sentinel
coordinates:

```
column = 32767      (0x7FFF, maximum int16)
row    = 2147483647 (0x7FFFFFFF, maximum int32)
```

So `#REF` is a coordinate deliberately pointing nowhere, and is recognizable structurally.

An **unknown function keeps its spelling**: node type `31` carries
`unknown_function_node_string = "UNKNOWNFUNC"` with its argument count. Numbers preserves
the text of a function it cannot resolve, so an unrecognized formula still round-trips,
the same instinct pybers applies to unknown cell types.

**A circular reference is not marked at all.** Two cells referring to each other hold
ordinary relative coordinates; circularity is a property the calculation engine detects, not
one the file records.

**The kind of error is not stored.** The `FORMULA_ERROR` data list is empty; an error cell is
simply type 8 pointing at an ordinary formula. Division by zero is indistinguishable in the
file from any other failure. Only `#REF` is visible, through those sentinels. So pybers can
report *that* a cell errored and, for broken references, *why*, but reproducing Numbers'
error text for anything else would mean evaluating the formula.

### Node types identified so far

```
 1  addition            17  number literal      36  cell coordinate
 3  multiplication      19  string literal      46  broken reference (sentinels)
 4  division            31  unknown function    67  range tract
 6  concatenation       32  whitespace appended, see findings-08
                        33  whitespace prepended
 7  comparison
16  function call
34/35  a bracketing pair around each argument of a nested call
```

**An operator IS its node type, and carries nothing else**, added 2026-09-04 from
PYB-41 along with types 3 and 6. `1+1` is type 1, `2*3` is type 3, `"a"&"b"` is type 6,
and none of them holds a field beyond `AST_node_type`, arity being implied. Every
FUNCTION, by contrast, is type 16 distinguished by a number. So the name map below is
needed for functions only: operators need at most a node-type-to-symbol table, and that
one is derivable from these fixtures rather than from Numbers.app.

Function indices: **168 = SUM, 62 = IF, 231 = SUMIFS, 126 = ROUND**. `ROUND(2.5)`
and `ROUND(2.5,0)` share index 126 with different `numArgs`, so arity is carried on
the call rather than encoded in the index. The full name map is derived
from Numbers itself by `tools/functions-extract.py`, rather than borrowed.

**Excel's table is not that map, checked 2026-09-03.** The comparison is worth making
because the two applications interoperate and because Excel's older binary format stores
formulas the same way Numbers does, as postfix tokens whose calls carry a numeric index.
Microsoft documents that index table as the `Ftab` in `[MS-XLS]`, and it disagrees
completely: `SUM` is 4 there against 168 here, `IF` is 1 against 62, and `SUMIF` is 345
against `SUMIFS` at 231. Excel's numbering follows its own implementation history,
interleaving Excel 4.0 macro commands such as `ADD.MENU` and `FOPEN` with real functions,
and reserves `0x00FF` for a user-defined function. Borrowing it would yield plausible
wrong functions rather than a failure.

Where the two formats DO agree is one level up: both store a formula together with the
result it last computed. `.xlsx` writes `<f>B7*7</f><v>56</v>`, formula text beside a
cached value, and Numbers writes a formula key beside a cached value. So interoperation
happens by translating at the boundary, not by sharing an encoding, which is why the
tables were free to diverge and why building a Numbers formula out of a string cannot
work. A string carries no per-axis anchoring, no distinction between an offset and a
fixed coordinate, and no cross-table identity.

The node message has 45 fields, so exhaustive modeling is neither necessary nor wise.
Unrecognized nodes should be carried through untouched, a formula is shared state that
other cells depend on.

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

**Mixed locking is per axis on one reference.** `$B1+C$1` decodes to two coordinate nodes
and an addition:

```
column={column: 1,  absolute: true }   row={row: -1, absolute: false}    ->  $B1
column={column: -4, absolute: false}   row={row: 0,  absolute: true }    ->  C$1
```

An absolute column beside a relative row, then the reverse, on the same formula.

### What this decides

**Moving a cell requires no reference rewriting.** A relative reference is already relative
to wherever the cell sits, so a moved or copied formula is correct by construction, which
is why Numbers never needs `$` as a workaround, and why a user can drag freely without
anything breaking. Locking is then free to mean what it should: *this one stays put*.

For pybers this removes an entire class of work. There is no formula text to parse, no
reference rewriting on move, and no regex, the defect in CLAUDE.md's bug list came from
treating as text something the format never stored as text. What remains is a walk over
nodes, and unrecognized node types should be carried through untouched rather than
interpreted, since a formula is shared state that other cells depend on.

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

### A whole-column reference is a coordinate with no row

`SUM(A)` gives `column: -5, absolute: false` and **no row component at all**. Unboundedness
is expressed by absence rather than by a sentinel or a flag.

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
 4  division            19  string literal      46  broken reference (sentinels)
 7  comparison          31  unknown function    67  range tract
16  function call       32  unidentified, follows a call in several files
34/35  a bracketing pair around each argument of a nested call
```

Function indices: **168 = SUM, 62 = IF, 231 = SUMIFS**. These are numeric, so a name map is
eventually needed and must be derived rather than borrowed, per the schema-ownership
decision.

The node message has 45 fields, so exhaustive modeling is neither necessary nor wise.
Unrecognized nodes should be carried through untouched, a formula is shared state that
other cells depend on.

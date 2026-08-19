# Structure: merges, tables and sheets

Merged cells, what structural edits do to them, and how tables and sheets are arranged
on a document.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## Merges are stored as FORMULAS, which is not what anyone would guess

From `22-merge-2x2` and `22b-merge-unmerged`, a pair differing only by whether the merges
exist. That pairing is what made this findable: presence checks had already misled once.

**A merge region lives in `TableModelArchive.merge_owner.formula_store.formulas[]`**, and each
one is a complete `TSCE.FormulaArchive`:

```
COLON_TRACT_NODE
  cross_table_reference_extra_info { table_id: <the table's UUID> }
  sticky_bits { all four absolute: true }
  colon_tract   { absolute_column {0..1}, absolute_row {0} }
FUNCTION_NODE   index=168  numArgs=1
```

Structurally that is `SUM($A$1:$B$1)`. Numbers expresses a merged region by reusing the
reference machinery it already had, so merges participate in the same dependency and
reference system as real formulas rather than being a parallel mechanism.

Measured across the pair:

```
merged     5 formulas: columns [0..1] [2..3] [4..5] [6..7] [8..9], all row 0
unmerged   0 formulas, and next_formula_index STAYS 5
```

The five ranges match the five columns missing from the tile exactly. `next_formula_index` is
monotonic and does not reset, so merge indices are never reused.

### Covered cells do not exist

The cells a merge covers have **no record in the tile at all** — indistinguishable from empty.
`spanCellType` is defined in `CellType` and is not used for this. So a reader cannot tell a
covered cell from an empty one by looking at the tile; it has to consult the merge ranges.
That makes merges load-bearing for correct reading, not an optional nicety.

### Merging is destructive, and unmerging does not undo it

When two cells that both hold content are merged, their values are **joined into a single
text cell separated by tab characters**:

```
"Hello" + "Hello Again"   ->   'Hello\tHello Again'
1 + 10                    ->   '1\t10'      a STRING, not a number
```

Numbers coerces to text, so merging two numeric cells destroys both numbers. `22b` proves the
loss is permanent: after unmerging, the tab-joined strings remain and the original values are
gone. **Anything in pybers that merges cells is performing a destructive operation** and
should say so.

### A reference to a covered cell is an error, and it recovers on unmerge

In `22`, `=I1` reads the merge anchor and returns 391, while `=J1` points at a covered cell
and is a **type 8** error. In `22b` that same formula becomes an ordinary type 2 cell holding
`0`, because J1 exists again.

So merge state directly determines whether a formula resolves. The error is not recorded as a
kind — consistent with the finding that error kinds are not stored — it simply becomes an
error cell and un-becomes one.

### ANSWERED: Numbers rewrites merge ranges on a structural edit

`23-row-inserted` takes `22` and inserts rows around the merged row.

```
22 (before)    5 merges, all at row 0
23 (after)    15 merges, next_formula_index 5 -> 15
               merges 0-4   now at row 1     THE ORIGINALS, REWRITTEN
               merges 5-9       at row 0     new, on an inserted row
               merges 10-14     at row 2     new, on an inserted row
```

So **"absolute" means absolute with respect to dragging a formula, not immune to structural
change.** The original five moved from row 0 to row 1 when a row was inserted above them, and
row 1 still holds all of `22`'s content with the same covered-column gaps. Merges track edits
correctly.

**Inserted rows inherit the merge pattern of the row they were created from**, which is why
five became fifteen. Rows 0 and 2 carry merges and no content at all, so **a merge can cover
entirely empty cells**: "is merged" and "has content" are independent properties, and a reader
must not infer either from the other.

`next_formula_index` went 5 to 15 — monotonic, never reusing an index.

### Rows and columns do NOT behave the same way

`24-column-inserted` repeats `23` sideways, and the results differ:

```
22 (before)   5 merges: cols [0..1] [2..3] [4..5] [6..7] [8..9]
24 (after)    5 merges: cols [0..1] [4..5] [8..9] [10..11] [12..13]
              next_formula_index STAYS 5
```

Existing merges shifted to their new columns correctly, but **no new merges were created** —
where inserting a row created ten. So an inserted **row** inherits the merge pattern of its
neighbour and an inserted **column** does not.

Had only one of the two been tested, the wrong rule would have been generalized to both. Any
structural operation in pybers has to be verified in both axes rather than assumed symmetric.

### The asymmetry this creates, which is the important part

**Reading is safe.** Any file Numbers wrote has correct merge ranges, because Numbers
maintains them.

**Writing is not.** If pybers inserts or deletes a row, *nothing* updates the merge ranges for
us. They are stored as absolute coordinates in a separate structure from the cells, so a
structural edit that ignores them leaves merges pointing at the wrong rows — and a merge
pointing past the end of the table is precisely the "phantom merge anchor" that raised
`ValueError: Value out of range` at save time in the defect recorded in `CLAUDE.md`.

That bug is now explained: it was not a quirk of merged cells, it was a structural edit that
did not maintain the merge store. Any row or column operation in pybers must update
`merge_owner.formula_store` in the same pass, or it is incorrect.

## Styles exist per BAND, not per row or column

`TST.TableModelArchive` carries a style reference for each band, and nothing else:

```
table_style          the whole table
body_cell_style      the default for every body cell
body_text_style      the default text for every body cell
header_row_style     the header-rows band     (+ header_row_text_style)
header_column_style  the header-columns band  (+ header_column_text_style)
footer_row_style     the footer-rows band     (+ footer_row_text_style)
```

There is **no per-row or per-column style reference for body rows.** Formatting body row 7
therefore writes a style onto each cell in it, and the fact that a whole row was selected is
not recorded anywhere — afterwards it is N cells that happen to match.

**Design consequence.** `setHeaderRowStyle(style)` is a genuine single-property operation
that round-trips as intent. A `setRowStyle(7, style)` would be sugar over N cell writes and
could never be read back as "row 7 is styled". The API should not make the two look alike.

Unverified: fixture `43-style-band-vs-row` exists in the list to confirm this by measurement
rather than leaving it as a reading of the schema.

## A table over 256 rows splits into tiles, and both facts about tiles are traps

From `27-big-table`, 2001 rows imported from a CSV. `TileStorage.tile_size` is **256**, and the
table splits into **8 tiles**. Every fixture before this one was single-tile, so neither of the
following had ever been visible.

### `tile_row_index` is LOCAL to its tile

Every tile reports rows `0..255` — the index restarts in each one:

```
tile 905818   256 rows, index 0..255
tile 907996   256 rows, index 0..255
tile 907995   209 rows, index 0..208
```

The document row is `tileid * tile_size + tile_row_index`. **Anything that reads "row 0" from a
multi-tile table gets eight different rows and no error**, which is the same silent-wrongness
this format specializes in.

### Tile archive identifiers are NOT in row order

```
tileid=0 -> 905818     tileid=1 -> 907996     tileid=2 -> 907997     tileid=3 -> 907991
tileid=4 -> 907992     tileid=5 -> 907993     tileid=6 -> 907994     tileid=7 -> 907995
```

`tileid=3` has a *lower* archive identifier than `tileid=1`. Iterating tile archives in file
order scrambles the table. **`TileStorage.tiles` is the authoritative order**, and the `tileid`
on each entry is what maps a tile to its row range.

`maxRow` reads 0 on every tile here, confirming again that it is not maintained.

## Sheets hold ordered DRAWABLES, and a table is one of them

From `25-two-tables`, which puts three tables on one sheet.

```
SheetArchive {
  name: "Sheet 1"
  drawable_infos: [905855, 907691, 908588]      ordered references
  in_portrait_page_orientation, print_margins, page_order, content_scale,
  headers, footers, print_backgrounds, ...
}
```

A table is not a special child of a sheet — it is a **drawable**, and the same list will hold
shapes, images and text boxes. Order is recorded, so it is part of the document and must be
preserved. The sheet also owns all page setup: orientation, margins, page order, scale,
headers and footers.

## Table geometry: tables are positioned, sized and rotatable

`TST.TableInfoArchive` wraps each table and its `super` carries the drawable properties:

```
geometry { position { x, y }  size { width, height }  angle  flags }
parent, exterior_text_wrap, locked, aspect_ratio_locked,
title, caption, title_hidden, caption_hidden
```

Measured across the three tables in `25`:

```
position (0, 0)          size 494 x 233
position (0.175, 68)     size 98 x 20.07
position (165.175, 0)    size 102 x 60
```

So placement and size are floating-point canvas coordinates, **`angle` means a table can be
rotated**, and `locked` and `aspect_ratio_locked` are real state. This validates the
`Position` and `Size` dataclasses already in `pybers.model.geometry`.

The `title` / `caption` / `title_hidden` / `caption_hidden` fields on the same block are the
settings switched off in every fixture in this directory, so the "atypical fixtures" note in
the README is visible right here.

**This substantially covers what `45-table-geometry` and `47-table-titles` were planned to
establish.** Those fixtures are now about *varying* these values rather than discovering them:
distinct column widths and row heights, and a table with its title and caption shown.

## Headers, footers and frozen panes are plain scalars

Also on `TST.TableModelArchive`, and simple enough to need no modeling beyond the values:

```
number_of_header_rows = 9      header_rows_frozen = 12
number_of_header_columns = 10  header_columns_frozen = 13
number_of_footer_rows = 11
repeating_header_rows_enabled = 29
repeating_header_columns_enabled = 32
```

**Freezing and repeating-on-print are different fields.** They are easy to conflate because
the Numbers UI presents both near each other, and conflating them would silently change print
behavior while appearing to set a view preference.

The presence of `HeaderStorageBucket-*.iwa` members in every fixture confirms header bands
have their own storage, not merely a count.

---

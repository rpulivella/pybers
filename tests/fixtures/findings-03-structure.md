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

The cells a merge covers have **no record in the tile at all**, indistinguishable from empty.
`spanCellType` is defined in `CellType` and is not used for this. So a reader cannot tell a
covered cell from an empty one by looking at the tile; it has to consult the merge ranges.
That makes merges essential to reading a table correctly, not an optional nicety.

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
kind (consistent with the finding that error kinds are not stored) it simply becomes an
error cell and un-becomes one.

**So merging is a recalculation event, and a writer that forgets this ships a wrong
number.** Added 2026-09-02 from PYB-16: writing the merge store alone leaves `L1` holding
whatever it resolved to before, so a file merged by this library displayed 0 where the
error belonged and an unmerged one displayed the error where 0 belonged. Numbers does not
notice on its own, for the same reason it does not notice an edited operand, see
`findings-02-formulas.md`. Every position whose merge state changed has to go into
`refs_to_dirty`, and then Numbers recomputes on open. Both directions are locked in by
`tests/golden/22b-merged-by-pybers.numbers` and its opposite.

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

`next_formula_index` went 5 to 15, monotonic, never reusing an index.

### Rows and columns do NOT behave the same way

`24-column-inserted` repeats `23` sideways, and the results differ:

```
22 (before)   5 merges: cols [0..1] [2..3] [4..5] [6..7] [8..9]
24 (after)    5 merges: cols [0..1] [4..5] [8..9] [10..11] [12..13]
              next_formula_index STAYS 5
```

Existing merges shifted to their new columns correctly, but **no new merges were created**,
where inserting a row created ten. So an inserted **row** inherits the merge pattern of its
neighbor and an inserted **column** does not.

Had only one of the two been tested, the wrong rule would have been generalized to both. Any
structural operation in pybers has to be verified in both axes rather than assumed symmetric.

### The asymmetry this creates, which is the important part

**Reading is safe.** Any file Numbers wrote has correct merge ranges, because Numbers
maintains them.

**Writing is not.** If pybers inserts or deletes a row, *nothing* updates the merge ranges for
us. They are stored as absolute coordinates in a separate structure from the cells, so a
structural edit that ignores them leaves merges pointing at the wrong rows, and a merge
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

### CORRECTED by `40-table-bands`: these are PARENT TEMPLATES, not applied styles

The reading above was from the schema and it was wrong in both halves. Measured against `40`:

**A band style is only a parent.** `header_row_style` is a root `CellStyleArchive`
(`is_variation: False`, `override_count: 4`) that no cell references directly. Every styled
cell (header, footer **and body**) carries its own reference to an anonymous *variation*
whose `parent` is the appropriate template:

```
header cell   -> #911973  variation, parent = header_row_style,   overrides cell_fill
footer cell   -> #912075  variation, parent = footer_row_style,   overrides cell_fill
body cell     -> #928722  variation, parent = the BODY style,     overrides cell_fill
plain body    -> no style reference at all
```

So formatting a header row and formatting a body row are **the same operation against
different parents**. Neither is a single-property band write, and the earlier design
consequence (that `setHeaderRowStyle` round-trips as intent while `setRowStyle` is sugar)
does not hold. Both are N cell writes.

**And there IS a per-row and per-column style slot**, in a place the schema reading missed:

```protobuf
message HeaderStorageBucket {
  message Header {
    required uint32 index = 1;
    required float  size = 2;
    required uint32 hidingState = 3;
    required uint32 numberOfCells = 4;
    optional .TSP.Reference cell_style = 5;
    optional .TSP.Reference text_style = 6;
  }
}
```

It is **unused** in the corpus: `40`'s deliberately-filled body row wrote per-cell styles and
left `cell_style` unset on the row. So the slot exists, Numbers did not use it for that
operation, and a reader must not depend on it being populated.

**A plain body cell carries no style reference at all.** Default body appearance is the
*absence* of a style, not a reference to a body style.

## Band membership: precedence, overlaps, and what survives un-setting

`40-table-bands` maxes every count, 5 header rows, 5 header columns, 5 footer rows on a
19x11 table, and labels the two overlap regions, so the corners can be attributed.

**Precedence is header row > header column > footer row.** Styling the header column left
the top-left corner on the header-**row** style; styling the footer left the bottom-left
corner on the header style. A corner belongs to the higher band, and styling a lower band
stops at the boundary rather than painting over it.

**Five is the maximum** for each of the three counts, bands always sit at the top, left and
bottom, and a band cannot be placed mid-table.

**A band has TWO templates, not one:** `header_row_style` for cell appearance and
`header_row_text_style` for text, each acting as a parent for its own kind of variation.

**The four cell templates differ in exactly one property.** Body, header row, header column
and footer row all carry identical `padding` (4 on every side), `text_wrap: True` and
`vertical_alignment: 0`; only `cell_fill` differs, and the body and footer fills are empty.
That is why removing a band changes less than expected.

**Un-setting a band re-parents its cells and preserves their overrides.** Setting header rows
from 5 back to 0 leaves each cell's explicit fill intact but re-parents its style from
`header_row_style` to the body style. The appearance the user chose survives; the band's own
default fill, its text-style parent, and the band effects (frozen, repeat-on-print) do not.
So band membership is **not** recoverable from cell styling after the fact.

### Freezing and repeat-on-print are independent fields

```
Table 1     header_rows_frozen UNSET   header_columns_frozen False
Table 1-1   header_rows_frozen True    header_columns_frozen True
BOTH        repeating_header_rows_enabled = True
            repeating_header_columns_enabled = True
```

`repeating_*` is `True` on both tables, including the one where `header_rows_frozen` is not
set at all. So the freeze control does not touch it, **repeat-on-print is print state**, set
elsewhere in the print layout UI, and a reader must not infer one from the other.

Print settings generally, along with pagination and per-object page position, are **not
covered by any fixture** and are real document state a round trip could silently drop.

## Row heights and column widths live in `HeaderStorageBucket`

Not on the table model, which carries only `default_row_height` and `default_column_width`.
Per-row and per-column state sits in `TST.HeaderStorageBucket`, one `Header` entry each:

```
index          the row or column number
size           its height or width  -- 0.00 means USE THE DEFAULT, not zero
hidingState    0 when visible
numberOfCells  how many cells that row or column holds
cell_style     optional, unused in the corpus
text_style     optional, unused in the corpus
```

**The two axes are reached differently.** `rowHeaders` is an inline `TST.HeaderStorage`
message on the data store, while `columnHeaders` is a `TSP.Reference` to one. A walker that
assumes both are references finds only the columns, silently.

`size = 0.00` reading as "default" rather than "zero" is the trap here: a reader that
propagates it literally collapses every row to nothing. Nothing in the corpus yet has a
resized or hidden row, so non-default values of `size` and `hidingState` remain unmeasured.

## A table over 256 rows splits into tiles, and both facts about tiles are traps

From `27-big-table`, 2001 rows imported from a CSV. `TileStorage.tile_size` is **256**, and the
table splits into **8 tiles**. Every fixture before this one was single-tile, so neither of the
following had ever been visible.

### `tile_row_index` is LOCAL to its tile

Every tile reports rows `0..255`, the index restarts in each one:

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

## A table declares its size, and it is often larger than its cells reach

From the whole corpus, measured 2026-09-01.

**`TableModelArchive.number_of_rows` and `number_of_columns` are explicitly set on all 74
tables**, and they are the table's real size. A Numbers table is a fixed grid rather than the
endless sheet Excel presents, so an address beyond it names nothing at all rather than naming
an empty cell.

Deriving the size from the cells that hold something instead returns a real rectangle that is
too small on **7 of those 74 tables**:

```
00-baseline                declared=(1, 1)   cells reach=(0, 0)
20-formula-shapes          declared=(10, 5)  cells reach=(1, 1)
20-formula-shapes          declared=(10, 5)  cells reach=(1, 1)
29-style-border            declared=(2, 9)   cells reach=(1, 8)
30-style-align             declared=(3, 9)   cells reach=(3, 8)
42-table-titles-captions   declared=(1, 1)   cells reach=(0, 0)
42-table-titles-captions   declared=(1, 1)   cells reach=(0, 0)
```

Every gap is ordinary: an empty trailing column, or a 10 by 5 table holding one value. The
derived rectangle is a perfectly plausible one, which is the usual shape of a mistake in this
format.

**No cell record anywhere in the corpus falls outside its table's declared size**, so the
declaration and the tiles agree and the declaration can be read as authoritative rather than
as a hint to be checked against the data.

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

A table is not a special child of a sheet. It is a **drawable**, and the same list will hold
shapes, images and text boxes. Order is recorded, so it is part of the document and must be
preserved. The sheet also owns all page setup: orientation, margins, page order, scale,
headers and footers.

### Print and page setup: unexercised, and MUST NOT BE BROKEN

No fixture tests any of this, and none is planned, Numbers' page-layout tools are a real
differentiator and reproducing them is out of scope. But every sheet in every fixture already
carries the state, so a writer that does not round-trip it damages documents it never
intended to touch:

```
in_portrait_page_orientation   print_margins { top 54 left 36 bottom 54 right 36 }
content_scale 0.72             page_order          layout_direction
show_page_numbers              using_start_page_number / start_page_number
page_header_inset 20.0         page_footer_inset 20.0
uses_single_header_footer      print_backgrounds   should_print_comments
is_autofit_on                  userDefinedGuideStorage    style
headers: [3 references]        footers: [3 references]
```

**`headers` and `footers` are three references each** (left, center and right) and they
point at real `TSWP.StorageArchive`s. Those are the six otherwise-unexplained storages that
appear in every document in this corpus. They hold **editable text**, so a writer that
regenerates storages rather than carrying them through can silently erase a document's page
headers.

Document-level metadata is the same category: `TN.DocumentArchive`, `TN.ThemeArchive`,
`TSP.DocumentMetadata`, `TSP.PackageMetadata`, `TSP.DataMetadata` / `DataMetadataMap`, and
`TSK.AnnotationAuthorStorageArchive` (comment authorship). None is decoded and none needs to
be, the requirement is only that they survive untouched.

This is the same duty the cell decoder already honors by preserving an unrecognized type byte
rather than rejecting it: **a library whose first job is not to damage documents has to carry
through what it does not understand.**

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

So placement is in **points**, the same unit as every other coordinate, `41-table-geometry`
labels its tables and they read exactly: `(144, 144)` is "x2.0in y2.0in", `(-72, 360)` is
"x-1.0in y5.0in". **A table may sit at a negative position**, off the left edge of the sheet.
`angle` means a table can be rotated, and `locked` and `aspect_ratio_locked` are real state.

The `title` / `caption` / `title_hidden` / `caption_hidden` fields on the same block are the
settings switched off in every fixture in this directory, so the "atypical fixtures" note in
the README is visible right here.

### A table's `geometry.size` is STALE and must never be used

The single most dangerous finding about tables. `41` builds a chain of eight tables, each
duplicated from the last and then resized, and every one of them stores a `geometry.size`
that describes the **previous** table:

```
table                  own content     geometry.size    predecessor content + 4
Table 1-1              216 x 112       220 x 116        220 x 116     MATCH
Table 1-1-1            360 x 180       220 x 116        220 x 116     MATCH
Table 1-1-1-1          360 x 72        364 x 184        364 x 184     MATCH
Table 1-1-1-1-1        360 x 360       364 x 76         364 x 76      MATCH
Table 1-1-1-1-1-1       72 x 216       364 x 364        364 x 364     MATCH
Table 1-1-1-1-1-1-1    360 x 216        76 x 220         76 x 220     MATCH
```

Six for six. `geometry.size` records the content size plus about 4 points of frame **at the
moment the table was created**, and is **never updated when rows or columns are resized**.

**The real size is `sum(row heights) x sum(column widths)`**, taking `default_row_height` and
`default_column_width` wherever a `size` reads `0.00`. A reader that trusts `geometry.size`
gets a plausible wrong number (off by a factor of five in the worst row above) with nothing
raising.

### Resizing a table distributes the stretch PROPORTIONALLY into rows and columns

Nothing about the stretch is recorded at the table level. Dragging a table's frame multiplies
every row height, or every column width, by the same factor and writes the results back into
`HeaderStorageBucket`:

```
12, 12, 24, 12, 12    sum  72
60, 60, 120, 60, 60   sum 360     every row x 5.0 exactly
36, 36, 72, 36, 36    sum 216     every row x 0.6 exactly
```

Afterwards a proportional stretch is **indistinguishable** from having typed those heights by
hand, so the operation cannot be recovered, only its result.

## A table's TITLE is its NAME, and names are forced unique per SHEET

From `42-table-titles-captions`. There is no separate title field: what the interface shows
above a table is **`table_name`**, and `table_name_enabled` is the checkbox that shows it.

```
table_name = 'I am a table Title'      table_name_enabled = True      title shown
table_name = 'I am a table Title-2'    table_name_enabled ABSENT      title hidden
```

The fixture's own cells state the constraint, and the eight table names confirm it:
**table names must be unique within a sheet, and uniqueness is enforced
case-insensitively**, `I am a Table` and `I AM a TAAble` are treated as the same. Numbers
appends `-1`, `-2`, `-1-1` to force it. A writer that renames a table has to enforce the same
rule or it will produce a document Numbers itself would not have written.

**Corrected 2026-09-01: the scope is the sheet, not the document.** This section read "unique
within a document", generalized from `42`, whose eight tables all sit on one sheet.
`20-formula-shapes` disproves that reading directly: it carries `Table 1` on Sheet 1 and
another `Table 1` on Sheet 2, in one document, with `Table 2` alongside the first. So a name
identifies a table within its own sheet and nowhere wider, and a lookup that takes a table
name has to be reached through the sheet that holds it.

`table_name_height` is `0.0` throughout, the same "use the default" convention as row heights.

**The title sits in negative page space**, above the table's own origin, one fixture table
is at `y = -28.0` with the title rendered above it. So a table's visible extent is larger
than its geometry when the name is shown.

### The title is a text container, styled like any other

```
table_name_style       -> TSWP.ParagraphStyleArchive  name='Table Title 1'
                          full char + para properties
table_name_shape_style -> TSWP.ShapeStyleArchive
                          vertical_alignment, padding
```

Two styles, exactly as a text box has: a paragraph style for the text and a shape style for
the container. Note that `Table Title 1` exists as six separate archives, one per table slot,
and is **not** visible in the styles browser, see the registry finding in
[findings-06-styles.md](findings-06-styles.md).

## A caption IS a text box

`TSA.CaptionInfoArchive` sits in the drawable's `caption` slot, and its `super` is a
**`TSWP.ShapeInfoArchive`**, the same archive a floating text box uses, with `is_text_box`
and `owned_storage`:

```
CaptionInfoArchive {
  super: TSWP.ShapeInfoArchive     the text box itself
  placement: TSA.CaptionPlacementArchive
  childInfoKind: Caption           the SAME archive type also serves titles
}
```

An uncaptioned drawable carries `TSD.StandinCaptionArchive` in that slot instead, the empty
placeholder from `33`. So the slot is always occupied and only its *type* says whether a
caption exists.

**Captions are NOT forced unique**, unlike table names; the fixture has three reading
`'I am a table caption'`.

Placement is anchor-based and identical on every caption measured,
`caption_anchor_location: 1`, `drawable_anchor_location: 7`, which matches the fixture's
observation that there is no way to set the gap between table and caption.

### Text inset lives on the SHAPE style, not the paragraph style

`42` proves this with a controlled pair: two captions sharing the paragraph style
`'Special Caption'` but differing in inset.

```
custom inset      para 'Special Caption'   shape #914776   padding 1/1/1/1
default inset     para 'Special Caption'   shape #904525   padding 4/4/4/4
```

Same named paragraph style, different shape styles. So **an inset does not travel with a
named paragraph style**, applying that style elsewhere will not carry the inset with it, and
a model that folds padding into the text style will get this wrong.

`TSWP.ShapeStylePropertiesArchive` also carries `shrink_to_fit`, `vertical_alignment`, a
`paragraph_style` reference for the container default, and **`columns`**, text containers
support multiple text columns. Every instance in the corpus reads
`equal_columns { count: 1 }`, so multi-column text is representable and **unexercised**.

## Hiding a row or column: by UUID, and not where the field name suggests

`41` hides one row and one column and labels both. Three things follow, none of them
guessable.

**`HeaderStorageBucket.hidingState` is NOT user hiding.** It reads `0` on the hidden row and
the hidden column alike, on every table in the corpus. Whatever it is for, it is not this.

**Hidden state lives on the table model, addressed by UUID:**

```
TableModelArchive.hidden_states_owner.hidden_states[]
   .row_hidden_state_extent.base_hidden_states[]
        row_or_column_uid { lower, upper }
        user_hidden: true
   .column_hidden_state_extent.base_hidden_states[]   ... same shape
```

A table with nothing hidden has the same structure with `base_hidden_states` **empty**. Every
table also carries a `HiddenStateFormulaOwnerArchive` and a `FilterSetArchive` whether or not
anything is hidden, so their presence proves nothing, only a non-empty `base_hidden_states`
does.

**Rows and columns are identified by UUID, not index**, the same identity-based design that
makes cross-table formula references survive edits. Resolving a UUID to an index needs
`base_column_row_uids` -> `TST.ColumnRowUIDMapArchive`, and its `*_uid_for_index` is a
**permutation** into `sorted_*_uids`:

```
column uid_for_index = [1, 2, 0]                the hidden uid sits at sorted[2]
                                                which is column index 1, NOT 2
row    uid_for_index = [1, 6, 2, 3, 5, 4, 0]    the hidden uid is row index 3
```

Reading the sorted list positionally reports the wrong column. **Sorted order is not document
order** and the map has to be applied.

`user_hidden` distinguishes manual hiding from filter hiding, which is the sibling
`filter_set` mechanism (`is_enabled: False` throughout the corpus). A row can therefore be
hidden two independent ways, and a hidden row **keeps its `size`**, hiding does not zero the
height.

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

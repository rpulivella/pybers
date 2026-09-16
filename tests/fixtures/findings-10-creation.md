# Creation: what Numbers writes for a new sheet and a new table

Every archive this library wrote before PYB-63 already existed. A new sheet or table is
built from nothing, so each fact here decides what a created archive must carry for Numbers
to accept it. Measured for PYB-63 from `48-table-inserted` and the fixtures derived from it.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## Every member is a component, and its strong references are derived

`Index/Metadata.iwa` holds one `TSP.PackageMetadata`. Each IWA member is a component in it,
named by `locator`, or by `preferred_locator` when the member carries no suffix, and the
component's identifier is its root archive's.

**A component's strong external references are exactly what its archives reference in other
components.** Measured across all 51 fixtures on 2026-09-14: collect each archive's
`ArchiveInfo.object_references`, keep the targets held by another component, and name the
object as 0 when it is that component's root. The result equals every component's stored
strong references, with no exception. Everything stored beyond that is marked `is_weak`, and
no schema marks a reference weak, so weak references cannot be derived. A table's `parent`
sheet, for one, never appears in `object_references`.

The same fixtures place every archive outside `Metadata.iwa` in exactly one component.
`tests/test_persistence_metadata.py` sweeps both properties.

## A new sheet

`48` → `49` adds nine archives, all in `Index/Document.iwa`: the `TN.SheetArchive`, a
`TSD.GuideStorageArchive`, six `TSWP.StorageArchive`s for the left, center and right headers
and footers, and a `TSWP.NumberAttachmentArchive` holding the page number Numbers puts in the
center footer. The document component gains a UUID for the sheet, the guides and the six
storages. `DocumentArchive.sheets` gains the sheet at its tab position, and the sidebar tree
gains a `TSK.TreeNode` naming it.

A sheet Numbers creates carries different page setup from the template's first sheet:

```
                      first sheet    inserted sheet
is_autofit_on         false          true
content_scale         0.72           -1.0 (automatic)
print_margins         54 36 54 36    72 72 72 72
page_header_inset     20             18
```

The one engine owner `49` gained is left over from the default table Numbers put on the new
sheet, which was then deleted. An empty sheet itself registers nothing in the engine.

**Numbers cannot make a sheet without a background.** Confirmed in the interface on
2026-09-14: neither No Fill nor a transparent color is accepted. The theme's sheet style
fills white, and every sheet shares it by reference.

## A new table

`48` → `50` inserts a 3 by 4 table beside an existing one, and `51` pastes a copy.

**The inserted table is the existing one with every name changed.** Its 49 archives match
`Table 1`'s one for one. After renumbering, 41 of them are identical in content, and
the rest differ only in UUIDs, `table_id`, the name and the position. The member files are 2
tiles, 23 data lists and 4 header buckets, each a new component. Twenty archives join
`CalculationEngine.iwa`.

**Every owner UUID a table has is one base plus a fixed offset.** The engine registers 11
formula owners per table. The owner of kind 1 carries the base itself, and every other
owner carries the base plus its `owner_kind`. The model's `conditional_style_formula_owner_id` is base plus 3, `merge_owner`
base plus 5, the hidden states base plus 4, and `haunted_owner` base plus 35. The four-word
and two-half spellings are the same value.

**A table's styles come from the theme's first table style preset.** The 27 stylesheet
references of an inserted table are exactly the network of
`TN.ThemeArchive`'s first `TST.TableStylePresetArchive`, so a table can be created in a
document holding no table at all.

The header name manager gives each table a slot, `per_table_precedent.column`, one above the
highest in use, registered as a cell record on the owner of kind 200.

**A second table on a sheet turns on the first table's title.** Both `50` and `51` set
`table_name_enabled` on `Table 1`. A pasted table whose name clashes, ignoring case, is
suffixed `-1`, so `51` holds `Table 1` and `Table 1-1`.

Only four kinds of field depend on the table's size: `number_of_rows` and
`number_of_columns`, the column and row UID map, the stroke sidecar's counts, and the layout
hint on `TST.TableInfoArchive`.

## The reset, as Numbers encodes it

`52-table-reset-styled` applies the pybers reset through the interface. Numbers writes three
variations and applies them cell by cell:

```
table style      parent: theme table style
                 v_strokes_visible false, h_strokes_visible false,
                 table_border_visible false
paragraph style  parent: Table Style 2
                 AvenirNext-Regular, 11 pt, kExactLineSpacing 15.5
cell style       parent: body cell style
                 text_wrap false
```

The table style variation is set in `TableModelArchive.table_style` itself. The text and cell
variations reach the cells only through each cell record, with 14 stroke layers alongside,
and the model's `body_text_style` and `body_cell_style` are left as they were. Row and column
sizes go into the header buckets, and `default_row_height` does not change.

`53-paragraph-style-named` names the text style `pybers-base`. Numbers replaces the
variation with a named root style, which carries every character and paragraph property
resolved and is listed in `TN.ThemeArchive.paragraph_style_presets`. All 12 cells then
name it directly.

**Numbers cannot create a table style or a cell style.** Only paragraph styles can be
created in the interface, so a table-level reset has no Numbers-made example to copy.

## What registering a created table touches beyond its own archives

Two of a table's references are weak, and neither shows in `object_references`:
`TableModelArchive.table_style_preset`, naming the theme's preset, and
`TableInfoArchive.super.parent`, naming the sheet. The calculation engine's component lists
both as weak external references.

The engine's owner of kind 8 records its edge to the owner of kind 35 as an integer,
`internal_owner_id_for_edge`, and each dependency tile names its owner the same way, so an
internal owner id is renumbered inside archive bodies as well as in `owner_id_map`. Those
records are identical in every fixture whatever the table's size.

`number_of_formulas` grows by four per table: 7 for one, 15 for three, 39 for nine.

## What registering a created style touches

A style is appended to `StylesheetArchive.styles` and given a UUID in the stylesheet's
component. A variation also gets an entry in `parent_to_children_style_map`. A named style
also gets an `identifier_to_style_map` entry keyed by its `style_identifier`, which Numbers
wrote as `text-0-paragraphstyle`, and a place in the theme's
`TSWP.ThemePresetsArchive.paragraph_style_presets`. Numbers leaves entries in `styles` for
styles it has since culled, 58 added against 12 surviving in `28-style-fills`, so the list is
appended to and never read as an inventory. The `styles_for_*` lists do not change.

## A first value in an empty table

A created table stores no row and no record, so neither can be copied. Numbers' first row in
an empty tile carries 255 narrow offset slots at storage version 5, identical in
`01-text-plain`, `11-value-types-noformats` and `18-formula-literals`. Its plain number
record, `42` in `20-formula-shapes`, carries two trailing references, both keys into the
table's format list, and the automatic number format they name is the same `256` entry in
`11` and `20`: `decimal_places` 253, `negative_style` 0, no thousands separator.

## Row height as Numbers draws it

A created table stores 24 pt rows, one line of 11 pt text on exact 15.5 pt spacing inside
4 pt padding, 23.5 pt in all. Numbers draws those rows at its fitted height, about 24.43 pt,
and reports 0.34 in. `52-table-reset-styled` stored the same 24.43 as its fitting size. The
roughly 0.93 pt beyond 23.5 is Numbers' text layout rather than rounding. Whether a cell
border adds to the fit was unmeasured as of 2026-09-14, and belongs to PYB-87.

## The first formula in a table

`48` → `55-table-inserted-formula` types `2` into `A1` and `=A1*3` into `B1` of the
inserted table, whose owner of kind 1 held no dependency tile. Measured for PYB-86 on
2026-09-15.

**Numbers creates the tile.** One `TSCE.CellRecordTileArchive` joins
`CalculationEngine.iwa`, in the component already holding the owner, so no external
reference changes. It carries the owner's `internal_owner_id`, begins at column 0 and
row 0, and holds the same cell record as the owner's `cell_dependencies`. The owner lists
it in `tiled_cell_dependencies` and names it as a strong object reference.

**The record carries the precedent as an edge.** `B1`'s record holds
`edge_without_owner_rows: 0` and `edge_without_owner_columns: 0`, naming `A1`. pybers
writes an empty edge set, as it does for every formula. Whether Numbers then recalculates
`B1` when `A1` is edited is what the golden `20-formulas-in-created-tables` settles.

## `table_id` is the table's identity, and the engine is reached through it

**`TableModelArchive.table_id` is the table's formula-owner identity, spelled as a
canonical uppercase UUID.** It matches in every table of every fixture: the identity's
four words, each written low byte first, are the UUID's sixteen bytes. pybers wrote a
fresh unrelated UUID there until 2026-09-16, and the cost was the whole calculation
engine registration.

Numbers opens such a document without a prompt, then **re-identifies the table**: it mints
a fresh owner base, creates new owners of kind 1, 6 and 8, rewrites the group-by and
tracked-reference UUIDs to that base, and drops every dependency tile, leaving pybers'
owners registered and inert. Nothing warns. A formula in the table is never evaluated and
shows a warning triangle with no message, a reference to the table from elsewhere reads
`The formula contains an invalid reference`, and re-entering the formula by hand makes
that one cell compute.

Measured for PYB-86 by bisection: a created table holding no formula is repaired the same
way, a formula pybers writes into a table Numbers made evaluates correctly, and the repair
is indifferent to the pybers reset styles, to row height and column width, and to the
table title. Everything else about a created table already matched a Numbers-inserted one,
archive for archive.

Two consequences follow. A table identity is a **version 4 UUID in file byte order**,
which is what `table_id` spells, and every identity in the fixtures reads as one. The
header name manager's slot record for a table carries an **edge on cell (0, 0)**, as every
slot Numbers writes does. Neither was the cause, and both are now what pybers writes.

The same save raises `number_of_formulas` from 7 to 8 and drops `owner_id_map` entry 34,
which no owner archive names. `49` and `50` drop it too, so it is a leftover Numbers culls
on any save rather than part of the edit.

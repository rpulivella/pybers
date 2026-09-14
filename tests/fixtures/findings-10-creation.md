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
formula owners per table, and each owner's UUID is the table's base UUID plus its
`owner_kind`. The model's `conditional_style_formula_owner_id` is base plus 3, `merge_owner`
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

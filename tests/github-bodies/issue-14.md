As a Python developer I want to reach a sheet or a table by its name or its position, and to walk every cell in a document in a defined order, so that a script can act on a whole document without digging through lists to find what it is acting on.

1. `Document.sheet` returns a sheet by name or by position, and `Sheet.table` returns a table the same two ways.
   1. Position counts from one, matching the rest of the model.
   1. `Document.sheets` and `Sheet.tables` remain, so an ordinary loop still works.
2. Position means the document's own order rather than any ordering this library invents.
3. A name that no sheet or table carries raises an error naming what was asked for and listing what is present.
   1. Matching a table name ignores case, because Numbers itself treats two names differing only in case as the same name and will not create both.
4. A name carried by two sheets, or by two tables on one sheet, raises rather than returning whichever comes first.
5. A document walks its own cells in a defined order: sheets in document order, tables in sheet order, and cells row by row and left to right within each table.
   1. Each cell arrives with the table holding it, so a script can tell two cells with the same reference in different tables apart.
   1. The walk covers cells that exist. Covering an empty rectangle as well is a different request and is spelled differently.
6. The walk is enough on its own to drive a whole-document edit: read each cell's value and type, change it, keep a running count across every sheet, and have the order hold across a save and a reopen.

## SPEC

- **Order comes from the file's own lists.** Sheets are `TN.DocumentArchive.sheets`, which is the tab order a person sees, confirmed against `26-multi-sheets`. Tables are `TN.SheetArchive.drawable_infos`. Neither list is sorted, and neither may be re-derived from names or from positions on the canvas.
- **A table's position is its place in the drawable list, not its place on the sheet.** `25-multi-tables` returns `Table 1`, then `Lower`, then `Right`, so an index says nothing about where a table sits. A caller expecting top-to-bottom gets a real table that is the wrong one.
- **A table name is unique within its sheet and nowhere wider.** Numbers enforces this and appends `-1`, `-2`, `-1-1` to force it, visible across the eight tables of `42-table-titles-captions`, and the fixture's own cells state that the enforcement is case-insensitive. It does not extend to the document: `20-formula-shapes` carries `Table 1` on Sheet 1 and another `Table 1` on Sheet 2. So `Sheet.table` by name is unambiguous and a document-wide table lookup by name is not, which is why this ticket offers only the first. See `findings-03-structure.md`, whose earlier claim of document-wide uniqueness was corrected on 2026-09-01 by that fixture.
- **Sheet name uniqueness is an observation rather than a measured rule.** No document in the corpus holds two sheets sharing a name, and nothing shows Numbers enforcing it, so AC 4 covers the case rather than assuming it cannot arise.
- **Cells are sparse.** Only a populated cell has a record in a tile, and a covered cell of a merge has none at all, so a walk over stored cells and a walk over a rectangle are two different traversals. `Table.extent` is what turns the second into the first.

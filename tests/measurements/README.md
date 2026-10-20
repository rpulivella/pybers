# Measurements: one change from an origin

A measurement is a document made from another document here by exactly one change, so that a
diff against its origin shows where that change lives. Origins are in
[`tests/fixtures/`](../fixtures/README.md). What each established is indexed in
[FINDINGS.md](../../docs/findings/FINDINGS.md).

## Making one

- **Save As from the origin, then make one change.** A new document renumbers every object
  identifier, so it cannot be compared; a Save As copy kept 36 of 37 members named alike.
- **A star, not a chain.** Derive from the origin directly, never from the previous
  measurement, or isolating one change means unpicking the ones before it.
- **Label what each cell displays**, in text beside it. What was typed cannot be recovered
  from the file, and `13-number-percent` showed the two can differ.
- Preview images and selection archives change on every save and mean nothing.
- Saved from the Numbers release `src/pybers/protos/README.md` records, or a later one pybers
  reads, which the catalog row then names.

## Catalog

| Document | Origin | The one change | Finding |
| --- | --- | --- | --- |
| `01-text-plain` | `00-baseline` | a plain string, which creates no archives | [text](../../docs/findings/findings-04-text.md) |
| `02-text-rich` | `00-baseline` | four differently formatted runs in one cell | [text](../../docs/findings/findings-04-text.md) |
| `03-text-multiline` | `00-baseline` | two paragraphs in one cell | [text](../../docs/findings/findings-04-text.md) |
| `04-text-monospace` | `00-baseline` | a font change over a whole cell | [text](../../docs/findings/findings-04-text.md) |
| `05-opentype` | `00-baseline` | ten character styles carrying OpenType features | [text](../../docs/findings/findings-04-text.md) |
| `06-strikethrough` | `00-baseline` | strikethrough over a whole cell | [text](../../docs/findings/findings-04-text.md) |
| `07-text-superscript` | `00-baseline` | synthetic superscript beside the real OpenType feature | [text](../../docs/findings/findings-04-text.md) |
| `08-text-para-backgrounds` | `00-baseline` | a text background at paragraph and at character scope | [text](../../docs/findings/findings-04-text.md) |
| `09-text-capitalization` | `00-baseline` | all caps | [text](../../docs/findings/findings-04-text.md) |
| `10-text-ligatures` | `00-baseline` | ligatures off on a paragraph, overridden on some letters | [text](../../docs/findings/findings-04-text.md) |
| `11-value-types-noformats` | `00-baseline` | one cell of every value type, labeled | [values](../../docs/findings/findings-01-values.md) |
| `12-number-currency` | `00-baseline` | nine currency formats beside a plain number | [values](../../docs/findings/findings-01-values.md) |
| `13-number-percent` | `00-baseline` | percent formats | [values](../../docs/findings/findings-01-values.md) |
| `14-number-date` | `00-baseline` | date and time formats | [values](../../docs/findings/findings-01-values.md) |
| `15-number-duration-formats` | `00-baseline` | one duration in every duration format | [values](../../docs/findings/findings-01-values.md) |
| `16-number-scientific-numeralsystems` | `00-baseline` | scientific notation and numeral systems | [values](../../docs/findings/findings-01-values.md) |
| `17-number-custom` | `00-baseline` | a custom format with positive, negative and zero forms | [values](../../docs/findings/findings-01-values.md) |
| `18-formula-literals` | `00-baseline` | formulas computed from literals only | [formulas](../../docs/findings/findings-02-formulas.md) |
| `19-formula-dragged` | `00-baseline` | relative, locked and mixed references, dragged down a row | [formulas](../../docs/findings/findings-02-formulas.md) |
| `20-formula-shapes` | `00-baseline` | ranges, nesting, whole columns, and references across tables and sheets | [formulas](../../docs/findings/findings-02-formulas.md) |
| `21-formula-errors` | `00-baseline` | broken references, an unknown function, and circularity | [formulas](../../docs/findings/findings-02-formulas.md) |
| `22-merge-2x2` | `00-baseline` | five merges, two over content, read by formulas | [structure](../../docs/findings/findings-03-structure.md) |
| `22b-merge-2x2-unmerged` | `22-merge-2x2` | every merge removed | [structure](../../docs/findings/findings-03-structure.md) |
| `23-row-inserted` | `22-merge-2x2` | rows inserted around the merged row | [structure](../../docs/findings/findings-03-structure.md) |
| `24-column-inserted` | `22-merge-2x2` | columns inserted through the merges | [structure](../../docs/findings/findings-03-structure.md) |
| `25-multi-tables` | `00-baseline` | more tables on one sheet | [structure](../../docs/findings/findings-03-structure.md) |
| `26-multi-sheets` | `00-baseline` | three sheets, with a tab color and a background | [structure](../../docs/findings/findings-03-structure.md) |
| `28-style-fills` | `00-baseline` | ten fills, including three image fills of `tile-pattern.png` | [styles](../../docs/findings/findings-06-styles.md) |
| `29-style-border` | `00-baseline` | cell borders, a table outline, gridlines and banding | [styles](../../docs/findings/findings-06-styles.md) |
| `30-style-align` | `00-baseline` | horizontal and vertical alignment and wrap | [styles](../../docs/findings/findings-06-styles.md) |
| `31-style-inset-2pt` | `00-baseline` | cell insets and paragraph indents | [styles](../../docs/findings/findings-06-styles.md) |
| `32-named-styles` | `00-baseline` | a named style applied, and formatting over it | [styles](../../docs/findings/findings-06-styles.md) |
| `33-textbox` | `00-baseline` | text boxes nudged, flipped and rotated | [drawables](../../docs/findings/findings-07-drawables.md) |
| `34-shape` | `00-baseline` | nine shape kinds sharing styles | [drawables](../../docs/findings/findings-07-drawables.md) |
| `35-image` | `00-baseline` | `orientation-test.png` and `tile-pattern.png` in thirteen placements | [drawables](../../docs/findings/findings-07-drawables.md) |
| `36-unicode-text` | `00-baseline` | accented, CJK, astral, emoji and right-to-left text | [text](../../docs/findings/findings-04-text.md) |
| `37-text-baselineshift` | `00-baseline` | baseline shift, and line spacing modes | [text](../../docs/findings/findings-04-text.md) |
| `38-text-outline-shadow` | `00-baseline` | text outlines in every dash and brush, and shadows | [text](../../docs/findings/findings-04-text.md) |
| `39-text-tabs-indents` | `00-baseline` | tab stops and indents on a cell and on a paragraph | [text](../../docs/findings/findings-04-text.md) |
| `40-table-bands` | `00-baseline` | header, footer and frozen bands, set and unset | [structure](../../docs/findings/findings-03-structure.md) |
| `41-table-geometry` | `00-baseline` | tables resized, moved, and a row and a column hidden | [structure](../../docs/findings/findings-03-structure.md) |
| `42-table-titles-captions` | `00-baseline` | table titles and captions | [structure](../../docs/findings/findings-03-structure.md) |
| `43-stroke-dashes` | `00-baseline` | every dash preset at 1pt and 5pt | [drawables](../../docs/findings/findings-07-drawables.md) |
| `44-line-ends` | `00-baseline` | connectors attached to shapes | [drawables](../../docs/findings/findings-07-drawables.md) |
| `46-formula-rare-functions` | `27-big-table` | rare functions typed over labels rewritten by a script | [formula text](../../docs/findings/findings-08-formula-text.md) |
| `49-sheet-inserted` | `48-table-inserted` | a sheet inserted | [creation](../../docs/findings/findings-10-creation.md) |
| `50-table-inserted-beside` | `48-table-inserted` | a table inserted beside the existing one | [creation](../../docs/findings/findings-10-creation.md) |
| `51-table-pasted-name-clash` | `48-table-inserted` | the table copied and pasted | [creation](../../docs/findings/findings-10-creation.md) |
| `54-format-star-rating` | `00-baseline` | a star-rating control and a label | [values](../../docs/findings/findings-01-values.md) |
| `54b-format-star-rating-released` | `54-format-star-rating` | the control's format set to Text, and the label retyped | [values](../../docs/findings/findings-01-values.md) |
| `54c-format-star-rating-cleared` | `54-format-star-rating` | Clear All on `A1:A2` | [values](../../docs/findings/findings-01-values.md) |
| `55-table-inserted-formula` | `48-table-inserted` | `2` in `A1` and `=A1*3` in `B1` | [creation](../../docs/findings/findings-10-creation.md) |
| `56-structure-base` | `00-baseline` | labeled formulas, five merges, a second table reading the first, built by a script, then row 9 and column H hidden by hand | [structure](../../docs/findings/findings-03-structure.md) |
| `56b-row-inserted` | `56-structure-base` | Add Row Above row 3 through AppleScript, which Numbers widened to two rows over the merge `C2:D3` | [structure](../../docs/findings/findings-03-structure.md) |
| `56c-row-deleted` | `56-structure-base` | Delete Row 3 through AppleScript, widened to rows 2 and 3 | [structure](../../docs/findings/findings-03-structure.md) |
| `56d-column-inserted` | `56-structure-base` | Add Column Before column E through AppleScript, widened to five columns over the merges | [structure](../../docs/findings/findings-03-structure.md) |
| `56e-column-deleted` | `56-structure-base` | Delete Column E through AppleScript, widened to columns C to G | [structure](../../docs/findings/findings-03-structure.md) |
| `56f-row-inserted-in-merge` | `56-structure-base` | `A3` selected alone, then Add Row Above, cutting through `C2:D3` | [structure](../../docs/findings/findings-03-structure.md) |
| `56g-row-deleted-in-merge` | `56-structure-base` | `A3` selected alone, then Delete Row, cutting through `C2:D3` | [structure](../../docs/findings/findings-03-structure.md) |
| `56h-row-8-deleted` | `56-structure-base` | Delete Row 8 through AppleScript, which breaks the locked `$A$8` and the unlocked `A8` | [structure](../../docs/findings/findings-03-structure.md) |
| `27b-rows-inserted-into-a-new-tile` | `27-big-table` | 60 rows added above row 100 through AppleScript, which pushes the last rows into a ninth tile | [structure](../../docs/findings/findings-03-structure.md) |
| `27c-rows-deleted-emptying-a-tile` | `27-big-table` | rows 1 to 300 deleted through AppleScript, which leaves the last tile empty | [structure](../../docs/findings/findings-03-structure.md) |
| `57-structure-refusals-base` | `00-baseline` | six tables, one per kind of state a structural edit has to carry: borders, conditional highlighting, bands, volatile formulas and spills, and merges to cut. Built by a script, then the borders and the highlighting added by hand | [structure](../../docs/findings/findings-03-structure.md) |
| `57-borders-*` | `57-structure-refusals-base` | a row and a column added and removed in `Borders`, which carries a border on every edge | [structure](../../docs/findings/findings-03-structure.md) |
| `57-conditions-*` | `57-structure-refusals-base` | the same four edits in `Conditions`, whose second rule reads `$C$1`, the cell the column deletion takes | [structure](../../docs/findings/findings-03-structure.md) |
| `57-bands-*` | `57-structure-refusals-base` | six edits in `Bands`, inside and beside its two header rows, its header column and its footer | [structure](../../docs/findings/findings-03-structure.md) |
| `57-engine-*` | `57-structure-refusals-base` | four edits in `Engine`, which holds `NOW()`, `RAND()` and two spills | [structure](../../docs/findings/findings-03-structure.md) |
| `57-anchors-*`, `57-collapse-*` | `57-structure-refusals-base` | a merge losing its anchor's line, and one left a single cell, each from a single selected cell so Numbers does not widen the selection | [structure](../../docs/findings/findings-03-structure.md) |
| `58-buckets-base` | `27-big-table` | the row count set to 100,000 through AppleScript and values written at twelve rows either side of 65,536, giving sixteen row-header buckets and a sparse run of tiles | [structure](../../docs/findings/findings-03-structure.md) |
| `58-buckets-row-inserted` | `58-buckets-base` | a row added above row 1, which carries row 65,536 into the second bucket | [structure](../../docs/findings/findings-03-structure.md) |
| `58-buckets-row-deleted` | `58-buckets-base` | row 1 deleted, which carries row 65,537 back into the first bucket | [structure](../../docs/findings/findings-03-structure.md) |
| `58-buckets-at-limit` | `27-big-table` | the row count set to 65,536, the most one bucket holds. Numbers marks the tile wide and leaves its rows narrow | [structure](../../docs/findings/findings-03-structure.md) |
| `58-buckets-created` | `58-buckets-at-limit` | a row added above row 1, which leaves 65,537 rows in the one bucket where setting the count would have made sixteen | [structure](../../docs/findings/findings-03-structure.md) |
| `59-conditions-relative-base` | `00-baseline` | column A rising, B falling and C constant, built by a script, then three highlighting rules added by hand: A reading `B1` unlocked, B reading `$C1`, and D reading the whole column A | [structure](../../docs/findings/findings-03-structure.md) |
| `59-conditions-relative-*` | `59-conditions-relative-base` | a row added and removed, a column added before B, and columns A, B and C each removed, which moves or breaks each rule in turn | [structure](../../docs/findings/findings-03-structure.md) |
| `60-move-base` | `00-baseline` | the block `B2:D5` holding a merge and formulas pointing inside it, out of it, locked, mixed and across tables, with formulas outside pointing into it, partly over it and at the two destinations. Built by a script | [structure](../../docs/findings/findings-03-structure.md) |
| `60b-move-cut-pasted` | `60-move-base` | `B2:D5` cut, then pasted at `F8` | [structure](../../docs/findings/findings-03-structure.md) |
| `60c-move-dragged` | `60-move-base` | `B2:D5` dragged so its top-left lands on `F8` | [structure](../../docs/findings/findings-03-structure.md) |
| `60d-move-overlapping` | `60-move-base` | `B2:D5` dragged down one row, onto itself | [structure](../../docs/findings/findings-03-structure.md) |
| `60e-move-overwrite` | `60-move-base` | `B2:D5` dragged one column right, over the formulas in `E2:E5` | [structure](../../docs/findings/findings-03-structure.md) |
| `61-move-styles-base` | `00-baseline` | twelve numbers in `B2:D5`, built by a script, then a fill on `B2`, bold on `D2`, a border on every edge of `C3` and highlighting on `C2` reading `B2` added by hand | [structure](../../docs/findings/findings-03-structure.md) |
| `61b-move-styles-cut-pasted`, `61c-move-styles-dragged` | `61-move-styles-base` | `B2:D5` moved to `F8`, by cut and paste and by dragging | [structure](../../docs/findings/findings-03-structure.md) |
| `62-move-rules-base` | `00-baseline` | `A1`, `E2` and twelve numbers in `B2:D5`, built by a script, then highlighting on `C2` reading `A1` and on `E2` reading `C2` added by hand | [structure](../../docs/findings/findings-03-structure.md) |
| `62b-move-rules-dragged` | `62-move-rules-base` | `B2:D5` dragged so its top-left lands on `F8` | [structure](../../docs/findings/findings-03-structure.md) |
| `72b-date-time-zones-region` | `72-date-time-zones` | the document's language and region set to English (Italy), saved by Numbers 15.4 | [values](../../docs/findings/findings-01-values.md) |

`tile-pattern.png` and `orientation-test.png` are the source images, each generated by a
script.

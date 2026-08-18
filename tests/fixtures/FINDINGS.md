# What the fixtures have established

Findings derived from the fixtures in this directory, each one reproducible by reading the
files with `pybers.archive`. Recorded here so they are not re-derived, and so a later
contradiction is recognizable as a contradiction.

Type identifiers are ours, read straight out of `ArchiveInfo.message_infos`. The
human-readable class names come from `reference/numbers-parser`'s `mapping.py` and are used
**for interpretation only** — pybers has not extracted its own mapping yet, and doing so is
the half of the bootstrap that requires executing an unsigned copy of Numbers.

---

## How cell text is stored — three tiers, not two

| what the cell has | what the archive gains |
|---|---|
| plain text, no formatting | **nothing** |
| one formatting applied uniformly to the whole cell | +1 `TSWP.CharacterStyleArchive`, +1 `TSWP.ParagraphStyleArchive`, **no payload** |
| formatting that varies *within* the cell | +1 `TST.RichTextPayloadArchive`, +1 `TSWP.StorageArchive`, and **one `CharacterStyleArchive` per distinct run** |

The run count is exact: `02-text-rich` has four differently formatted stretches in one cell
and produces exactly four new character styles. `03-text-multiline` has two paragraphs and
produces exactly two new `ParagraphStyleArchive`.

This validates the split already present in `pybers.model.text`
(`RichText` → `Paragraph` → `TextRun`): the archive format is one-to-one with it.

## `ParagraphStyleArchive` carries character properties too

`TSWP.ParagraphStyleArchive` has **both** `para_properties` and `char_properties`. The
second is easy to miss and cost a wrong conclusion once: a search that looked at
`para_properties` on paragraph styles and `char_properties` only on character styles
reported that all-caps was stored nowhere.

Formatting applied to a whole cell lands on the **paragraph** style's `char_properties`.
Formatting applied to part of a cell lands on a **character** style. Both use the same
`CharacterStylePropertiesArchive` message, so the property list is identical either way —
only the owner differs.

## Text background is TWO different fields, chosen by scope

The Numbers UI has one control, labeled **Text Background**, in the character-level "More
Text Options" panel. It writes to two unrelated fields depending on what was selected:

| applied to | stored as |
|---|---|
| a whole paragraph | `TSWP.ParagraphStylePropertiesArchive.fill` (with `fill_null`) |
| selected characters | `TSWP.CharacterStylePropertiesArchive.background_color` (with `background_color_null`) |

Measured in `08-text-para-backgrounds`, which contains one of each and labels them in its
own text:

```
913191  para_properties.fill             = rgba(0.001, 0.301, 0.500)   the blue one
913502  char_properties.background_color = rgba(0.005, 0.443, 0.002)   the green one
```

**A model with one `backgroundColor` on a text run cannot round-trip this.** The two are not
the same property at different scopes — they are different fields with different names and
different companions, and writing a paragraph-scoped background into the character field
would change what Numbers displays. Both need representing.

Neither is `TST.CellStylePropertiesArchive.cell_fill`, which is the cell's own background —
a third thing again.

### Do not mistake `tsd_fill` for a background

`CharacterStylePropertiesArchive` also carries `tsd_fill`, and it is **not** a background: it
is the fill of the glyphs themselves, the gradient-capable successor to the flat
`font_color`. Nearly every inherited paragraph style in every fixture sets it to black or
white, so a search for "fills" returns hundreds of irrelevant hits. `font_color` and
`tsd_fill` are foreground; `background_color` and `para_properties.fill` are background.

There is also `tsd_fill_should_fill_text_container`, which looks like it might turn a glyph
fill into a container fill. Nothing observed sets it, so its behavior is **untested and
unknown** — recorded only so it is not assumed to be the background field.

## Synthetic typography sits right beside the real thing

`CharacterStylePropertiesArchive` offers both routes, and this is the single most important
thing in this document, because choosing wrongly produces output that looks amateur while
appearing to have worked:

```
enum CapitalizationType { kNoCaps=0; kAllCaps=1; kSmallCaps=2; kTitled=3; }
enum SuperscriptType    { kNoScript=0; kSuperscript=1; kSubscript=2; }
optional SuperscriptType    superscript    = 10;
optional CapitalizationType capitalization = 13;
repeated FontFeatureArchive font_features  = 34;
```

- `superscript = kSuperscript` / `kSubscript` **raises and shrinks the existing glyph.**
  Synthetic. Never write it.
- `capitalization = kSmallCaps` **scales down capitals.** Synthetic. Never write it.
- The real forms are OpenType features in `font_features`, using the font's own designed
  glyphs.
- `capitalization = kAllCaps` is legitimate — it is a genuine case transform, not a faked
  glyph — and is the one member of that enum pybers should write.

`07-text-superscript` contains both routes side by side, which is what makes this testable
rather than asserted: archive `912364` uses `superscript = kSuperscript`, while `912394`,
`912487`, `912545` and `912503` each use a `font_features` entry instead.

**All caps is two settings in two places.** `capitalization = kAllCaps` alone renders badly,
because capitals inherit lowercase sidebearings and lowercase-height punctuation. It needs
the two OpenType capital features alongside it. Visible in `09`: the style that looks right
(`914066`) carries two extra feature entries that the one that does not (`913544`) lacks.
pybers must carry both or it will produce ugly output while believing it matched.

## Ligatures are NOT an OpenType feature here

Numbers keeps ligatures in its own field with its own three-value enum, not in
`font_features`:

```
enum LigaturesType { kRequiredLigatures=0; kStandardLigatures=1; kAllLigatures=2; }
optional LigaturesType ligatures = 16;
```

All four paragraph styles in `10-text-ligatures` carry *identical* `font_features`, which is
what proves the setting does not travel through the AAT list.

`kStandardLigatures` **is written explicitly** — it is set on roughly 240 inherited styles in
every fixture. A paragraph set to "Use Default" therefore produces no *new* style, because an
existing one already carries that value and gets reused. That is style deduplication, not an
absent field, and the distinction matters: **do not read a missing `ligatures` field as
"default"**, because the field is present nearly everywhere. Only three styles are new in
`10`:

```
914611  ParagraphStyleArchive  kRequiredLigatures   the two "no ligatures" paragraphs
914725  ParagraphStyleArchive  kAllLigatures        the "all ligatures" paragraph
914565  CharacterStyleArchive  kRequiredLigatures   see the layered case below
```

Two paragraphs share `914611`, which is direct evidence that **styles are deduplicated by
value across the document** rather than created per use site.

### The layered case, and the capability it exposes

One paragraph in `10` sets **None on the whole paragraph and Default on specific letters**
(`ff ffi ffl ct`). That is a paragraph-level value with a character-level override on top —
exactly the layering CLAUDE.md anticipates for named styles.

The data is consistent with the new character style `914565` (`kRequiredLigatures`) covering
the paragraph's ordinary text while the overridden letters reuse an existing
`kStandardLigatures` character style. **This is not confirmed.** Confirming it needs the
*style run table* — `StorageArchive.table_char_style`, which maps character ranges to style
identifiers — and that is not parsed yet.

That is the honest boundary of what the fixtures can currently prove: which styles exist and
what they contain, but not yet which characters they apply to. Parsing the run tables is the
next capability, and it is required before any claim about per-run formatting can be made
rather than inferred.

**This is a fidelity ceiling, and it is Numbers', not ours.** The OpenType tags `liga`,
`dlig`, `hlig` and `clig` are independently switchable in a real typesetting system.
Numbers collapses them into three choices, so **a caller cannot ask for discretionary
ligatures alone.** pybers should expose exactly the three states Numbers can store rather
than an API implying tag-level control it cannot honor.

pybers should expose exactly the three states Numbers can store, rather than an API implying
tag-level control it cannot honor.

## OpenType features are stored as AAT integer pairs

There are no `onum` / `pnum` tag strings anywhere. Numbers stores Apple Advanced Typography
pairs:

```
message FontFeatureArchive {
  required uint32 feature_type     = 1;
  required uint32 feature_selector = 2;
}
```

Observed, with readings of varying confidence:

| pair | evidence | confidence |
|---|---|---|
| `(10, 1) (10, 2) (10, 3) (10, 4)` | the four vertical-position variants, in the fixture built from superscript / subscript / ordinal / scientific | **high** — fixture design corroborates it independently |
| `(33, 2)` and `(33, 0)` | present only on the all-caps run that renders correctly | **high that these are the two capital features**, from matching the maker's own description |
| `(21, 0)` and `(6, 1)` | on essentially every style in every fixture | baseline defaults; **meaning not established** |
| `(38, 1) (37, 1)` | on one inherited style across several fixtures | **unknown** |

**Two structural facts, both certain and both consequential:**

1. **Several entries may share one `feature_type`.** `914066` carries `(33,2)` *and*
   `(33,0)`. So this cannot be modeled as a `dict[featureType, selector]` — it is an
   ordered list, and pybers must treat it as one.
2. **`font_features_null` is a distinct state from an absent list.** One style in `05`
   carries `font_features_null` with no `font_features` at all, which reads as features
   explicitly cleared rather than unspecified.

The full numeric table is **not** established. It should be verified against Apple's
`SFNTLayoutTypes.h` rather than from recall, and the design consequence stands regardless:
callers think in OpenType tags, so pybers should expose tags and translate to AAT pairs
internally rather than making every caller learn this enum.

**`calt` is on by default** in effectively every font, so a feature record existing does not
mean the fixture's feature was applied.

---

## Cell values: the one place the schemas stop helping

`TST.Tile` holds rows as `TileRowInfo`, and the values are **not protobuf**. They live in an
opaque `cell_storage_buffer`, indexed by a `cell_offsets` array. Everything below was
reverse-engineered against `11-value-types-noformats`, whose second row labels every cell in
text — which is the only reason the decode is verifiable rather than plausible.

```
cell_offsets           fixed 255 entries, uint16 (uint32 when has_wide_offsets)
                       0xFFFF means NO CELL — an empty cell has no record at all
cell_storage_buffer    records laid end to end; a record runs to the next live offset
```

Record layout, as far as it is needed to read a value:

```
byte  0      storage version (5 in every file seen)
byte  1      value TYPE (below)
bytes 4-7    flags bitmask — NOT decoded
bytes 8-11   purpose unknown — NOT decoded
bytes 12+    the value
```

| type | meaning | encoding at byte 12 |
|---|---|---|
| 2 | number | IEEE-754 **decimal128**, little-endian, 16 bytes |
| 3 | string | uint32 key into the `STRING` `TableDataList` |
| 5 | date | float64 seconds since **2001-01-01 UTC** (Apple epoch) |
| 6 | boolean | float64, zero is false |
| 7 | duration | float64 seconds |

Verified end to end: the fixture decodes to `1234.5`, `42`, `2027-06-15`, `0:20:00`, `True`,
`3`, `50`, `1`, `'Item 1'` — matching all nine of its own labels, with the tenth cell empty
and carrying no record.

### Numbers are decimal128, and this matters more than anything else here

Not float64. `1234.5` is stored exactly, as mantissa `12345` with exponent `-1`. A spreadsheet
library that round-trips values through Python's `float` **will corrupt them**: reading `0.1`
and writing it back would introduce binary-representation error into a document that never had
any. `decimal.Decimal` is the correct type for `Cell.value`, and this decides that part of the
model rather than leaving it to taste.

### Interactive controls are ordinary values plus a presentation reference

A checkbox, star rating, slider, stepper and popup menu all store a **normal value** — bool,
number, or string — and reference a `CONTROL_CELL_SPEC` separately. The control is how the
value is edited, not what it is. So they need no new value type, only a reference to carry.

### Two storage strategies by type

Strings are **pooled and deduplicated** into a `TableDataList` and referenced by key; numbers,
dates, booleans and durations are stored **inline** in the record. There is no `NUMBER` list
type. Any writer has to maintain the string pool, not just the cell.

### Do not trust `numCells`, `maxColumn` or `maxRow`

All three read **0** in a tile holding 19 real cells across two rows. They are not maintained.
The row count comes from `rowInfos`, and the populated columns come from the offsets array.
This cost a debugging cycle: a filter skipping tiles where `numCells == 0` skipped everything.

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

## Method notes, learned the hard way

- **Diff archive *contents* by identifier, not just presence.** An archive modified in place
  keeps its identifier, so a set difference over identifiers misses it entirely. This is how
  the all-caps hunt went wrong the first time.
- **Derive fixtures from one baseline by Save As.** Numbers renumbers object identifiers
  throughout a newly created document, so two files made from the template share almost no
  internal names. Save-As lineage keeps 36 of 37 members stable and is what makes a diff
  readable.
- **`TSD.DrawableSelectionArchive` (3061) and `TST.SelectionArchive` (6030) are noise** —
  they reflect what was selected when the file was saved. Filter them.
- **File size is dominated by the preview JPEGs** Numbers regenerates on each save. Not a
  content signal.

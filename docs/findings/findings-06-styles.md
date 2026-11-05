# Cell styling: borders, fills and alignment

How a cell gets its borders, its background and its alignment, three subsystems that turn
out to share almost nothing.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## Alignment is split across TWO style types, and the STYLE list is heterogeneous

From `30-style-align`. The `STYLE` data list does not hold one kind of thing:

```
key 1  TSWP.ParagraphStyleArchive     key 2  TST.CellStyleArchive
key 3  TSWP.ParagraphStyleArchive     key 6  TST.CellStyleArchive
```

**Horizontal alignment is a paragraph property. Vertical alignment and text wrap are cell
properties.** A cell needing both references both, which is why cell records carry a variable
number of style references:

```
refs=(5,1)        all defaults, no style of its own
refs=(1,5,1)      one paragraph style      h: left
refs=(6,1,5,1)    a cell style AND a paragraph style    h: left, v: middle
```

This is what the flags bitmask on a cell record gates, not one style slot, but several, of
different kinds. That resolves the variable-length tail that had been unexplained since the
value fixtures.

### The alignment enum has NO usable names, so the fixture is the authority

Apple's compiled descriptor carries placeholders:

```
enum TextAlignmentType { TATvalue0 = 0; TATvalue1 = 1; TATvalue2 = 2; TATvalue3 = 3; TATvalue4 = 4; }
```

Established by measurement instead, from a fixture that labels each cell with what it shows:

```
alignment 0 = left      alignment 2 = center
alignment 1 = right     alignment 3 = justify
```

Note that **1 is right and 2 is center**, which is not the order anyone would guess. `TATvalue4`
is not exercised by this fixture and remains unknown.

**Horizontal "auto" is the ABSENCE of a paragraph style**, not a value, the auto cells carry
no paragraph reference at all. Same for vertical top and wrap-on: they are defaults expressed
by omission.

Vertical alignment on the cell style:

```
0 = top (default, never written)    1 = middle    2 = bottom
```

**Where a schema gives placeholder names, only a labeled fixture can supply meaning.** That
makes fixtures the source of truth for parts of this format, not merely a check on it.

## The cell owns its box, the paragraph owns its text

`31-style-inset-2pt` adds insets and the indent controls sitting beside them in the UI, and the
split matches what `30` found for alignment:

```
key 2  CELL       padding  L2 T2 R2 B2
key 3  CELL       padding  L0 T0 R0 B0
key 4  PARAGRAPH  first_line_indent 18.0
key 1  PARAGRAPH  first_line_indent 18.0, left_indent 18.0
key 5  PARAGRAPH  first_line_indent 18.0, left_indent 18.0, right_indent 18.0
```

The rule that now covers every styling fixture:

| the CELL owns | the PARAGRAPH owns |
|---|---|
| `padding` (the inset) | `alignment` |
| `vertical_alignment` | `first_line_indent`, `left_indent`, `right_indent` |
| `text_wrap` | `fill` (the paragraph background) |
| `cell_fill` | |

**Everything is points.** An indent entered as `0.25in` stores as `18.0`, which is 0.25 x 72.
Inches, and any other unit the UI offers, are a display convenience with no presence in the
file.

**A 4pt inset is the default and needs no per-cell style**, the 4pt cell carries no cell
style key of its own, where the 2pt and 0pt cells do. The value is not absent from the
document, though: the built-in styles carry `L4 T4 R4 B4` explicitly, 3,366 times. The
default lives in the inherited style and the cell simply declines to override it.

**Padding is always uniform in practice.** Across every fixture here, 3,368 cell styles carry
padding and **not one is uneven**, only `4/4/4/4`, `2/2/2/2` and `0/0/0/0` appear. The UI
offers a single value and Numbers never writes anything else.

That leaves an open **write** question rather than a read one. `PaddingArchive` has four
independent floats, so pybers is able to emit `L2 T0 R4 B8`; whether Numbers honors it,
normalizes it, or rejects the file cannot be known until such a file exists. It is recorded
here so the capability is not assumed in either direction.

## Borders: THREE separate mechanisms, and none is built on the others

`29-style-border` carries five tables, each using a different border feature. The result
contradicts the reasonable guess that the table-level controls are convenience wrappers that
write ordinary cell borders. They are not.

```
Table 1              per-cell borders     8 strokes in the sidecar
Table 1-1            table outline 2pt    0 strokes
Table 1-1-1          gridlines on         0 strokes
Table 1-1-1-1        gridlines off        0 strokes
Table 1-1-1-1-1      alternating rows     0 strokes
```

| mechanism | stored in |
|---|---|
| per-cell borders | `TableModelArchive.stroke_sidecar` |
| gridlines and outline | `TableStyleArchive.table_properties.{v,h}_strokes_visible`, `table_border_visible` |
| row and column banding | `TableStyleArchive.table_properties.banded_rows`, `banded_fill` |

**Cell styles carry no strokes at all.** `CellStylePropertiesArchive` defines `top_stroke`,
`right_stroke`, `bottom_stroke` and `left_stroke`, and not one cell style in this fixture sets
any of them. Borders do not travel with a cell's style.

### The stroke sidecar is run-length layers per side

```
left_column_stroke_layers    one layer per COLUMN, runs indexed by row
right_column_stroke_layers   one layer per COLUMN, runs indexed by row
top_row_stroke_layers        one layer per ROW,    runs indexed by column
bottom_row_stroke_layers     one layer per ROW,    runs indexed by column
```

Each run carries an origin, a length, and a stroke with width, color and a dash pattern. A
width of `0` is how "no border" is expressed, so the layers are dense rather than sparse,
every position has a run, most of them empty.

Verified against the fixture: a 3pt top border on B1 is `top_row` layer 0 at column 1; a 0.5pt
blue right border on C1 is `right_column` layer 2; a dashed bottom on D1 carries
`dash[1, 1]`; a dotted left on E1 carries `dash[0, 2]`.

### One line between two cells is stored TWICE

This is the part worth knowing before writing anything.

The border between F1 and G1 appears as **both** F1's right stroke and G1's left stroke. The
border between H1 and H2 appears as **both** H1's bottom and H2's top. A single visual line is
two independent stored strokes on the facing edges.

**Setting a border between two cells means writing both sides.** Writing one leaves the
pair disagreeing, and which one Numbers renders is not something this fixture establishes.
Reading has the mirror problem: a border reported from one cell's perspective may or may not
be matched by its neighbor, and those are different document states.

### The table style has more than sixty stroke slots

Beyond the visibility flags, `table_properties` carries header row, header column, footer,
body horizontal and vertical strokes, five levels of category strokes, and a set of pivot
variants. The border vocabulary is large and almost all of it is **band-level** rather than
cell-level, consistent with the earlier finding that styles exist per band and not per row
or column.

Tables that only change a table-level setting show it as an override list on a variation
style, `Table 1-1-1-1` sets exactly `v_strokes_visible`, `h_strokes_visible` and
`table_border_visible`, the same parent-plus-override pattern seen in sheet tab colors.

## A fill is a three-way union

From `28-style-fills`, which carries ten variants in one row. A cell's style reaches
`cell_properties.cell_fill`, a `TSD.FillArchive` holding exactly one of:

```
color       a single flat color
gradient    an ordered stop list
image       a reference to image data, plus placement and tint
```

The cell style itself is reached through the `STYLE` data list, `refs[0]` on the cell record
is the style key. The cell labeled "No fill" has **no style reference at all**: its record is
two references where the others are three. Absence of a style is how "no fill" is expressed,
not a fill archive saying nothing.

## Color carries a COLOR SPACE, and it varies within one gradient

This is the finding that changes the model:

```
stop 0    model: rgb   rgbspace: srgb   headroom: 1
stop 1    model: rgb   rgbspace: p3     headroom: 1
stop 2    model: rgb   rgbspace: p3     headroom: 1
```

Three stops of a **single gradient**, two color spaces. A model storing `(r, g, b, a)` floats
would silently shift color, because 0.5 red in sRGB is not 0.5 red in Display P3. `rgbspace`
and `headroom` are part of the value, not metadata about it, and `model` allows for
non-RGB spaces this fixture has not exercised.

Anything in pybers representing a color must carry the space, and must not convert between
spaces silently. Converting is a decision a caller makes, not a side effect of reading a file.

## Gradients

```
type          Linear or Radial
stops[]       each with color, fraction, inflection
opacity
advancedGradient
anglegradient { gradientangle }     radians
```

`fraction` is the stop's position from 0 to 1. **`inflection` is the midpoint handle between
this stop and the next**, the control that makes a gradient non-uniform. It defaults to `0.5`,
and the "advanced" fixture carries `0.153` on its first stop. A reader that ignored
`inflection` would render every gradient as evenly distributed and look approximately right,
which is the worst kind of wrong.

Radial and linear share the same structure; only `type` and the angle differ.

## Supplied images become zip members, stored once and shared

`28` was extended with a real 1024x1024 PNG used across six fills. It appears as a **new zip
member**:

```
Data/tile-pattern-16.png    239,547 bytes
```

Three things follow, all verified.

**The bytes are stored unmodified.** The embedded member is byte-identical to the source PNG
by SHA-256, Numbers does not re-encode, resample or strip it. An image survives a round
trip exactly, provided the member is carried through untouched.

**The filename encodes the asset identifier.** `tile-pattern-16.png` is the original name plus
the `imagedata` identifier `16`. Every one of the six fills references `imagedata = 16`, and
there is exactly **one** `Data/` member, so image bytes are deduplicated across every use.

**Styles are deduplicated by value too.** Two cells given the identical fill share one style
archive with `refcount = 2`, exactly as formulas do. Changing only the scale produces a
different style.

### Technique and scale

`ImageFillTechnique` is a small enum, and `fillsize` carries the rendered tile size in points:

```
NaturalSize = 0     ScaleToFill = 3
Stretch     = 1     ScaleToFit  = 4
Tile        = 2
```

```
tile at 10%   technique=Tile          fillsize 102 x 102     1024 * 0.10 = 102.4
tile at 50%   technique=Tile          fillsize 512 x 512     1024 * 0.50 = 512
original      technique=NaturalSize   fillsize 102 x 102
scale to fit  technique=ScaleToFit
scale to fill technique=ScaleToFill
```

**Scale is not stored as a percentage.** It is expressed as the rendered `fillsize` in points,
which only means anything relative to the source image's own dimensions. Reporting a
percentage to a caller requires reading the image to learn its natural size.

## Image fills can reference data that is NOT in the document

```
technique      Tile, and other placements
tint           an optional color laid over the image
fillsize       { width, height }
imagedata      { identifier: 8 }
referencecolor
```

Before a real image was added, `28`'s fills pointed at `imagedata` identifier **8** with **no
archive 8 anywhere in the file**, the default image Numbers offers resolves to application
resources rather than to document content.

That state is worth remembering even now that supplied images are understood: **a reader must
tolerate an image reference that does not resolve**, because it is a legitimate document state
rather than corruption. A document using only Numbers' own default imagery carries no `Data/`
member at all.

## Only SOME style kinds can be named: and cell styles never are

Counted across `30-style-align`, `02-text-rich` and `10-text-ligatures`. `TSS.StyleArchive`,
the shared base of every style, carries `name`, `style_identifier`, `parent` and
`is_variation`, but only some kinds ever populate `name`.

| kind | named | anonymous |
|---|---|---|
| `TSWP.ParagraphStyleArchive` | 21, Body, Title, Heading, Caption, Table Style 1-7 | 667 |
| `TSWP.CharacterStyleArchive` | 8, Emphasis, Italic, Link, Underline, Strikethrough | 5 |
| `TSWP.ListStyleArchive` | 5, Bullet, Numbered, Lettered, Image, None | 0 |
| `TST.CellStyleArchive` | **0** | **309** |
| `TST.TableStyleArchive` | **0** | 18 |
| `TN.SheetStyleArchive` | **0** | 3 |

**Cell styles are never named**, in 309 instances. Nor are table or sheet styles. They exist
only as anonymous archives deduplicated by value and reached through a table's `STYLE` list.

Two details worth keeping. A **user-created** character style appears in the same registry as
Apple's own (`'smallcap'`, made while building `09-text-capitalization`) so named styles are
not a fixed built-in set. `Table Style 1` through `Table Style 7` are **paragraph** styles
despite the name, so the table styling vocabulary is expressed through named paragraph styles
rather than through named table styles.

### What this decides for the named-style question in CLAUDE.md

The layering machinery is real and already observed: a style may carry a `parent`, be marked
`is_variation`, and record an `override_count`, seen directly in the sheet tab colors of
`26-multi-sheets` and in the table-level border settings of `29-style-border`.

However, it applies to **paragraph, character and list** styles only. A `NamedStyle` registry that
covers those maps onto something Numbers really has. Extending it to cell styles would be
inventing a concept the format does not carry, and any such feature has to be labeled a
pybers concept rather than presented as a mapping, otherwise a round trip would promise a
persistence it cannot deliver.


## A `name` does NOT make a style visible: the stylesheet registry does

**The most consequential styles finding, from `42-table-titles-captions`.** A
`ParagraphStyleArchive` can carry a perfectly good `name` and still never appear in the
paragraph-styles browser. Being named and being *offerable to the user* are different things,
and only one of them is what `name` controls.

Every named paragraph style in the document is listed in `TSS.StylesheetArchive.styles`. What
separates the visible from the hidden is whether it also has an entry in
**`identifier_to_style_map`**, which keys a style by a stable string:

```
name                     archive    identifier_to_style_map key
Body                      903884    'text-6-paragraphstyle-Body 1'          theme, IN BROWSER
Heading                   903880    'text-2-paragraphstyle-Heading 1'       theme, IN BROWSER
Title                     903878    'text-0-paragraphstyle-Title'           theme, IN BROWSER
Table Style 1-7           9038xx    'text-13..19-paragraphstyle-Table...'   theme, IN BROWSER
Special Caption           914532    'text-0-paragraphstyle'                 USER-MADE, in browser
Object Caption            904523     NONE                                   HIDDEN
Object Title              904522     NONE                                   HIDDEN
Table Title 1 (x6)        904094+   'tableName-0-textStyle' ... '-5-'       per-slot, HIDDEN
```

`Object Caption` and `Object Title` are real, named, round-trippable styles that the user can
never see or select. `Table Title 1` exists as **six separate archives**, one per table slot,
each with its own `tableName-N-textStyle` key, so it is not one shared browser style either.

**The rule for pybers.** Creating a *paragraph* or *list* style the user can actually see
takes two writes, not one:

```
1. the ParagraphStyleArchive with its `name`         -- makes it a named style
2. an identifier_to_style_map entry in the stylesheet -- makes it VISIBLE
```

Doing only the first produces exactly the `Object Caption` situation: a style that is real,
survives a round trip, applies correctly, and is invisible in the browser forever. That is a
silent failure of the worst kind, everything looks right except the one thing the user asked
for.

### The rule does NOT hold for character styles

Measured against the expanded `32-named-styles`, which adds three user-created character
styles. **Every named character style in the document is absent from
`identifier_to_style_map` and visible anyway:**

```
smallcaps, 'smallcaps +2%', 'tabular numbers'   NO KEY   user-created, visible
Emphasis, Italic, Underline, Strikethrough, Gray NO KEY  Numbers' own, visible
Link                                'character-style-hyperlink'   special
None                                'character-style-null'        special
```

Only the two special system character styles are keyed. The registry governs **paragraph
and list styles**; for character styles a `name` appears to be sufficient on its own. Do not
generalize the paragraph rule across style kinds. It was stated too broadly on first
measurement and `32` corrected it.

### How keys are allocated

```
theme paragraph styles     'text-<N>-paragraphstyle-<Name>'    Body 1, Heading 1, Title...
USER paragraph styles      'text-<N>-paragraphstyle'           NO name suffix
theme list styles          'text-<N>-liststyle-<Name>'
USER list styles           'text-<N>-liststyle'
per-table-slot title       'tableName-<N>-textStyle'           six of them, hidden
```

User styles are numbered **from 0 independently of the theme styles**, so `Text` holds
`'text-0-paragraphstyle'` while `Title` holds `'text-0-paragraphstyle-Title'` in the same
document. The name suffix is therefore part of the key, not decoration, and is what keeps the
two namespaces from colliding.

The stylesheet also carries `parent_to_children_style_map` and a long series of
`styles_for_<version>` lists, neither of which is decoded.

## Named styles: applying one writes a REFERENCE, overriding one writes a VARIATION

`32-named-styles` answers the open question in `CLAUDE.md` about how named styles and local
formatting relate. The design that document proposed, a style reference plus an optional
local override layered on top, is what Numbers actually does.

Applying a named style to a cell stores a **direct reference** to the shared style:

```
key 2  'Heading'   is_variation=False
key 3  'Title'     is_variation=False
key 4  'Body'      is_variation=False
key 5  'Text'      is_variation=False     a user-created named style
```

Formatting a cell that already carries a named style creates an **anonymous variation**:

```
key 6  variation of 'Heading'          override_count=1   char: font_color, tsd_fill
key 8  variation of 'Body'             override_count=3   char: bold, font_name, font_size
key 1  variation of 'Table Style 2'    override_count=1   para: alignment
```

The variation stores **only the overridden properties**. Everything else resolves through
`parent`. The chain is `cell -> variation -> named style`, and reading a cell's effective
formatting means walking it.

### `override_count` counts logical properties, not fields

Key 6 changed one thing (the color) and stores **two** fields, `font_color` and `tsd_fill`,
which are the legacy and modern spellings of the same property. `override_count` is 1. Key 8
changed three genuinely different things and reports 3.

The count cannot be derived by counting set fields, and should be preserved rather than
recomputed.

### There is no unparented text style

The cell in `32` labeled as manually styled, the fixture's own note says it was hard to
"remove all styling", is **still a variation of `Body`**. Nothing in the document carries text
formatting without a named parent.

**Manual formatting is not the absence of a named style; it is an anonymous variation of one.**
For the model this means a text style reference is never genuinely absent, and a design with
`styleRef: str | None` should treat `None` as "not yet resolved" rather than "has no style".

### Character styles cannot be applied to a cell

Recorded in the fixture's own text: a character style can only be applied to **selected text**,
never to a whole cell by clicking it. Paragraph styles can be applied either way.

That matches the earlier finding that the cell owns its box and the paragraph owns its text,
and it means a per-cell API for character styling would be offering something the application
cannot express.

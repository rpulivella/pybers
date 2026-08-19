# Fills, gradients and color

How a cell gets its background, and why color is not three floats.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

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
width of `0` is how "no border" is expressed, so the layers are dense rather than sparse —
every position has a run, most of them empty.

Verified against the fixture: a 3pt top border on B1 is `top_row` layer 0 at column 1; a 0.5pt
blue right border on C1 is `right_column` layer 2; a dashed bottom on D1 carries
`dash[1, 1]`; a dotted left on E1 carries `dash[0, 2]`.

### One line between two cells is stored TWICE

This is the part worth knowing before writing anything.

The border between F1 and G1 appears as **both** F1's right stroke and G1's left stroke. The
border between H1 and H2 appears as **both** H1's bottom and H2's top. A single visual line is
two independent stored strokes on the facing edges.

So **setting a border between two cells means writing both sides.** Writing one leaves the
pair disagreeing, and which one Numbers renders is not something this fixture establishes.
Reading has the mirror problem: a border reported from one cell's perspective may or may not
be matched by its neighbour, and those are different document states.

### The table style has more than sixty stroke slots

Beyond the visibility flags, `table_properties` carries header row, header column, footer,
body horizontal and vertical strokes, five levels of category strokes, and a set of pivot
variants. The border vocabulary is large and almost all of it is **band-level** rather than
cell-level — consistent with the earlier finding that styles exist per band and not per row
or column.

Tables that only change a table-level setting show it as an override list on a variation
style — `Table 1-1-1-1` sets exactly `v_strokes_visible`, `h_strokes_visible` and
`table_border_visible` — the same parent-plus-override pattern seen in sheet tab colors.

## A fill is a three-way union

From `28-style-fills`, which carries ten variants in one row. A cell's style reaches
`cell_properties.cell_fill`, a `TSD.FillArchive` holding exactly one of:

```
color       a single flat color
gradient    an ordered stop list
image       a reference to image data, plus placement and tint
```

The cell style itself is reached through the `STYLE` data list — `refs[0]` on the cell record
is the style key. The cell labelled "No fill" has **no style reference at all**: its record is
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
this stop and the next** — the control that makes a gradient non-uniform. It defaults to `0.5`,
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
by SHA-256 — Numbers does not re-encode, resample or strip it. So an image survives a round
trip exactly, provided the member is carried through untouched.

**The filename encodes the asset identifier.** `tile-pattern-16.png` is the original name plus
the `imagedata` identifier `16`. Every one of the six fills references `imagedata = 16`, and
there is exactly **one** `Data/` member — so image bytes are deduplicated across every use.

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
archive 8 anywhere in the file** — the default image Numbers offers resolves to application
resources rather than to document content.

That state is worth remembering even now that supplied images are understood: **a reader must
tolerate an image reference that does not resolve**, because it is a legitimate document state
rather than corruption. A document using only Numbers' own default imagery carries no `Data/`
member at all.

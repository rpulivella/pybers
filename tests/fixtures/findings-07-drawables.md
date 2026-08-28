# Floating objects: text boxes, shapes and images

Everything that sits ON a sheet rather than inside a table.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## A text box IS a shape, with a flag saying so

Both `33-textbox` and `34-shape` produce `TSWP.ShapeInfoArchive`, but it carries
**`is_text_box`**, `True` for all fifteen drawables in `33`, `False` for every shape in `34`.
So they share the archive and are distinguished by a field, which is why `ShapeStyleArchive`
was the one style kind with no `name` in the naming survey. A connector is the exception: it
is a `TSD.ConnectionLineArchive` and has no `is_text_box` at all.

`DrawableArchive.parent` points at the **`TN.SheetArchive`** itself, so a drawable knows its
sheet without a reverse lookup.

The inheritance chain matters for finding anything:

```
TSWP.ShapeInfoArchive   is_text_box, owned_storage, text_flow, autogrows_for_localization
  -> TSD.ShapeArchive   style, pathsource, head_line_end, tail_line_end
    -> TSD.DrawableArchive   geometry, locked, aspect_ratio_locked, hyperlink_url,
                             comment, title, caption, accessibility_description
```

Text lives in **`owned_storage`**, not a field called `text`. `deprecated_storage` points at
the same archive, so a reader must prefer `owned_storage` and not double-count.

## The unit is the point, and the inch readout in the UI is lossy

`33` settles this with a controlled experiment rather than an inference. Two boxes place
`2.0 in` on one axis and a single arrow-key nudge on the other, with the axes swapped between
them, and four more step the nudge from one press to four:

```
nudges   stored x   Numbers displays   n / 72
  1        1.00        0.01 in         0.01389
  2        2.00        0.03 in         0.02778
  3        3.00        0.04 in         0.04167
  4        4.00        0.06 in         0.05556

2.0 in  ->  144.00        100 in -> 7200.00        200 in -> 14400.00
```

So the stored unit is **1/72 inch, the PostScript point**, confirmed at three scales three
orders of magnitude apart and on both axes. **One arrow-key nudge is exactly 1.0 point.**

The third column is where a reader goes wrong. The stored positions are perfectly uniform, one point apart,
but the inches Numbers *shows* step `0.01, 0.03, 0.04, 0.06`, deltas of 0.02, 0.01, 0.02.
The UI rounds `n/72` to two decimals, so its readout is neither uniform nor reversible.
**Any value taken from the displayed inch figure is wrong**: reading `0.01 in` back yields
0.72 points where the file holds 1.0, and the object moves.

Positions may be **negative** (two boxes sit above and left of the origin) and arbitrarily
large, so neither is an error condition to guard against.

## `geometry.flags` is a bitmask, and it explains auto-sizing

Unknown since `25-multi-tables`, resolved by the text boxes:

```
bit 1 (value 1)   width is explicit
bit 2 (value 2)   height is explicit
bit 4 (value 4)   flipped horizontally
```

```
flags=0   size 0.0 x 0.0     a text box sizing to its content in BOTH directions
flags=1   size 89.5 x 0.0    a text box with a fixed width, height still automatic
flags=3   size 100 x 100     shapes and images, both dimensions explicit
flags=5   fixed width + flipped
flags=7   both explicit + flipped
```

**A text box never sets bit 2.** Its height is automatic in every specimen, which is why
`geometry.size.height` is `0.0` on all fifteen, including the ones with an explicit width.

### A vertical flip is a horizontal flip plus a 180 degree rotation

`33`'s fixed-width boxes label themselves, and the labels separate three cases that `flags`
alone cannot:

```
"I am ... rotated"                flags=1  angle=180
"I am ... flipped horizontally"   flags=5  angle=0
"I am ... flipped vertically"     flags=5  angle=180
```

There is **no vertical-flip bit**. Numbers stores a vertical flip as bit 4 combined with a
180 degree rotation, which is geometrically the same transform. So `flags=5, angle=180` is
ambiguous on its face and a reader cannot recover which of the two the user asked for,
nor does it need to, since they render identically. A writer must not invent a second bit.

This also means **rotation and flipping are not independent** in the way the two-by-two of
`flags` against `angle` first suggests. Three of those four cells are distinct transforms;
the fourth is a flip expressed through the rotation field.

### There are TWO flip mechanisms and Numbers uses only one

`TSD.ShapeArchive.pathsource` carries `horizontalFlip` and `verticalFlip`, and both are
**`False` on every shape and text box in the corpus**. The flip that Numbers actually writes
is `geometry.flags` bit 4. Images have no `pathsource` at all.

A reader must therefore not treat the pathsource fields as authoritative, and a writer should
not set them expecting an effect.

## The laid-out size of a text box IS stored, in the path source

A zero `geometry.size` is not missing data, and it is also not the whole story. The size the
box actually occupies lives in **`pathsource.bezier_path_source.naturalSize`**, and it is
present on every text box including the fully automatic ones:

```
geometry.size            naturalSize          text
  0.000 x  0.000     290.534 x 19.692    one line, no explicit width
  0.000 x  0.000     373.932 x 30.478    one line, 18pt Heading style
 89.480 x  0.000      89.480 x 43.692    fixed width, wrapping to 3 lines
 89.480 x  0.000      89.480 x 55.692    fixed width, wrapping to 4 lines
 89.480 x  0.000      89.480 x 67.692    fixed width, wrapping to 5 lines
```

Two things follow. When a width is explicit, `geometry.size.width` and `naturalSize.width`
agree exactly, so the explicit width is stored twice. And the height, which `geometry` never
carries for a text box, is here, growing in 12.0 point steps per wrapped line from a
one-line height of 19.692.

So **reporting a text box's footprint does not require laying out its text**: Numbers has
already cached the answer. It does mean a writer that changes text, font or width leaves a
stale `naturalSize` behind unless it re-derives one, which is a layout problem this library
cannot solve from the archive alone.

The path itself is a plain rectangle, stored in the path's own coordinate space rather than
in points, see the next section for what that space is.

```
moveTo (0,0) -> lineTo (100,0) -> lineTo (100,100) -> lineTo (0,100) -> closeSubpath
```

## A bezier path's coordinate space is its OWN bounding box, not 0..100

Every text box in `33` uses a path running exactly 0..100, which makes "normalized to 100"
look like the rule. It is not. `34` contains paths in three different spaces, and the only
statement true of all of them is that **the path's bounding box maps onto `naturalSize`**:

```
              path extent                    naturalSize      scale x, y
34 [16]   (0.000,0.000)-(400.000,200.000)   120.0 x 60.0     0.3000, 0.3000
34 [19]   (0.000,0.000)-(141.421,  0.000)   141.4 x  0.0     1.0000, degenerate
34 [12]   (0.000,0.000)-(100.000,100.000)   100.0 x100.0     1.0000, 1.0000
33 [0]    (0.000,0.000)-(100.000,100.000)   290.5 x 19.7     2.9053, 0.1969
```

**The space is not 0..100**, `[16]` is authored at 400 x 200 and the 45-degree line at
141.421, so a reader has to derive the extent rather than assume it.

Shapes scale **uniformly**, because each is authored at its own natural aspect ratio. The
text-box rectangle does not, because a rectangle has no aspect to preserve, `2.9053` against
`0.1969` in the last row. So a reader cannot infer a single scale factor either; it has to
map the extent on each axis independently.

### Control points fall OUTSIDE the shape, so min/max over stored points is wrong

The ellipse `[12]` is the counter-example that matters. Taking the minimum and maximum of
every point stored in the path gives `(-4.882, -4.882)-(104.882, 104.882)`, and taking only
the on-path endpoints gives `(14.645, 14.645)-(85.355, 85.355)`. **Neither is the shape.**

It is a circle of radius 50 centered at `(50, 50)`, drawn as four `curveTo` elements whose
nodes sit at the 45-degree diagonals (`50 ± 50/√2` is exactly 14.645 and 85.355) with
control points pushed out to -4.882 to round the curve. Its true extent is `0..100`, which
matches `naturalSize` at scale 1.0.

So computing a shape's bounds means **evaluating the beziers**, not scanning the stored
coordinates. The naive minimum and maximum overstates this shape by about 10 percent, and
the on-path-only version understates it by about 30 percent. Both are plausible numbers, and
nothing raises, the characteristic failure of this format.

Paths made only of `lineTo`, the triangle, the quadrilateral, the line, the text-box
rectangle, are unaffected, which is exactly why measuring against `33` alone looked
conclusive and was not.

## Z-order is the order of `drawable_infos`

**There is no z-order field anywhere in the schema**, not on `DrawableArchive`, not on
`TN.SheetArchive`. By elimination the list order has to carry it, and `34` demonstrates it
directly. Every drawable appears in ascending archive-identifier order, which is creation
order, with exactly one inversion:

```
index 10   id 924580   'z sent to back'
index 11   id 924010   'z brought to front, 72.1% opacity'
```

`924010` was created first yet sits later in the list, and the two shapes overlap on the
sheet. So **later in `drawable_infos` means nearer the front**, and reordering the list is
how Numbers records a z-order change.

One detail is unresolved: the shape sent to back landed at index 10 rather than index 0, so
the operation is not a simple move to the end of the list. Whether Numbers scopes the
operation to overlapping objects, or something else reorders, needs its own fixture.

## Opacity is quantized to whole percent

`34`'s shape labeled `'z brought to front, 72.1% opacity'` stores:

```
opacity = 0.7200000286102295        which is float32(0.72) exactly
                                    float32(0.721) would be 0.7210000157356262
```

The tenth of a percent accepted in the UI is **not** in the file. This is the same class of
trap as the inch readout above: Numbers presents more precision than it keeps, so a value
read off the interface and written back is not the value that was there.

## Every drawable owns two empty caption archives

`DrawableArchive` carries `title` and `caption` references plus `title_hidden` and
`caption_hidden` booleans. Both references resolve to `TSD.StandinCaptionArchive`, which the
schema defines as **an entirely empty message**:

```protobuf
message StandinCaptionArchive {
}
```

Its existence is its whole payload, a placeholder saying "there is a caption slot here and
nothing is in it". Every drawable therefore costs two extra archives that carry no data, and
a writer that omits them is not producing an equivalent document.

## Shapes: five kinds of path

`pathsource` is a union, and `34` exercises all five:

```
scalar_path_source           a parametric shape, rectangle, ellipse and friends
bezier_path_source           a fixed bezier path
point_path_source            a point-defined shape
editable_bezier_path_source  a shape the user chose "Make Editable" on
connection_line_path_source  a connector, on TSD.ConnectionLineArchive
```

`editable_bezier_path_source` is what "made editable" produces, so **editing a shape's path
changes its path-source kind** rather than adding points to the original. One shape also
carries a `localizationKey`, which suggests some paths are template-provided and localizable.

### What the twenty-one drawables in `34` actually are

The path source names the *storage* kind, not the shape. Reading the element sequences
identifies each one, and the fixture is deliberately varied:

```
[0]-[11]  kTSDRoundedRectangle   scalar path, scalar 15 (and 21.73 on the resized one)
[12]      ellipse                4 curveTo, closed, nodes on the 45-degree diagonals
[13]      triangle               2 lineTo, closed
[15]      quadrilateral          3 lineTo, closed
[16]      curved 120x60 shape    4 curveTo + 2 lineTo, authored in a 400x200 space
[19]      straight line          1 lineTo, naturalSize height 0
[14]      kTSDRightSingleArrow   point path, point (64, 0.34)
[17]      editable bezier        1 CLOSED subpath, 6 nodes, sharp and smooth mixed
[20]      editable bezier        1 OPEN subpath, 9 nodes
[18]      connector              ConnectionLineArchive, 3 elements (an elbow)
```

Element point counts confirm the convention: `lineTo` and `moveTo` carry one point,
`curveTo` carries **three** (two control points then the endpoint) and `closeSubpath`
carries none. Every closed path also ends with a trailing `moveTo` back to the start.

A node in an editable bezier carries a `type` of `sharp` or `smooth`, so the smoothness of
each control point is stored per node rather than inferred from the handles.

`ConnectionLineArchive` sets no fields of its own, but its path source carries `type`,
**`outset_from`** and **`outset_to`**, the gap left between the connector and each endpoint.
Notably it holds **no reference to the shapes it connects**, so either this connector is
unattached or attachment is recorded somewhere else entirely; that needs its own fixture.

### The parametric kinds carry their parameters, and they are not normalized

```
scalar_path_source   type: kTSDRoundedRectangle  scalar: 15         naturalSize 100.000 x 100.000
scalar_path_source   type: kTSDRoundedRectangle  scalar: 21.733593  naturalSize 144.891 x 144.891
point_path_source    type: kTSDRightSingleArrow  point { x: 64  y: 0.34 }
```

`scalar` is the **corner radius in natural-size units, not a fraction**: 15 against 100 and
21.733593 against 144.890625 are both exactly 15%, so it scales with the shape and a reader
that treats it as a ratio is out by the size of the shape. `is_curve_continuous` rides along
with it.

`point_path_source` carries a two-component `point` instead, which for an arrow controls the
shaft proportions. Neither kind stores an expanded path, so **rendering a parametric shape
means reimplementing Apple's construction for that `type`**, the archive does not describe
the geometry, only names it.

`editable_bezier_path_source` has a different shape again: `subpaths`, each with a `closed`
flag and a list of nodes carrying `inControlPoint` / `nodePoint` / `outControlPoint` and a
node `type`. It is the only kind expressed as editable control points rather than a path or
a parameter.

### A saved custom shape style is STILL anonymous

`34` carries a shape labeled `'I am text in a rectangle shape and my shape has an
annoymously custom saved style (no ability to name them)'`. Its style archive carries the
full seven `shape_properties`, **no `name`, and no `is_variation`**.

So explicitly saving a shape style as a reusable preset does not produce a named style. This
confirms from a second direction the naming survey in
[findings-06-styles.md](findings-06-styles.md): only paragraph, character and list styles
carry names, and a `NamedStyle` registry for shapes would be a pybers invention that no round
trip can persist.

The default shapes in `34` each carry a complete anonymous style with all seven properties,
while every modified one is a **variation overriding exactly one**, `stroke`, `shadow`,
`reflection` or `opacity`. So the variation mechanism established for text in `32` is the
same mechanism shapes use.

## Style archives are SHARED BY REFERENCE between drawables

The single most important structural fact in `34`. Twenty-one shapes do not have twenty-one
styles. They have twelve, because unmodified shapes point at the **same archive**:

```
#903914   shapes [0, 12, 13, 14, 15, 16, 17]     seven drawables, one archive
#903915   shapes [8, 9]
#903908   shapes [18, 19, 20]
```

And `#903915` is doing double duty: it is the style of shapes `[8]` and `[9]` **and** the
`parent` that the variations on `[1] [2] [3] [4] [6] [7]` inherit from. A single archive
therefore backs eight drawables at once, two directly and six by inheritance.

This is what makes the aliasing defect in this project's rationale a real hazard rather than
an implementation slip: **the format genuinely shares styles, so a decoder that hands the same
mutable object to every user of an archive will let one edit silently restyle seven unrelated
shapes.** The frozen-`Style` contract in `pybers.model` has to hold on the read path, not only
when writing.

Numbers itself never mutates a shared archive. Changing one shape produces a **new** archive
that is a variation of the old one, `[1]` through `[7]` each got a fresh identifier in the
918000-933000 range rather than an edit to `#903915`. That is the behavior to copy.

## Absence has THREE different encodings in one message

`shape_properties` turns a property off three incompatible ways, and none of them is field
absence. Every one of these has `HasField()` returning **true**:

```
fill        an EMPTY sub-message            [18] [19] [20], the line-like objects
stroke      a full stroke whose pattern     [0] and every unmodified shape carry a
            type is TSDEmptyPattern         black stroke of width 1 that does not draw
shadow      either an EMPTY sub-message     filled shapes carry an empty shadow;
            or a full one with              the lines carry a complete shadow,
            is_enabled: false               angle 315 offset 5 radius 1, switched off
```

So `HasField("fill")` does not mean the shape is filled, a stroke with a color and a width
does not mean it has a border, and a shadow with a color, angle, offset and radius does not
mean it casts one. A reader must check **sub-message content** for `fill` and `reflection`,
the **pattern type** for `stroke`, and **`is_enabled`** for `shadow`, and the three tests are
not interchangeable.

The `'border'` shape is the control: it differs from the default only by `TSDSolidPattern` and
width 5 where the default has `TSDEmptyPattern` and width 1.

## Shape styles carry seven properties, and variations override one

A full `ShapeStyleArchive.shape_properties` holds:

```
fill, stroke, opacity, shadow, reflection, head_line_end, tail_line_end
```

`34` names each shape by what was done to it, and the styles match exactly, a variation
overriding precisely one property:

```
'border'          shape_properties = ['stroke']
'drop shadow'     shape_properties = ['shadow']
'contact shadow'  shape_properties = ['shadow']
'curved shadow'   shape_properties = ['shadow']
'reflection'      shape_properties = ['reflection']
```

### A shadow is a tagged union with per-type extensions

The three shadow kinds share one `shadow` field carrying a `type` discriminator, plus an
optional sub-message that only that type uses:

```
type: TSDDropShadow      color, angle 90, offset 2,  radius 5,  opacity 0.5
type: TSDContactShadow   color, angle 0,  offset 0,  radius 28, opacity 0.75
                         contactShadow { height: 0.173648179 }
type: TSDCurvedShadow    color, angle 90, offset 1,  radius 15, opacity 1
                         curvedShadow { curve: -0.12309546 }
```

So the common geometry (color, angle, offset, radius, opacity, `is_enabled`) applies to
every kind, and `contactShadow` / `curvedShadow` add the one parameter their kind needs.
A model with a flat "shadow" record would lose `height` and `curve`.

`type` is a plain integer enum: **0 drop, 1 contact, 2 curved.**

`34` contains **two** contact shadows differing only in `offset` (0 and 14), which shows the
common fields remain independently settable within a type rather than being fixed by it.
Both carry the identical `contactShadow { height: 0.173648179 }`.

#### `contactShadow.height` is a SINE, despite the name

```
height  = 0.173648179
asin(height) = 10.000000 degrees exactly     sin(10 deg) = 0.173648178
```

The value is `sin(10°)` to float32 precision, so what the field stores is the **sine of an
angle the interface presents in degrees**, under a name that reads like a distance. A writer
setting a "height" of 10 would produce something wildly wrong, and setting a fraction like
0.5 would silently mean 30 degrees.

`curvedShadow.curve` is **not** the same encoding, `asin(-0.12309546)` is -7.0708 degrees,
not a round number, so it reads as a raw curvature parameter and must not be treated as an
angle by analogy. Two adjacent fields, two different conventions, neither documented.

A reflection is by comparison trivial: `reflection { opacity: 0.5 }` and nothing else. `34`
carries exactly one, so the only reflection parameter observed is its opacity.

### A stroke carries a six-slot dash array that nothing in the corpus uses

Every stroke in `34` has the identical shape:

```
color, width, cap: ButtCap, join: MiterJoin, miter_limit: 4
pattern { type, phase: 0, count: 0, pattern: 0 x6 }
```

`pattern.pattern` is a **fixed six-element array** with a `count` saying how many slots are
live, and `phase` for the dash offset. `count` is `0` in every style in the corpus, so a
dashed or dotted border is representable but **unexercised**, the layout of the array is
inferred from the schema rather than measured, and needs its own fixture before a writer
should emit one.

The only stroke variation `34` does exercise is `TSDSolidPattern` with `width: 5` for the
shape labeled `'border'`, against `TSDEmptyPattern` with `width: 1` for the default.

### What `34` does NOT cover

Worth stating so the gaps are not mistaken for absences in the format:

```
dashed / dotted strokes     pattern.count is 0 everywhere
arrowheads                  head_line_end and tail_line_end are EMPTY on every style,
                            including the connector and the plain 45-degree line
gradient and image fills    every fill in the fixture is a flat rgb color
```

`head_line_end` and `tail_line_end` appear on the style **and** on `ShapeArchive`, and `34`
resolves which one Numbers uses. Every `ShapeArchive` in the fixture sets exactly
`style`, `pathsource` and `strokePatternOffsetDistance`, **the line-end fields on the shape
itself are never set**, even on the lines that do carry arrowheads. So the style is where
line ends live in practice, and the shape-level fields should be read as a fallback rather
than written.

### Arrowheads: named AND fully described

Ten lines in `34` hold `head_line_end` fixed at `'simple arrow'` and vary only the tail,
which is what proves which field is which. `TSD.LineEndArchive` carries:

```protobuf
message LineEndArchive {
  optional .TSP.Path path = 1;
  optional .TSD.LineJoin line_join = 2 [default = MiterJoin];
  optional .TSP.Point end_point = 3;
  optional bool is_filled = 4;
  optional string identifier = 5;
}
```

```
identifier         is_filled   end_point        path
'simple arrow'       True      (3.0,  0.0)     moveTo/lineTo/lineTo/close
'filled arrow'       True      (3.0,  1.5)     4 straight segments
'inverted arrow'     True      (3.0,  0.33)    extent only 6 x 3
'open arrow'         False     (3.0,  0.0)     moveTo/lineTo/lineTo/moveTo/lineTo, OPEN
'filled circle'      True      (3.0,  0.5)     4 curveTo
'open circle'        False     (3.0, -0.3)     4 curveTo
'filled square'      True      (3.0,  0.5)
'open square'        False     (3.0,  0.2)
'filled diamond'     True      (3.0,  0.33)
'line'               False     (3.0, -0.8)     a single lineTo
```

**Contrast this with `smart_stroke`.** A brush stroke gives only a name and leaves the
rendering to Apple. A line end gives a name **and the complete path**, so it can be drawn
without Apple's engine. The `identifier` is a convenience, not the definition, a reader
should draw the path and use the name only for reporting.

Every arrowhead is authored in a **6 x 6 box** regardless of shape, scaled at draw time.
`is_filled` distinguishes the open variants, whose paths are deliberately unclosed. And
`end_point` is where the line attaches, which **may be negative**, `'open circle'` at
`-0.3` and `'line'` at `-0.8` pull the line back so it does not show through the marker.

`head_line_end` and `tail_line_end` are independently settable; the variations that carry
them override exactly two properties and nothing else.

The stroke palette offered to lines is the same one text outlines get, brushes included.

### The dash array is in MULTIPLES OF STROKE WIDTH, not points

**Settled by `43-stroke-dashes`**, which draws every preset at two widths so the two readings
can be told apart:

```
                   1pt                    5pt                    verdict
short dashed   [1.0, 1.0]             [1.0, 1.0]             IDENTICAL
dashed         [2.0, 2.0]             [2.0, 2.0]             IDENTICAL
wide dashed    [6.0, 6.0]             [6.0, 6.0]             IDENTICAL
wide dotted    [0.001, 2.0]           [0.001, 2.0]           IDENTICAL, RoundCap
solid          TSDSolidPattern count 0                       no array at all
```

Every preset stores the same numbers at both widths. Absolute points would require `[10, 10]`
at 5pt to look proportional; it stores `[2, 2]`, so a 5pt dashed stroke renders **10pt dashes
with 10pt gaps**. A reader converting the array to points must multiply by `width`, and a
writer must divide.

`cap` tracks the preset rather than the width, `RoundCap`/`RoundJoin` on the dotted styles,
`ButtCap`/`MiterJoin` on the rest, confirming the zero-length-dash-plus-round-cap
construction for dots.

`43`'s ten specimens are otherwise identical: all `editable_bezier_path_source`, all
variations of one parent overriding exactly `fill` (empty) and `stroke`, `is_text_box: False`
despite carrying text. Nothing else in the fixture is unaccounted for.

### Connectors DO record what they connect

`44-line-ends` attaches connectors to shapes, which `34` never did, its lone connector was
simply unattached. `TSD.ConnectionLineArchive` carries **four** fields for it:

```
connected_from       TSP.Reference to the source ShapeInfoArchive
connected_to         TSP.Reference to the target
connected_from_uuid  TSP.UUID
connected_to_uuid    TSP.UUID
```

Both the reference and the UUID are populated on every attached connector, the same
belt-and-braces identity pairing that row and column hiding uses. The references point
straight at the drawables in the sheet's `drawable_infos`.

`connection_line_path_source.type` is the routing mode: **`1` on the connector attached to
the shape labeled "orthogonal connection line", `0` on all six others.** `outset_from` and
`outset_to` are `0.0` throughout.

One shape acts as a hub with four connectors attached, so a drawable may be referenced by
many connectors and a reader must not assume one.

## Images: what is stored, and what Numbers adds

From `35-image`, which places two source images thirteen times with varied size, rotation,
flipping, locking, cropping and deliberate distortion.

### Numbers writes a DERIVATIVE alongside every original

```
Data/orientation-test-16.png          14,236     byte-identical to the source
Data/orientation-test-small-17.png    18,426     a companion Numbers generated
Data/tile-pattern-18.png             239,547     byte-identical to the source
Data/tile-pattern-small-19.png        66,686
```

Originals are stored **unmodified**, verified by hash in `28` and consistent here. But each
one gains a `-small` companion, and **the companion of the orientation image is LARGER than
the original** (18 KB against 14 KB). "Small" means smaller *dimensions*, not fewer bytes:
the source has large flat regions that compress extremely well and the re-encoded derivative
does not.

The companion is the **thumbnail**, and `ImageArchive` says so with a field of its own:

```
data.identifier          16  ->  Data/orientation-test-16.png
thumbnailData.identifier 17  ->  Data/orientation-test-small-17.png
data.identifier          18  ->  Data/tile-pattern-18.png
thumbnailData.identifier 19  ->  Data/tile-pattern-small-19.png
```

So an image costs **two** package members and two asset identifiers, and the numeric suffix
in each filename is the identifier that refers to it.

Two consequences. A writer must not assume a derivative is smaller, and **regenerating
derivatives on save could inflate a document** that was previously fine. Carrying the
existing members through untouched is the safe behavior.

The numeric suffix is the asset identifier and matches `ImageArchive.data.identifier`, and
it increments across the document, `16`, `17`, `18`, `19` here, continuing from `16` in `28`.

### Placement, rotation, flipping and locking

`TSD.ImageArchive.super` is a `TSD.DrawableArchive`, the same base a shape uses, carrying
`geometry`, `locked` and `aspect_ratio_locked`. Measured across the nine placements:

```
pos=(101.0, 462.0)  size=800.0x500.0  angle=  0.00  flags=3  lock=False  MASK
pos=(670.4,   0.0)  size=147.2x 92.0  angle=  0.00  flags=3  lock=False
pos=(911.6, 247.9)  size=147.2x 92.0  angle=  0.00  flags=7  lock=False
pos=(911.6,   0.0)  size=147.2x 92.0  angle=180.00  flags=7  lock=False
pos=(682.2, 209.9)  size=147.2x 92.0  angle= 12.10  flags=3  lock=False
pos=(931.0, 136.1)  size=108.3x 67.7  angle=  0.00  flags=3  lock=True
pos=(732.7, 343.2)  size= 22.6x 92.0  angle=  0.00  flags=3  lock=False
```

**`angle` is in DEGREES here** (180 and 12.10) where the gradient angle in `28` was in
radians. The format is not internally consistent about angular units, and each one has to be
established separately rather than assumed.

**`flags` carries the flip.** Exactly the two placements described as flipped read `7` where
every other reads `3`; bit value 4 is the difference. The individual bits are not otherwise
decoded.

**`locked` is a plain boolean** on the drawable, matching the one table geometry carries.

### Distortion is just a size that disagrees with naturalSize

`naturalSize` is the source image's true dimensions and stays constant per asset, `800x500`
for one image, `1024x1024` for the other. `size` is what is drawn.

```
natural 800x500   size 147.2x92.0    proportional
natural 800x500   size  22.6x92.0    squashed to a quarter of its aspect
```

There are **no scale factors and no distortion field**. Non-uniform scaling is expressed
purely as a `size` whose aspect ratio differs from `naturalSize`, so a reader wanting to
report "distorted" has to compare the two, and a writer distorts simply by writing the size
it wants.

`originalSize` tracks the placed size rather than the source, so it is **not** a synonym for
`naturalSize` despite the name. Measured across all thirteen placements in `35`,
`originalSize` equals `geometry.size` **exactly, every time**, so it is redundant with the
geometry rather than carrying independent information, and a writer has to keep the two in
step.

### `aspect_ratio_locked` records the INTENT to distort, separately from the distortion

Twelve of the thirteen images have `aspect_ratio_locked: True`. The one that does not is
precisely the squashed placement, `22.6 x 92.0` against a natural `800 x 500`.

So the flag is the user having unlocked the proportions in the interface, not a derived fact.
It correlates with distortion here but does not define it: **the distortion is still only
visible by comparing `size` to `naturalSize`**, and an unlocked image that happens to sit at
its natural ratio is undistorted. A reader wanting "is this stretched" must compare the sizes;
a writer changing proportions should also clear the flag, or Numbers will re-constrain the
image on the next drag.

### `traced_path` is present on every image and defaults to the whole rectangle

```
moveTo (0,0) -> lineTo (800,0) -> lineTo (800,500) -> lineTo (0,500) -> closeSubpath -> moveTo
```

This is the instant-alpha outline, and it is stored in **source pixel units**, 800 by 500,
the image's `naturalSize`, not normalized and not in points. An untraced image still carries
one, describing the full rectangle, so its presence says nothing.

`ImageArchive` also has a **`flags` field of its own**, distinct from `geometry.flags` and
`0` on every image in the corpus. Nothing observed sets it, so its meaning is unestablished
and it must be carried through rather than reconstructed.

`interpretsUntaggedImageDataAsGeneric` is `False` throughout, a color-management switch for
images with no embedded profile.

### Cropping is a mask, and the image keeps its FULL size

A cropped image carries a `TSD.MaskArchive` whose `super` is itself a drawable, so the mask
has its own geometry. Measured across the cropped placements in `35`:

```
size 800.0x500.0   MASK pos=(   0.0,  0.0)  size=800.0x500.0    uncropped
size 800.0x500.0   MASK pos=(  94.6, 96.9)  size=293.3x294.8
size 800.0x500.0   MASK pos=(   0.0,  0.0)  size=293.3x294.8
size 800.0x500.0   MASK pos=( -44.0,-44.8)  size=293.3x294.8
size 632.9x395.6   MASK pos=(-127.6,-97.0)  size=293.3x294.8    cropped AND scaled
```

**The image's `size` does not change when it is cropped**, it still describes the whole
image. The mask's size is what the reader sees.

So **the on-screen footprint of a cropped image is the MASK's size, not the image's**.
Reporting `size` for a cropped image would be wrong by a factor of three in these examples,
and wrong silently, since both numbers are plausible.

**Mask positions may be negative**, which places the visible window past the image's
top-left corner. And the last example is cropped *and* scaled, so cropping and scaling are
independent transforms rather than alternatives, a reader has to resolve both.

An uncropped image may still carry a mask covering the whole image, so the presence of a
`MaskArchive` does not by itself mean the image is cropped. Comparing the mask geometry to
the image size is what answers that.

### The crop is the mask's GEOMETRY: its path is a full-image rectangle

`TSD.MaskArchive` has exactly two fields, `super` and `pathsource`, and the path is the
misleading one. Every mask in `35` carries the same path:

```
mask path extent   (0,0)-(800,500)      the WHOLE image, in source pixel units
mask naturalSize    293.34 x 294.76     the crop window
mask geometry       pos + size          the crop window, positioned on the image
```

So the path does **not** describe the crop. It is a plain rectangle covering the entire
image, identical across cropped and uncropped placements alike, while the actual crop is the
mask's `geometry`, position and size relative to the image's own top-left corner.

`35` demonstrates one window size at four offsets, two of them negative:

```
mask pos ( 94.62,  96.88)   a window taken from inside the image
mask pos (  0.00,   0.00)   flush to the top-left
mask pos (-44.00, -44.76)   the window starts outside the image
mask pos (-127.56,-96.98)   outside, and on an image also scaled to 632.9 x 395.6
```

Every mask in the corpus is a rectangle. Masking to a **shape** would presumably use the
path, which is what the field is for, but nothing here exercises it, so the rule "the crop
is the geometry" is established only for rectangular crops and should not be assumed for a
shape mask.

# Text, styles and typography

How cell text is stored, how styles attach to runs and paragraphs, and the typography
traps worth knowing before writing any of it back.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## How cell text is stored: three tiers, not two

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
`CharacterStylePropertiesArchive` message, so the property list is identical either way,
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
the same property at different scopes. They are different fields with different names and
different companions, and writing a paragraph-scoped background into the character field
would change what Numbers displays. Both need representing.

Neither is `TST.CellStylePropertiesArchive.cell_fill`, which is the cell's own background,
a third thing again.

### Do not mistake `tsd_fill` for a background

`CharacterStylePropertiesArchive` also carries `tsd_fill`, and it is **not** a background: it
is the fill of the glyphs themselves, the gradient-capable successor to the flat
`font_color`. Nearly every inherited paragraph style in every fixture sets it to black or
white, so a search for "fills" returns hundreds of irrelevant hits. `font_color` and
`tsd_fill` are foreground; `background_color` and `para_properties.fill` are background.

There is also `tsd_fill_should_fill_text_container`, which looks like it might turn a glyph
fill into a container fill. Nothing observed sets it, so its behavior is **untested and
unknown**, recorded only so it is not assumed to be the background field.

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
- `capitalization = kAllCaps` is legitimate. It is a genuine case transform, not a faked
  glyph, and is the one member of that enum pybers should write.

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

`kStandardLigatures` **is written explicitly**. It is set on roughly 240 inherited styles in
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
(`ff ffi ffl ct`). That is a paragraph-level value with a character-level override on top,
exactly the layering CLAUDE.md anticipates for named styles.

The data is consistent with the new character style `914565` (`kRequiredLigatures`) covering
the paragraph's ordinary text while the overridden letters reuse an existing
`kStandardLigatures` character style. **This is not confirmed.** Confirming it needs the
*style run table*, `StorageArchive.table_char_style`, which maps character ranges to style
identifiers, and that is not parsed yet.

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
| `(10, 1) (10, 2) (10, 3) (10, 4)` | the four vertical-position variants, in the fixture built from superscript / subscript / ordinal / scientific | **high**, fixture design corroborates it independently |
| `(33, 2)` and `(33, 0)` | present only on the all-caps run that renders correctly | **high that these are the two capital features**, from matching the maker's own description |
| `(21, 0)` and `(6, 1)` | on essentially every style in every fixture | baseline defaults; **meaning not established** |
| `(38, 1) (37, 1)` | on one inherited style across several fixtures | **unknown** |

**Two structural facts, both certain and both consequential:**

1. **Several entries may share one `feature_type`.** `914066` carries `(33,2)` *and*
   `(33,0)`. This cannot be modeled as a `dict[featureType, selector]`. It is an
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

## Character spacing is `tracking`, and it is a FRACTION

The Character Spacing control in "More Text Options" writes
`CharacterStylePropertiesArchive.tracking`, **stored as a fraction rather than points**. A
setting of +2% is `0.02`, so a reader must not report the stored number as a point value.

Measured across every document under `tests/fixtures/` and `tests/measurements/`, there are exactly two non-zero values:

```
tracking = -0.01    in ALL 38 fixtures, including 00-baseline
tracking =  0.02    in 32-named-styles only, once
```

**Only the second one was set by anyone.** The `-0.01` is a built-in template style's
default and is present in the untouched baseline, which is precisely why a value appearing
in a fixture is not evidence that the fixture's author put it there. It was briefly reported
here as a deliberate setting; it is not.

The `0.02` sits on the custom named paragraph style in `32`, not on any text box, so
character spacing is a *paragraph-reachable character property* like the rest, with nothing
text-box-specific about it.

`kerning` is a **separate field** on the same message, zero throughout. Tracking and kerning
are distinct properties rather than one control under two names, even though the UI exposes
only one.

`baseline_shift` is likewise on every character style and always `0.0` so far, identified
but never exercised.

## There is ONE place tabs live, and "cell level" writes the TABLE's text style

`39-text-tabs-indents` looks contradictory in the interface, the same cell shows three tab
stops when a paragraph is selected and an **empty** Tabs panel when the cell is selected,
and the archive explains it.

There is no cell-level tab storage at all. `tabs` exists only in `para_properties` on a
`ParagraphStyleArchive`. What differs is *which* paragraph style gets written:

```
cell selected        -> a variation of #903892, the table's BODY_TEXT_STYLE,
                        attached to every cell in the table
paragraph selected   -> a variation in that cell's rich-text table_para_style run
```

Setting tabs "on a cell" really sets them for **every paragraph in the table**, which is
why Numbers shows the table style as dirty (`Table Style 2*` with an Update button). The
cell-selected panel appears empty because it shows stops defined at that exact scope, and
they went one level up.

### Tab stops decode directly, in points

```
tabs { position: 7.2 }                                 0.1in, left, no leader
tabs { position: 36  leader: " " }                     0.5in
tabs { position: 108 alignment: kTabAlignmentCenter }  1.5in
tabs { position: 144 alignment: kTabAlignmentRight }   2.0in
tabs { position: 72  leader: "-" }                     1.0in with a dash leader
tabs { position: 72  alignment: kTabAlignmentDecimal } paired with decimal_tab "."
```

All four alignments are exercised. **`leader` is a single-character string**, and both an
unset field and `" "` mean no leader, so a reader must treat a space as absence, not as a
space-filled leader.

`default_tab_stops` is the fallback interval in points, `36.0` in the theme and changed to
`18.0` on one paragraph. `decimal_tab` is a separate string holding the decimal character.

### Indents: THREE point fields, plus a second mechanism that has no points at all

```
first_line_indent = 18.0     left_indent = 18.0     right_indent = 18.0      (0.25in each)
```

Three independent floats, in points, exactly as labeled. However, the **indent button** writes
somewhere else entirely:

```
"indented using indent button"          table_para_data: @0  (1, 0)
"...using the indent button again"      table_para_data: @30 (2, 0)
all three indent fields                 0.0
```

`table_para_data.first` is an integer indent **level** (one press, then two) with **no point
value stored anywhere**. It is the first time that run table has carried anything but
`(0, 0)` in every document.

There are two independent indent mechanisms that look identical in the interface, and a
reader that consults only the paragraph style sees an unindented paragraph and renders it
flush left. The list style is `'None'` throughout, so this is not list indentation.

**Paragraph borders** are visible in the same panel and present in the schema,
`border_positions = 0` and `rule_width = 1.0` on the base style, but unexercised.

## `*_null` booleans mean "explicitly NONE", not "unspecified"

**Settled by `38-text-outline-shadow`, and it changes how the whole style chain resolves.**
`CharacterStylePropertiesArchive` is littered with paired fields, `shadow` / `shadow_null`,
`background_color` / `background_color_null`, `font_features` / `font_features_null` and
many more. The pair is a tri-state that protobuf cannot express on its own.

Two character runs in the same cell, both variations of the style named `'None'`, both with
`override_count = 1`:

```
#981307   set fields: ['shadow_null']   shadow_null = True    an override to NOTHING
#982958   set fields: ['shadow']        shadow = <blue>       an override to a VALUE
```

Both **count as one override**, which is the proof: `shadow_null = True` is not "I say
nothing about shadow", it is "I define shadow, and it is none". A property genuinely left
alone sets neither field and contributes nothing to `override_count`.

```
neither field set    inherit from the parent chain
value field set      use this value
*_null set True      explicitly NO value, cancelling anything inherited
```

A reader that treats `shadow_null` as noise will inherit a shadow onto text that Numbers
shows without one. A writer that omits it cannot express "remove the inherited shadow" at
all.

## Text shadow and outline exist at BOTH the cell and the character level

`38` demonstrates this by accident, and the fixture labels the accident, which is what makes
it usable. One cell was copied from another; the copy kept the source's **cell-level** style
archive (`c7` and `c8` share style key 4, carrying a black shadow) and then had a blue
shadow applied to part of its text:

```
cell style (shared with c7)          shadow: black, angle 46.98, offset 0, radius 3
  run [0:17]  'weak blue shadow '    shadow_null = True        -> no shadow
  run [17:41] 'only on these...'     shadow: blue              -> blue shadow
```

Resolving a character's effective shadow means walking the cell's style **and** the
character run, in that order, applying the `*_null` rule above at each step. The same is true
of the outline. Text typed into the cell that is not yet part of a run picks up the
cell-level value, which is exactly the black shadow the fixture's own label reports as
suspicious.

## Text outline is `tsd_stroke`, and it DECODES THE DASH ARRAY

The Outline checkbox writes a full `tsd_stroke` on the character properties, the same stroke
message shapes use for borders. `38` carries five outline styles and so resolves the dash
array that `34-shape` left completely unexercised:

```
                 pattern.type       count   pattern[0..1]      cap / join
solid            TSDSolidPattern      0     0, 0               ButtCap  MiterJoin
dotted           TSDPattern           2     1.0, 1.0           ButtCap  MiterJoin
dashed           TSDPattern           2     2.0, 2.0           ButtCap  MiterJoin
wide dashed      TSDPattern           2     6.0, 6.0           ButtCap  MiterJoin
circular dotted  TSDPattern           2     0.001, 2.0         RoundCap RoundJoin
```

Four things this settles. A solid stroke has its **own pattern type** and leaves the array
empty rather than filling it. `count` says how many of the six slots are live, and dashes use
**two**, dash length then gap length. **Circular dots are a zero-length dash with a round
cap**, the classic construction, not a distinct pattern kind: `0.001` is as close to zero as
Numbers writes. `cap` and `join` change with the preset, so they are part of the style
rather than constants.

Still open: every outline in `38` has `width: 1.0`, so whether the dash numbers are **points
or multiples of the stroke width** cannot be told apart here. That is now the only thing
`46-stroke-dashes` still needs to answer.

### Cell borders use the SAME encoding, from a different menu

Checked against `29-style-border` rather than assumed. A cell border lives in
`TST.StrokeLayerArchive.stroke_runs`, each run carrying `origin`, `length` and a `stroke`
whose `pattern` is the identical `{ type, phase, count, pattern[6] }` message:

```
solid border    pattern { type: TSDSolidPattern }   cap ButtCap   join MiterJoin
dotted border   pattern { type: TSDPattern }        cap RoundCap  join RoundJoin
no border       pattern { type: TSDEmptyPattern }   width 0
```

One stroke encoding serves shape borders, cell borders and text outlines. **The menus
differ, not the format**: the cell Border Styles menu offers only solid, dashed, dotted and
No Border, while the text-outline menu offers about ten, including five brush strokes.

### Brush strokes are named, not described

The text-outline menu's five artistic strokes are **not** a dash array and not a raster
asset. `TSD.StrokeArchive` has a `smart_stroke` sub-message, and the brush is identified by a
plain string:

```protobuf
message SmartStrokeArchive {
  optional string stroke_name = 2;
  optional uint32 random_seed = 3;
  optional .TSP.ReferenceDictionary parameterValues = 4;
  optional double pattern_offset_distance = 5;
}
```

```
width 3.0  RoundCap  stroke_name 'Chalk2'
width 8.0  RoundCap  stroke_name 'Feathered Brush'
width 3.0  ButtCap   stroke_name 'Calligraphy'
width 8.0  RoundCap  stroke_name 'Dry Brush'
width 8.0  RoundCap  stroke_name 'Pen'
```

Four consequences. The `pattern` on these is an ordinary `TSDSolidPattern` with `count: 0`,
so **a reader checking only the pattern would call a chalk stroke solid**, `smart_stroke`
has to be checked before the pattern is believed. `stroke_name` is an internal identifier,
not a localized label: `'Chalk2'` carries a digit no menu shows. `cap` varies with the brush
(`Calligraphy` uses `ButtCap` where the others use `RoundCap`), so it is part of the preset
rather than a constant. `random_seed` exists because these strokes are randomized,
preserving it is what keeps a document rendering identically, so it must be carried through
rather than regenerated.

`parameterValues` is a `ReferenceDictionary` and is unset on all five, so per-brush tuning is
possible but unexercised. Brush strokes default to **8pt**; the fixture includes 3pt versions
of two of them to show the width is independent of the preset.

pybers can round-trip all of this faithfully without being able to render any of it, which is
the correct outcome, the geometry lives in Apple's renderer, keyed by that name.

## Baseline shift is the THIRD route to a raised character

`37-text-baselineshift` completes the set. Three different fields produce a similar look and
a reader must tell them apart, because only one of them is typographically real:

```
superscript      an enum on CharacterStylePropertiesArchive   SYNTHETIC, never write it
font_features    AAT sups / subs / ordn                       the real OpenType feature
baseline_shift   a float, SIGNED POINTS                       a manual nudge, no semantics
```

`baseline_shift` is plain signed points, `-1.0`, `3.0`, `-3.0`, `5.0`, `10.0` across the
fixture. It carries no meaning about what the text *is*, unlike a real superscript feature,
so it must never be used to represent one and must never be mistaken for one on read.

### Uniform baseline shift puts a CHARACTER property on a PARAGRAPH style

The cells that shift the whole cell are **plain strings with no rich-text payload**. Their
value goes into the cell's own style reference, which resolves to a `ParagraphStyleArchive`
variation carrying `char_properties.baseline_shift`:

```
"Baseline shift -1pt of all text in this cell"   plain string
   -> ParagraphStyleArchive #964645 VARIATION ov=2   char.baseline_shift = -1.0
```

This is the uniform-formatting tier again, and it confirms that a paragraph style is where
character properties live when the whole cell shares them. Only a cell with *mixed* baseline
shift produces a rich-text payload and a `table_char_style` run.

### A saved named character style is NOT a variation

`37` has both routes side by side and they are structurally different:

```
applied to selected text     #969015  name=''              is_variation=True   ov=1
                                      parent -> character style named 'None'
                             #969799  name=''              is_variation=True   ov=1

applied as a saved style     #974338  name='+5pt baseline' is_variation=False  ov=1
                                      no parent
```

An ad-hoc formatting change is an **anonymous variation of the character style named
`'None'`**, while a style the user saved and named is a **root** with no parent. This is the
third confirmation that there is no unparented text style: "no character style" is itself a
named style called `'None'`, exactly as "no list" is a list style called `'None'` in `33`.

`#969799` is shared by **three** cells, so text styles are shared by reference across cells
just as shape styles are across drawables. See the aliasing warning in
[findings-07-drawables.md](findings-07-drawables.md); it applies here too.

### Line spacing has four modes, and the labels identify three of them

```
kExactLineSpacing           amount 15.5     the UI's "Exactly" / fixed line height
kMinimumLineSpacing         amount 15.5     the UI's "At Least"
kSpaceBetweenLineSpacing    amount 15.5     the UI's "Between"
(field unset)                               the theme default
```

`37` labels these in its second row, which is what makes the mapping checkable: the cells
describing themselves as "fixed", "minimum" and "between" carry exactly
`kExactLineSpacing`, `kMinimumLineSpacing` and `kSpaceBetweenLineSpacing`, and the row-1
labels name the two ambiguous ones as the UI's `"at least"` and `"between"`.

Line spacing sits in `para_properties` and is a sub-message with a `mode` and an `amount`,
not a bare number, so a model storing line height as a float loses which mode it is.

**Read line spacing from the payload's paragraph style, not the cell's style reference.**
For a rich-text cell the two can disagree: `37`'s character-style cell has `kExactLineSpacing`
on its paragraph style inside the payload while its own cell-level style sets no
`line_spacing` at all. The paragraph style is the one that describes the paragraph.

## `character_index` counts UTF-16 CODE UNITS, not Python characters

**Settled by `36-unicode-text`, and it was the last open question in the object model.**
pybers previously assumed these indices were Python offsets. That assumption is wrong.

The fixture puts a single astral character between two differently formatted runs, `AB`
bold, the astral `𠮟` (U+20B9F) left alone, `CD` carrying OpenType features:

```
text            A    B    𠮟         C    D
python scalar   0    1    2         3    4
utf-16 unit     0    1    2    3    4    5

table_char_style:   @0 -> bold      @2 -> inherit      @4 -> font_features
```

The third run begins at **4**. Under Python indexing it would begin at 3, so the two
readings reconstruct differently and only one of them is coherent:

```
utf-16    [0:2] 'AB' bold     [2:4] '𠮟'  inherit    [4:6] 'CD' features    correct
scalar    [0:2] 'AB' bold     [2:4] '𠮟C' inherit    [4:5] 'D'  features    WRONG
```

Note the failure mode. The scalar reading does not raise, does not produce an out-of-range
index, and does not yield an obviously broken result, it produces **three runs of plausible
text with the wrong boundaries**, which is unfalsifiable without an answer key. This is why
`02-text-rich` validated perfectly and proved nothing: it is entirely BMP, where the two
counts agree exactly.

### The scope of the problem, precisely

This affects **run-table indices only**. It is not a general Unicode defect:

- Plain string cells hold their text in a protobuf `string`, which is UTF-8, and Python
  decodes it natively. `36` has a cell containing 48 Python characters and 53 UTF-16 units
  of CJK including astral Extension B, stored as an ordinary string with no run tables, and
  it round-trips with no special handling.
- **Nineteen of the twenty-one run tables** key on `character_index`, so all nineteen are
  affected together: character and paragraph styles, language, bidi, drop cap, dictation,
  tracked insertions and deletions.

The conversion belongs at the boundary where a run table is read or written, not in the
text handling generally. A model holding Python strings with Python offsets is the right
shape; it just has to translate on the way in and out.

### Arabic-Indic digits in a NUMBER cell are not stored at all

`36` puts the same three characters in two adjacent cells and labels both:

```
r0c8   "Arabic-Indic digits as a cell type number"   type 2, Decimal('123')
r0c9   "Arabic-Indic digits as a cell type text"     string U+0661 U+0662 U+0663 U+0020
```

Typing `١٢٣` where Numbers infers a number **parses it and stores the decimal 123**. The
Arabic-Indic code points are gone from the value entirely; the numeral system is carried by
the format, consistent with the numeral-system discovery in `16-number-scientific-numeralsystems`.
The text cell keeps the characters exactly, trailing space included.

A value's digits are **presentation**, and a round trip that reads a number and rewrites
it must not attempt to preserve the digit characters. There are none to preserve.

### Skin-tone emoji are a BASE plus a SEPARATE modifier code point

The emoji cell in `36` is 16 code points and 29 UTF-16 units:

```
U+1F91E  astral   HAND WITH INDEX AND MIDDLE FINGERS CROSSED
U+1F3FC  astral   EMOJI MODIFIER FITZPATRICK TYPE-3      <- a separate code point
U+270A   BMP      RAISED FIST                            <- a BMP base ...
U+1F3FC  astral   EMOJI MODIFIER FITZPATRICK TYPE-3      <- ... with an ASTRAL modifier
U+2699   BMP      GEAR
U+FE0F   BMP      VARIATION SELECTOR-16
```

Three things follow. A skin-toned emoji is **two code points**, so a run boundary can legally
fall between the base and its modifier, which renders as an unmodified emoji followed by an
orphan modifier. The base is not always astral (`✊` is BMP) and the modifier is not always
astral (`U+FE0F` is BMP), so **neither half can be predicted from the other**. A
grapheme cluster here spans up to 4 UTF-16 units, so grapheme-safe editing is a separate
problem from the index conversion above.

No ZWJ sequence (a family or profession emoji) is present, so the multi-person case is still
untested.

### Numbers NORMALIZES to precomposed form on entry

`36` has a cell labeled "e typed with accent added by long-press of the e key to add the
accent after". It stores **one** character, `é` U+00E9, not the two-character decomposed
sequence:

```
stored          py 1     'é'  U+00E9
NFD would be    py 2     'e' + U+0301 COMBINING ACUTE ACCENT
```

The decomposed form did not survive entry. The accented-Latin cell tells the same story:
34 characters stored, 39 under NFD.

A reader should therefore expect NFC, and a **writer must not emit decomposed sequences**
expecting them to round-trip, Numbers would renormalize and the character indices in all
nineteen run tables would shift underneath.

### Right-to-left is still unresolved, and `36` cannot resolve it

`36` contains four RTL cells, plain Hebrew, Hebrew with niqqud, Arabic, and mixed-direction
text with both European and Arabic-Indic digits. **All of them are plain strings.** A plain
string cell has no `StorageArchive` and therefore no run tables at all, so
`table_para_bidi` remains `(0, 0)` everywhere and its two `uint32` fields are still unmapped.

Answering it needs an RTL cell with **mixed formatting**, which forces a rich-text payload
into existence. The same is true of `table_language`, which only ever shows `"en"` so far.

### `rich_text_payload` is field 9, and `reference` is field 4

Found while reading `36`, and worth recording because of how it fails. `TableDataList.
ListEntry` has both:

```protobuf
optional .TSP.Reference reference = 4;
optional .TSP.Reference rich_text_payload = 9;
```

A rich-text entry populates **`rich_text_payload`**. Reading `reference` instead returns an
unset message whose `identifier` is `0`, no exception, no missing-field error, just a
reference to nothing. The rich text then appears to be absent rather than misread.

## Rich text: a StorageArchive with TWENTY-ONE parallel run tables

This is the layer that several earlier findings missed by only reading a table's own
`styleTable`. A rich-text cell references a `TST.RichTextPayloadArchive`, which references a
`TSWP.StorageArchive`, and that carries the text plus a set of run tables indexed the same way.

Six of them appear in the cell fixtures, which is what this section originally recorded. The
schema defines **twenty-one**, and a text box in `33` sets three more that no cell does:

```
table_char_style    table_para_style    table_list_style    table_para_data
table_para_starts   table_language      table_para_bidi     table_drop_cap_style
table_dictation     table_attachment    table_smartfield    table_layout_style
table_bookmark      table_footnote      table_section       table_rubyfield
table_insertion     table_deletion      table_highlight     table_tatechuyoko
table_overlapping_highlight             table_pencil_annotation
```

`table_language` and `table_para_bidi` mean **language and text direction are RUN properties**,
not document or paragraph settings, relevant to the unresolved Unicode questions.
`table_insertion` and `table_deletion` are tracked changes; `table_tatechuyoko` is Japanese
horizontal-in-vertical text; `table_pencil_annotation` is Apple Pencil markup.

### The tables come in four shapes, and one of them can OVERLAP

```protobuf
ObjectAttributeTable             character_index + optional Reference
StringAttributeTable             character_index + optional string
ParaDataAttributeTable           character_index + required first, second   (both uint32)
OverlappingFieldAttributeTable   a TSP.Range + a Reference
```

Nineteen of the twenty-one key on a single `character_index`, so each is a **strict
non-overlapping partition** of the text: a run ends where the next begins. However,
`table_overlapping_highlight` and `table_pencil_annotation` use a `TSP.Range` instead,
**because highlights can overlap each other and character styles cannot**.

A model that represents every run as one ordered list of boundaries is therefore correct for
nineteen tables and wrong for those two, which need real intervals.

### `StorageArchive.kind` defaults to TEXTBOX, so a cell must set it explicitly

```protobuf
optional KindType kind = 1 [default = TEXTBOX];
// BODY, HEADER, FOOTNOTE, TEXTBOX, NOTE, CELL, UNCLASSIFIED, TABLEOFCONTENTS, UNDEFINED
```

None of the text boxes in `33` sets `kind` at all, because protobuf omits a field equal to its
default. **An absent `kind` means text box**, and a writer producing a cell's storage has
to set `CELL` explicitly or it silently becomes something else.

### `table_para_starts` marks where list numbering RESTARTS

The expanded `32-named-styles` gives this run table its first non-zero value anywhere in the
documents. Mapped against paragraph boundaries in a storage holding four different lists:

```
@0    para_starts (0,0)   list 'None'           "Hello I am set as the named style Text."
@40   para_starts (1,0)   list 'Bullet'         "...text with bullets."      <-- the ONLY 1
@93   para_starts (0,0)   list 'Bullet'         "Another bullet."
@337  para_starts (0,0)   list 'Named Bullet'   "I am a named bullet style..."
@389  para_starts (0,0)   list 'Numbered'       "I am a CONTINUOUSLY numbered list."
@424  para_starts (0,0)   list 'Numbered'       "number 2"
```

`first = 1` appears on exactly one paragraph, the first list item in the storage. Note that
the numbered list at `@389` begins a different list style and still reads `(0, 0)`, and the
fixture labels it "continuously numbered". This is **not** a "list begins here" marker; it
reads as a **restart-numbering flag**, which is why a continuing sequence leaves it at zero.

One observation only, so treat the reading as provisional. What is certain is that the field
is not always zero and therefore cannot be dropped.

### `table_dictation` carries a UUID per dictated word

`33`'s text boxes expose a run table no cell fixture has. Two of them carry:

```
entries { character_index: 0 }
entries { character_index: 16  object: "9640819A-4879-4687-9E93-F31D6DF1F40A" }
entries { character_index: 20 }
```

Characters 16 to 20 of that text are the word **"with"**. macOS tags dictated or
autocorrected text with a per-word UUID, and it persists in the saved document.

Two consequences. It is **user-provenance metadata that travels with any shared file**, which
is worth knowing before a library silently preserves or strips it. Because it is keyed by
character index, **any insertion or deletion must shift it exactly like a style run**, a
structural edit that reindexes only the style tables leaves the UUID pointing at the wrong
word.

### Absence is asserted POSITIVELY, not by omission

A text box with no list still carries a `table_list_style` entry pointing at a
`ListStyleArchive` **named `'None'`**. Likewise `table_drop_cap_style` is present on all
fifteen with an entry that has a `character_index` and no `object`.

"No list" and "no drop cap" are things Numbers writes down rather than leaves out, and a
writer that omits the table is not producing the same document. This matches the
`StandinCaptionArchive` pattern in
[findings-07-drawables.md](findings-07-drawables.md), where an empty message is written purely
to say the slot exists.

### A text box's paragraph style is a NAMED reference with no variation

Every text box in `33` points its `table_para_style` at a theme style, `'Body'` on fourteen
of them, `'Heading'` on the one labeled "this paragraph is a heading". Neither is a variation
and **neither has a parent**, so theme base styles are roots.

The two differ in exactly three properties:

```
                Body      Heading
char.bold       False     True
char.font_size  11.0      18.0
para.outline_style  1     2
```

**`table_char_style` is absent entirely** from every text box, because none has
character-level formatting. This is consistent with character styles applying to selected text
rather than to a container: with nothing selected and restyled, the table is simply not
written.

### A run with no object inherits from the paragraph

The character run table alternates styled and unstyled spans. An entry whose `object` field is
**absent** (`HasField("object")` is false, not an identifier of zero) carries no character
style, and the text there takes the paragraph's formatting:

```
character_index=0     hasObject=False        the paragraph's own formatting
character_index=380   hasObject=True   -> a named character style
character_index=390   hasObject=False        back to the paragraph
```

The table is a sequence of overrides over a paragraph baseline, and a reader must treat a
missing object as "inherit" rather than skipping the entry or treating it as an error.

### Character styles live HERE, not in the table's style list

A table's `styleTable` holds paragraph and cell styles. **Character styles appear only inside
rich-text storages**, reached through the run table. Any survey of "the styles in a table" that
reads `styleTable` alone will not see a single character style, which is what caused two
wrong attributions recorded and corrected earlier in this file.

This matches the behavior the fixture documents in its own text: a character style cannot be
applied by selecting a cell, only by selecting text. It is available to text anywhere, cells,
text boxes, shapes, but always to a *range*, never to a container.

### Named character styles carry real properties, including tracking

From `32-named-styles`, user-created styles alongside Apple's built-ins:

```
'tabular numbers (lining + monospaced)'   font_features [(6, 0)]
'smallcaps'                                font_features [(33, 2)]
'smallcaps +2%'                            font_features [(33, 2)] + tracking 0.02
'Emphasis'   built-in                      bold = True
'Italic'     built-in                      italic = True
```

Anonymous character **variations**, exactly as paragraph styles do:

```
font_color + tsd_fill        override_count = 1     a color change
font_name SkolarSansLatn-El  override_count = 1     a weight change
font_name + italic           override_count = 2
```

The reference-plus-variation model established for paragraph styles applies unchanged to
character styles. A color change again writes both `font_color` and `tsd_fill` and counts as
one override.

### Two more AAT feature pairs identified

```
(33, 2)   small caps           the 'smallcaps' style sets exactly this
(6,  0)   tabular / lining figures
```

`(33, 2)` retroactively explains `09-text-capitalization`, where `(33, 2)` and `(33, 0)` appear
together with `capitalization = kAllCaps`, feature type 33 is the letter-case family, and its
selectors are what the earlier finding described only as "the two capital features".

`(6, 0)` is the counterpart of the `(6, 1)` that appears as a default throughout, so feature
type 6 is the number-spacing family.

## Typeface variants live in the font NAME, and bold/italic can fake them

A third place where Numbers offers a synthetic alternative beside the real thing. Every
distinct combination in `32-named-styles`:

```
HelveticaNeue         bold=False  italic=False
HelveticaNeue         bold=True   italic=False     SYNTHETIC bold on a regular face
HelveticaNeue-Bold    bold=False  italic=False     the real bold face, flag off
HelveticaNeue-Bold    bold=True   italic=False     the real bold face AND the flag
HelveticaNeue-Light   bold=False  italic=False
HelveticaNeue-Medium  bold=False  italic=False
SkolarSansLatn-El     bold=(unset) italic=(unset)  extralight
SkolarSansLatn-ElIt   bold=(unset) italic=True     the italic face AND the flag
SkolarSansLatn-Rg     bold=False  italic=False
```

**Weight and slant are part of `font_name`** (the PostScript name) and `bold` / `italic` are
independent booleans layered on top, which means:

- `bold=True` on a regular face is **faux bold**, the same class of defect as the synthetic
  superscript and scaled small caps recorded above.
- `bold=True` on a face that is already bold is redundant at best.
- A style may set neither flag, which is what a chosen variant like extralight looks like.

**pybers must not treat `bold` as "make this bold".** Choosing a real face is a change of
`font_name`; setting the flag asks the renderer to synthesize. A caller wanting genuine
weight needs the family's actual face, and the library should be able to tell the two apart
when reading and prefer the real face when writing.

## Lists are nine-level arrays

Every list property is an array with one entry per nesting level, nine of them, whether or
not the text nests:

```
label_types    0 = none,  2 = bullet from `strings`,  3 = number
strings        the glyph per level, e.g. ['■','•','•','•','•','•','•','•','•']
indents        per level in points, e.g. [0, 11, 22, 33, 44, 55, 66, 77, 88]
text_indents   per level
geometries     scale, baseline_offset, scale_with_text
number_types   for numbered lists
tiered_numbers whether a level shows its ancestors' numbers
```

A bullet's size is `geometries[level].scale` and its vertical nudge is
`geometries[level].baseline_offset` in points. Measured across `32`, and unambiguous:

```
200%              scale = 2.0     baseline_offset =  0.0
100%, -2pt        scale = 1.0     baseline_offset = -2.0
100%, +10pt       scale = 1.0     baseline_offset = 10.0
'Named Bullet'    scale = 1.35    baseline_offset =  1.0
```

`scale` is a multiplier where 1.0 is 100%, so the UI percentage divided by a hundred.

List styles follow the same reference-and-variation model as everything else: named ones,
`'None'`, `'Bullet'`, `'Numbered'`, and a user-created `'Named Bullet'`, plus anonymous
variations carrying only what differs, such as a single overridden `strings` array to change
one glyph.

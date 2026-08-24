# Text, styles and typography

How cell text is stored, how styles attach to runs and paragraphs, and the typography
traps worth knowing before writing any of it back.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

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

## Character spacing is `tracking`, and it is a FRACTION

The Character Spacing control in "More Text Options" writes
`CharacterStylePropertiesArchive.tracking`, **stored as a fraction rather than points**. A
setting of +2% is `0.02`, so a reader must not report the stored number as a point value.

Measured across every fixture in this directory, there are exactly two non-zero values:

```
tracking = -0.01    in ALL 38 fixtures, including 00-baseline
tracking =  0.02    in 32-named-styles only, once
```

**Only the second one was set by anyone.** The `-0.01` is a built-in template style's
default and is present in the untouched baseline, which is precisely why a value appearing
in a fixture is not evidence that the fixture's author put it there. It was briefly reported
here as a deliberate setting; it is not.

The `0.02` sits on the custom named paragraph style in `32`, not on any text box — so
character spacing is a *paragraph-reachable character property* like the rest, with nothing
text-box-specific about it.

`kerning` is a **separate field** on the same message, zero throughout. Tracking and kerning
are distinct properties rather than one control under two names, even though the UI exposes
only one.

`baseline_shift` is likewise on every character style and always `0.0` so far — identified
but never exercised.

## Rich text: a StorageArchive with SIX parallel run tables

This is the layer that several earlier findings missed by only reading a table's own
`styleTable`. A rich-text cell references a `TST.RichTextPayloadArchive`, which references a
`TSWP.StorageArchive`, and that carries the text plus **six** run tables indexed the same way:

```
table_char_style    character styles      table_para_starts   paragraph boundaries
table_para_style    paragraph styles      table_language      language runs
table_list_style    list styles           table_para_bidi     bidirectional runs
```

`table_language` and `table_para_bidi` mean **language and text direction are RUN properties**,
not document or paragraph settings — relevant to the unresolved Unicode questions.

### A run with no object inherits from the paragraph

The character run table alternates styled and unstyled spans. An entry whose `object` field is
**absent** — `HasField("object")` is false, not an identifier of zero — carries no character
style, and the text there takes the paragraph's formatting:

```
character_index=0     hasObject=False        the paragraph's own formatting
character_index=380   hasObject=True   -> a named character style
character_index=390   hasObject=False        back to the paragraph
```

So the table is a sequence of overrides over a paragraph baseline, and a reader must treat a
missing object as "inherit" rather than skipping the entry or treating it as an error.

### Character styles live HERE, not in the table's style list

A table's `styleTable` holds paragraph and cell styles. **Character styles appear only inside
rich-text storages**, reached through the run table. Any survey of "the styles in a table" that
reads `styleTable` alone will not see a single character style — which is what caused two
wrong attributions recorded and corrected earlier in this file.

This matches the behavior the fixture documents in its own text: a character style cannot be
applied by selecting a cell, only by selecting text. It is available to text anywhere — cells,
text boxes, shapes — but always to a *range*, never to a container.

### Named character styles carry real properties, including tracking

From `32-named-styles`, user-created styles alongside Apple's built-ins:

```
'tabular numbers (lining + monospaced)'   font_features [(6, 0)]
'smallcaps'                                font_features [(33, 2)]
'smallcaps +2%'                            font_features [(33, 2)] + tracking 0.02
'Emphasis'   built-in                      bold = True
'Italic'     built-in                      italic = True
```

And anonymous character **variations**, exactly as paragraph styles do:

```
font_color + tsd_fill        override_count = 1     a color change
font_name SkolarSansLatn-El  override_count = 1     a weight change
font_name + italic           override_count = 2
```

So the reference-plus-variation model established for paragraph styles applies unchanged to
character styles. A color change again writes both `font_color` and `tsd_fill` and counts as
one override.

### Two more AAT feature pairs identified

```
(33, 2)   small caps           the 'smallcaps' style sets exactly this
(6,  0)   tabular / lining figures
```

`(33, 2)` retroactively explains `09-text-capitalization`, where `(33, 2)` and `(33, 0)` appear
together with `capitalization = kAllCaps` — feature type 33 is the letter-case family, and its
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

**Weight and slant are part of `font_name`** — the PostScript name — and `bold` / `italic` are
independent booleans layered on top. So:

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

List styles follow the same reference-and-variation model as everything else: named ones —
`'None'`, `'Bullet'`, `'Numbered'`, and a user-created `'Named Bullet'` — plus anonymous
variations carrying only what differs, such as a single overridden `strings` array to change
one glyph.

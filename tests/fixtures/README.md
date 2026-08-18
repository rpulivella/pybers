# Fixtures — what to make, and how

Real `.numbers` documents used to map Apple's archive format and to lock in round-trip
behavior. Each one exists to isolate **exactly one** feature.

Saved from **Numbers 15.3.1**, the same version `src/pybers/protos/` was extracted from, so
the schemas and the files agree.

---

## The method — this is the part that matters

**Derive every file from `00-baseline.numbers` by File → Save As. Never create a new
document from the template.**

Numbers stamps fresh object identifiers throughout a newly created document, so two files
made from the template share almost no internal names and cannot be compared. A Save As
copy keeps them: measured across `01 → 02`, **36 of 37** IWA members kept the same name,
which is what lets a diff say "these three archives are the rich text" instead of "these
two documents are different".

A **star**, not a chain: every file is `00-baseline` plus one change, derived directly from
`00-baseline`. Not `02` from `01`, `03` from `02`. A chain accumulates, so isolating the
third feature means unpicking the first two.

Whatever formatting the default new document carries is fine — **do not try to strip it to
truly empty.** The baseline is a subtraction reference, not a minimal document; anything it
carries cancels out in the diff as long as every file starts from the same one.

### Label what is DISPLAYED, not what you typed

The label row is the answer key that makes a decode verifiable, so it has to describe
something checkable. What a cell displays can be confirmed against a screenshot. What was
typed cannot be recovered from the file at all — and `13-number-percent` showed the two can
differ, where typing `0.25` and `-0.25` into percent cells did not store symmetric values.

Describing the formatting applied is useful too. Just do not assume the stored value equals
the keystrokes.

### Things that do not matter, so do not spend effort on them

- **File size.** It is dominated by the preview JPEGs Numbers regenerates on every save
  (46 KB in one fixture, 8.6 KB in another). Not content.
- **What was selected when you saved.** It shows up as `TSD.DrawableSelectionArchive` and
  `TST.SelectionArchive` appearing and disappearing. Filtered on the reading side.

---

## Status

`00-baseline` was re-made from `01-text-plain` with the cell contents deleted, which put it
into the same lineage as everything else. Verified: 36 to 37 of 37 members shared with each
of `01` through `10`.

Everything through `10-text-ligatures` is present and has been read. What each one
established is in [FINDINGS.md](FINDINGS.md) — read that before making more, because several
fixtures turned out to carry more than they were asked for and the list below has been
adjusted accordingly.

**The style run table is solved.** `StorageArchive.table_char_style` is a sparse list of
`(character_index, style reference)` entries, each run ending where the next begins. Verified
against `02-text-rich`, which resolves to exactly the four runs it was built from: `He` bold,
`l` italic, `l` in the alternate font with OpenType features, `o` underlined and colored. So
findings can now state which characters a style covers, not just that the style exists.

**Made so far: 00 through 14.** Text and formatting are done, and the cell-value encoding is
broken open for numbers, currency, percent and dates. What the set still lacks: durations
with formats, formulas, merges, named styles and floating objects.

---

## Made — 00 through 10, all text and formatting

All read, all mapped. What each established is in [FINDINGS.md](FINDINGS.md); the notes
here are only what is worth knowing about the *fixture*.

```
00-baseline             The subtraction reference. Everything else is this plus one change.
01-text-plain           A plain string. Establishes that plain text creates NO archives.
02-text-rich            Four differently formatted runs in one cell. The single most useful
                        fixture: proved one CharacterStyleArchive per run, and later proved
                        the run table maps them to exact character ranges.
03-text-multiline       Two paragraphs. Proved one ParagraphStyleArchive per paragraph.
04-text-monospace       A font change over a whole cell. Proved that UNIFORM formatting
                        needs no rich-text payload.
05-opentype             Ten distinct character styles carrying OpenType features. Proved
                        features are stored as AAT integer pairs, not tag strings.
06-strikethrough        Same shape as 04. Confirmed the uniform-formatting tier.
07-text-superscript     Carries BOTH the synthetic superscript enum and the real OpenType
                        features, side by side. That contrast is what makes the
                        never-write-the-fake-one rule testable rather than asserted.
08-text-para-backgrounds  Corrected a wrong expectation. The UI calls this "Text
                        Background" and offers it in the character panel, but it writes to
                        TWO DIFFERENT FIELDS by scope — paragraph to
                        ParagraphStylePropertiesArchive.fill, character to
                        CharacterStylePropertiesArchive.background_color. Carries one of
                        each and names them in its own text, which is what made the
                        difference findable.
09-text-capitalization  All caps. Established that it is TWO settings in two places:
                        capitalization=kAllCaps plus the two OpenType capital features,
                        because the enum alone renders badly.
10-text-ligatures       A LAYERED case — None on the paragraph, Default overridden onto
                        specific letters. The only fixture with paragraph-value-plus-
                        character-override, which is the structure named styles will need.
                        Also proved ligatures are their own enum, not an OpenType feature.
```

**Typographic rules these fixtures exist to protect.** Real OpenType features are always
preferred over an application's synthetic imitation: `sups` / `subs` / `ordn` rather than
raised-and-shrunk text, and true `smcp` rather than scaled capitals. Synthetic versions
distort the glyph and carry no semantic meaning, so `pybers` must be able to tell them
apart and must never write the fake form. All caps is a genuine feature Numbers supports
and `pybers` should support it too.

**Note on `calt`.** Contextual alternates were on throughout, as they almost always are.
So its presence is a baseline condition rather than a signal — a feature record appearing
does not by itself mean the fixture's feature was applied.

**Nothing further is needed for text properties.** 38-41 below are the remaining controls
from the "More Text Options" panel, and they are low priority — the structural lessons are
already learned.

---

## To make

Each line is one Save As from `00-baseline`, one change, save. Nothing else touched.

### Values

```
11-value-types-noformats  DONE, and the highest-yield fixture in the whole set. It
                        broke open the cell-value encoding, which is the one part of
                        the format the protobuf schemas do not describe at all — the
                        values live in an opaque binary buffer.

                        It worked because its second row labels every cell in text.
                        With known contents, nine unknown byte records became nine
                        verifiable ones. Any future fixture over an opaque encoding
                        should be built the same way: put the answer key in the file.

                        It also carried more than was asked — a star rating, slider,
                        stepper and popup menu — which established that interactive
                        controls are ordinary values plus a presentation reference,
                        not new value types. See FINDINGS.md.
```

### Number formats — after 11

These layer a display format over a value, which is a separate concern from the value
itself. `11` must come first or there is nothing to compare them against.

```
12-number-currency      DONE, and it settled the question both ways. Currency IS a
                        distinct cell type (10) but is NOT a distinct value
                        encoding — the decimal128 sits at the same offset as a
                        plain number. It also disproved the assumption that the
                        storage type byte is TST.CellType: 10 is in neither enum.
                        Nine variants in one file, with a plain number beside them
                        for comparison, is what made both conclusions provable.
                        See FINDINGS.md.
13-number-percent       DONE. Percent is NOT its own cell type — it is an ordinary
                        number plus a format, which is the opposite of currency and
                        makes the pair worth reading together. Confirmed the stored
                        value is always the fraction, never the displayed figure.
                        See FINDINGS.md.
14-number-date          DONE. Established that a date-time is ONE float64 — the time
                        lives in the value, not in a separate field — and that dates
                        keep type 5 whatever format is applied. Also exposed that the
                        trailing references start after the value, whose width varies
                        by type, so there is no fixed tail offset. See FINDINGS.md.
                        NOTE: col 4's label mentions 11:00 but the cell stores
                        00:00:00, unlike its neighbours 5 and 6. Worth a glance.
15-duration-formats     Durations are the one type whose FORMAT carries more
                        information than any other, because Numbers lets you choose
                        which units appear and in what style. One duration cell per
                        presentation, in the same file:
                          - a plain unformatted duration, for comparison
                          - hours and minutes only
                          - a range including milliseconds
                          - the compact style, e.g. 2h 30m
                          - the long style, e.g. 2 hours 30 minutes
                          - the colon style, e.g. 2:30
                        Two open questions this settles: whether the stored value
                        stays a plain seconds float64 across all of them (expected,
                        by analogy with percent and date), and whether duration cells
                        keep type 7 throughout or gain a distinct type the way
                        currency did. Currency is the only type so far that changed
                        its type byte for a format, so either answer is a finding.
16-number-scientific    One cell in scientific notation
17-number-custom        One cell using a custom format you define
```

Note these are *number formats*, not typography — but `onum` versus `lnum` (oldstyle
versus lining figures) is typography applied to numerals, and the two are stored in
different places. Keep them in separate fixtures so that stays visible.

### Formulas

```
18-formula-literals     THE BASELINE, and deliberately reference-free. Several
                        formulas that compute from literals only, so the formula
                        machinery is visible without any reference machinery mixed
                        into it. Whatever appears in 19 that is not here IS a
                        reference.
                          =1+1
                          =2*3
                          =SUM(1,2,3)          one function, several arguments
                          =ROUND(2.5,0)        ROUND needs value AND digits
                          =IF(1>0,1,2)         nesting plus a comparison operator
                          ="a"&"b"             string concatenation
                        Substitute freely if Numbers rejects any of these — the point
                        is a spread of shapes (operator, function, nesting, string),
                        not these exact calls.
                        Include one plain number cell as well, so a formula cell
                        and a value cell can be compared side by side.

19-formula-dragged      THE DECISIVE ONE — do not retype anything, DRAG it.
                        Values run ACROSS a row, matching the label-row pattern the
                        other fixtures use:
                          A1, B1, C1 = 1, 2, 3
                          A2, B2, C2 = 4, 5, 6      so dragged copies land on real
                                                    data rather than empty cells
                        Then three formulas in row 1, each dragged DOWN one row:
                          D1 = =SUM(A1:C1)          relative at both ends
                          E1 = =SUM($A$1:$C$1)      both ends fully locked
                          F1 = =$A1+B$1             ONE formula, mixed locking:
                                                    column locked on the first term,
                                                    row locked on the second
                          drag D1 -> D2, E1 -> E2, F1 -> F2
                        F1 is the sharpest test. Dragged down it should become
                        $A2 + B$1 — the $A holds the column while the row moves, the
                        $1 holds the row while the column does not. One formula
                        exercising both flags in opposite directions.
                        Three questions answered at once. If D1/D2/D3 hold
                        IDENTICAL stored bytes then references are relative offsets
                        and movement is structural — the good case, and the reason
                        Numbers needs no $ kludge. If they differ, references are
                        resolved addresses and pybers must do the shifting itself,
                        which is exactly where the range-shift bug in CLAUDE.md
                        lived. The E and F columns show how anchoring is encoded
                        differently — a flag on a reference, or a separate node.

20-formula-shapes       Variety in one file, once 18 and 19 have established the
                        basics. One cell each:
                          - a range argument:      =SUM(A1:A10)
                          - a multi-range SUMIFS   (the shape of the CLAUDE.md bug)
                          - a cross-sheet ref      =Sheet2::TableName::A1
                          - a whole-column ref     =SUM(A)
                          - a nested call          =IF(SUM(A1:A3)>0,"y","n")
                          - a reference to a cell that itself holds a formula

21-formula-errors       Formulas that fail, in one file:
                          - =1/0                       a division error
                          - a reference to a deleted cell, for the #REF shape
                          - =UNKNOWNFUNC(1)            an unresolvable name
                          - a circular reference, if Numbers will save one
                        Errors are their own cell type (formulaErrorCellType = 8),
                        so this establishes what a failed formula stores as opposed
                        to what it displays.
```

**Read 18 and 19 before making 20 and 21.** If 19 shows references are relative offsets,
the later fixtures answer different questions than if they are resolved addresses, and the
list above may want revising rather than following.

### Structure

```
22-merge-2x2            Merge A1:B2. Nothing else.
23-row-inserted         One row inserted
24-column-inserted      One column inserted
25-two-tables           A second table on the same sheet
26-two-sheets           A second sheet added
27-big-table            ~2000 rows of any values — enough to push one .iwa past
                        64 KB and force multi-frame chunking
```

### Cell styling

```
28-style-fill           One cell with a background fill color. This is
                        TST.CellStylePropertiesArchive.cell_fill — a THIRD thing,
                        distinct from both backgrounds in 08. See FINDINGS.md.
29-style-border         One cell with a border on one edge only
30-style-align          One cell set to centered
31-style-inset-2pt      One cell with the text inset reduced from the 4 pt default
                        to your usual 2 pt
32-style-inset-uneven   One cell with FOUR DIFFERENT insets if the UI allows it —
                        the archive stores left/top/right/bottom as independent
                        floats (TSWP.PaddingArchive), so this checks whether the
                        single-value UI control is a real constraint or just a
                        convenience. If Numbers will not let you, say so and skip.
33-named-style          One cell using a built-in NAMED style rather than manual
                        formatting — drives the named-styles decision in CLAUDE.md
```

### Floating objects

```
34-textbox              One floating text box with a word in it
35-shape                One drawn shape, a rectangle is fine
36-image                One small embedded image
37-image-and-shape      Both, to check they are independent
```

### Still unexplored from the "More Text Options" panel

That panel holds several controls no fixture covers yet, and each is a separate field:

```
38-text-charspacing     Character Spacing set to something other than 0%
39-text-baselineshift   Baseline Shift set to something other than 0 pt
40-text-outline         The Outline checkbox
41-text-shadow          The Shadow checkbox
```

Baseline Shift is worth having precisely because it is the manual way to fake a
superscript, so it needs to be distinguishable from both the synthetic `superscript`
enum and the real OpenType feature. Three routes to a similar look, three different
fields.

### Table bands and panes

Numbered from 41 to avoid renumbering the list again. Grouping is by section, not by
adjacent numbers.

```
42-table-bands          Set header rows = 1, header columns = 1, footer rows = 1,
                        all in one file. These are plain scalars on the table model
                        (number_of_header_rows / _header_columns / _footer_rows), so
                        one fixture covers all three.
43-table-frozen         Freeze the header row AND the header column. Note that
                        freezing (header_rows_frozen) is a SEPARATE field from
                        repeating-on-print (repeating_header_rows_enabled) — set only
                        freezing here so the two stay distinguishable.
44-style-band-vs-row    The important one. Give the HEADER row one fill and BODY row 3
                        a different fill, in the same file. The schema says a band has
                        a real style reference (header_row_style) while a body row has
                        none — so this should show one reference change for the header
                        and N per-cell styles for the body row. Confirms whether
                        "format a row" is a real operation or only sugar.
```

---

## Highest value first

**`18-formula-literals` and `19-formula-dragged` come before everything else**, and not
because formulas are the biggest feature. They are the only fixtures that can still change
the *object model*. Whether a formula is a string, a token list, or a tree carrying
relative references decides what `Cell` looks like, what "move a range" means, and whether
relocating cells is a walk over structure or a rewrite of text. Everything else on this list
refines knowledge that is already settled; these two can invalidate a design.

After those, and in this order:

**`22-merge-2x2`, `33-named-style`, `34-textbox`, `27-big-table`.**

`27-big-table` is the odd one out — it tests the container rather than the model, and it is
the only fixture that exercises the multi-frame path with real user data.

---

## Also worth reporting

- Numbers → Settings → General → *Save new documents as*: **Package** or **Single file**?
  Both are real container formats and the choice changes what is on disk.
- Any file where Numbers behaved unexpectedly, since that is itself a finding.

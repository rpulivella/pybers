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

**Made so far: 00 through 35, plus 22b.** Text and formatting are done. The cell-value
encoding is broken open for every type. Formulas are fully mapped. Merges, structural edits,
tiles, sheets, table geometry, the fill subsystem and the floating objects — text boxes,
shapes and images — are all understood.

**The object model has NO remaining unknowns.** `36-unicode-text` settled the last one:
`character_index` counts **UTF-16 code units**, not Python characters, across all nineteen
run tables that use it. Everything still to make adds coverage rather than architecture.

**`39` was freed and REUSED.** It was planned as `39-text-shadow`, but
`38-text-outline-shadow` covers both checkboxes in one file. The number now holds
`39-text-tabs-indents`, so the sequence stays gapless.

**Still to make, in the order worth doing them:**

1. `40-table-bands` and `45-table-titles` — header rows, header columns, footers and titles.
   Every fixture here has these switched OFF, which is NOT the Numbers default, so the most
   common table shape in the world is the one shape never tested. Worth promoting well above
   their numbers, and they are now the highest-value fixtures remaining.
2. `41-table-frozen`, `42-style-band-vs-row`, `43-table-geometry`, `44-table-dimensions` —
   the remaining table settings. Largely covered already by `25`, so these are about varying
   the values rather than discovering them.
3. `39-text-tabs-indents` — tab stops are entirely unexercised and are common in real
   documents. `TabArchive` carries a position, four alignments including decimal, and a
   leader string, none of it observed anywhere.
4. `47-line-ends` — MOSTLY DONE. The expanded `34-shape` mapped `TSD.LineEndArchive`
   completely. What remains is only the connector question: a connector actually attached to
   two shapes, since the one in `34` holds no reference to anything it connects.
5. `46-stroke-dashes` — now a single question, whether dash lengths are points or multiples
   of stroke width. Lowest value.

**Two smaller gaps, each needing one cell rather than a fixture:** an RTL cell with MIXED
formatting, to populate `table_para_bidi`, which is still `(0,0)` everywhere because every
RTL cell in `36` is a plain string; and a ZWJ emoji sequence such as a family or profession
emoji, which `36`'s skin-tone coverage does not include.

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

**Nothing further is needed for text properties.** 37-39 below are the remaining controls
from the "More Text Options" panel, and they are low priority — the structural lessons are
already learned. The one text fixture that is NOT low priority is `36-unicode-text`, which
is about how character indices are counted rather than about a formatting control.

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
15-number-duration-formats  DONE, and the most informative of the three. Proved
                        durations keep type 7 across EVERY format, so currency stays
                        the only type that changes its type byte for a format. Also
                        gave the controlled experiment identifying the format key as
                        the LAST trailing reference — one value, five presentations,
                        one slot moving. Plus three behaviors nobody asked for: a
                        leading apostrophe is an input directive and is not stored,
                        duration arithmetic coerces to HOURS, and feeding one value
                        into two DURATION() slots pins its argument order. See
                        FINDINGS.md.
16-number-scientific-numeralsystems  DONE, with a surprise: Numbers has NUMERAL SYSTEMS, base 2,
                        10 and 16 with configurable places and two's complement for
                        negatives. All display only — the value never changes.
17-number-custom        DONE. Established that ONE custom format archive holds its
                        positive, negative and zero presentations together, rather
                        than three formats chosen by sign.
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

20-formula-shapes       DONE. Established that cross-table references are relative
                        offsets plus a table UUID, that multi-range functions carry
                        each range as an independent node, and that a whole-column
                        reference is a coordinate with no row. See FINDINGS.md. The
                        original request is kept below for the record:

                        Put these across row 11 beside the existing SUM, then a
                        LABEL ROW in row 12 under each one saying what it is — the
                        labels are what make a decode checkable rather than assumed.

                          B11 = =SUM(A1:A10)+1
                                a range feeding an operator, to see how a tract and
                                an arithmetic node combine

                          C11 = =SUMIFS(A1:A10,A1:A10,">5")
                                TWO ranges plus a criteria string in one call. This
                                is the exact shape of the range-shift bug in
                                CLAUDE.md, so it is the most important single cell
                                in the file.

                          D11 = =IF(SUM(A1:A5)>10,"big","small")
                                a call nested inside a call, with a comparison and
                                two string literals — shows how nesting appears in
                                postfix order

                          E11 = =A11*2
                                a reference to a cell that ITSELF holds a formula,
                                which is a dependency rather than a value

                          F11 = =SUM(A)
                                a whole-column reference, made by clicking the
                                column header rather than typing. If Numbers writes
                                something different, that is the finding — an
                                unbounded range has to encode differently from
                                A1:A10. Skip it if the UI will not produce one.

                        THEN two structural references, which need company in the
                        document. Both are worth more than everything above:

                          G11 = a reference to a cell in a SECOND TABLE on the same
                                sheet. Add a small table, put a number in its first
                                cell, and point G11 at it by clicking rather than
                                typing so Numbers writes its own syntax.

                          H11 = a reference to a cell on a SECOND SHEET, same way.

                        G11 and H11 are the priority. Every reference seen so far is
                        an ASTLocalCellReferenceNodeArchive, and the schema also has
                        ASTCrossTableCellReferenceNodeArchive carrying a table UUID.
                        Nothing has ever populated it, so how a reference survives
                        leaving its own table is completely unknown — and it is the
                        mechanism that decides whether moving a table breaks the
                        formulas pointing into it.

21-formula-errors       DONE, and richer than asked. Established that a broken
                        reference is node type 46 with sentinel coordinates, that an
                        unknown function keeps its spelling, that circularity is not
                        recorded at all, and that the FORMULA_ERROR list is empty —
                        the KIND of error is not stored. See FINDINGS.md.
```

**Read 18 and 19 before making 20 and 21.** If 19 shows references are relative offsets,
the later fixtures answer different questions than if they are resolved addresses, and the
list above may want revising rather than following.

### Structure

```
22-merge-2x2            DONE, and it carries far more than the name suggests: five
                        merges across row 0, two of them merging cells that already
                        held content, plus formulas reading both a merge anchor and a
                        covered cell. That range is what made the findings possible.
22b-merge-2x2-unmerged  The SAME file with every merge removed and nothing else
                        touched. This pair is what located merge storage — a presence
                        check had already failed, because the field exists in both and
                        only its CONTENT differs. Established that merges live in
                        TableModelArchive.merge_owner.formula_store as full formula
                        archives, that merging is destructive and unmerging does not
                        undo it, and that a reference to a covered cell errors and
                        recovers. See FINDINGS.md.

                        THE PATTERN WORTH REUSING: when a feature cannot be located,
                        make the same file with and without it. Two files differing in
                        one property beat any amount of searching by field name.
23-row-inserted         DONE, and it explained an existing bug. Numbers DOES rewrite
                        merge ranges on a structural edit — the originals moved from
                        row 0 to row 1. Inserted rows also INHERIT the merge pattern
                        of their neighbour, so 5 merges became 15, and a merge can
                        cover entirely empty cells. See FINDINGS.md.

24-column-inserted      DONE, and it proved rows and columns differ. Merges shifted
                        to their new columns correctly, but NO new merges were
                        created — where a row insert created ten. Testing only one
                        axis would have produced the wrong rule for both.

25-multi-tables         DONE, and it answered more than asked. Sheets hold an ORDERED
                        list of drawable_infos and a table is simply a drawable.
                        TableInfoArchive.super carries geometry — position, size,
                        angle, locked — so tables can be ROTATED. This largely covers
                        what 45 and 47 were meant to discover.

26-multi-sheets         DONE. Three sheets, one with a tab color and one with a
                        background color. Both live in SheetStyleArchive
                        .sheet_properties (tab_color and fill), NOT as sheet fields —
                        and the styled sheets carry parent + is_variation + an
                        override_count, which is the named-style layering from
                        CLAUDE.md decision 2 visible in the wild.

27-big-table            DONE, and it was discovery rather than confirmation. A table
                        over 256 rows SPLITS INTO TILES — 2001 rows became 8. Two
                        traps followed: tile_row_index restarts at 0 in every tile, so
                        a document row is tileid * tile_size + tile_row_index; and
                        tile archive identifiers are NOT in row order, so
                        TileStorage.tiles is the authoritative sequence. Built by
                        importing a generated CSV, which breaks Save-As lineage — fine
                        here, because this fixture is not compared against a baseline.
```

### Cell styling

```
28-style-fills          DONE, and it opened the whole fill subsystem. Ten variants in
                        one row: no fill, white, solid, solid with alpha, standard and
                        advanced gradients, radial, and three image fills. Established
                        that a fill is a three-way union (color / gradient / image),
                        that COLOR CARRIES A COLOR SPACE which varies within a single
                        gradient, that gradient stops have an inflection midpoint, and
                        that an image fill can reference data not present in the
                        document. See findings-06-styles.md.

                        EXTENDED with a real 1024x1024 PNG across six fills, which
                        closed the image question: a supplied image becomes a zip
                        member under Data/, its filename carries the asset id, the
                        bytes are stored UNMODIFIED and byte-identical to the source,
                        and one copy serves every fill. Techniques are a small enum
                        and scale is stored as a rendered fillsize in points, not a
                        percentage. The tile itself is tests/fixtures/tile-pattern.png,
                        generated by workarea/make-tile.py — seamless by construction
                        and original, so there is no licence to track.
29-style-border        DONE, and it disproved all three reasonable guesses. Five
                        tables: per-cell borders, table outline, gridlines on, off,
                        and banding. Table-level settings write NOTHING into the
                        stroke sidecar — they are a separate mechanism in the table
                        style, not convenience over cell borders. And a single line
                        between two cells is stored TWICE, once on each facing edge.
                        See findings-06-styles.md.
30-style-align          DONE, and it resolved the variable-length style tail. The
                        STYLE list is HETEROGENEOUS — horizontal alignment is a
                        paragraph style, vertical alignment and wrap are cell styles,
                        and a cell referencing both carries two style keys. Also
                        established the alignment enum by measurement, because the
                        schema ships it with placeholder names (TATvalue0..4). See
                        findings-06-styles.md.
31-style-inset-2pt          DONE, and extended with the indent controls that sit beside
                        inset in the UI. Established that insets are CELL padding
                        while indents are PARAGRAPH properties — the cell owns its
                        box, the paragraph owns its text. Also confirmed everything
                        is stored in points (0.25in -> 18.0) and that the 4pt default
                        writes no style at all. See findings-06-styles.md.
32-named-styles         DONE, and it ANSWERED CLAUDE.md decision 2. Applying a named
                        style writes a REFERENCE to the shared style; formatting on top
                        of one creates an anonymous VARIATION carrying parent,
                        is_variation and override_count, storing only the overridden
                        properties. The design CLAUDE.md proposed — a style reference
                        plus an optional local override — is what Numbers does.

                        Two things nobody predicted. override_count counts LOGICAL
                        properties, not fields: a color change stores font_color and
                        tsd_fill but counts as 1. And there is NO unparented text
                        style — the cell labelled "manually styled" is still a
                        variation of Body, so manual formatting is an anonymous
                        variation of a named style rather than the absence of one.

                        Also recorded in the fixture's own text: character styles
                        cannot be applied to a cell at all, only to selected text.
                        See findings-06-styles.md.
```

### Floating objects

```
33-textbox              DONE, and far richer than the name. Settled the UNITS question
                        for the whole format with an arrow-key nudge ladder, and
                        proved a vertical flip is a horizontal flip plus a 180-degree
                        rotation rather than a bit of its own.
34-shape                DONE, and it carries the single most important structural
                        fact in the drawable layer: Numbers SHARES style archives by
                        reference between shapes. Also z-ordering, three separate
                        encodings of "off", and nine different shape kinds.
35-image                DONE. Thirteen placements covering scaling, rotation,
                        flipping, locking, deliberate distortion and four crops.
```

### Unicode — NOT COVERED, and one hazard is live

The corpus contains four non-ASCII characters in total, all smart quotes Numbers inserted
by autocorrect, all in the Basic Multilingual Plane. **Zero astral-plane characters.** So
nothing here tests Unicode deliberately.

**DONE, and it ANSWERED the question it was promoted for.** `character_index` counts
**UTF-16 code units**, not Python characters. The decisive cell is `AB𠮟CD` with `AB` bold and
`CD` in a small-caps character style: the third run begins at index **4**, where Python
indexing would put it at 3. Only the UTF-16 reading reconstructs `AB` / `𠮟` / `CD`; the scalar
reading yields `AB` / `𠮟C` / `D` — plausible, wrong, and silent. pybers assumed Python offsets
and that assumption is now known to be wrong. Full detail in
[findings-04-text.md](findings-04-text.md).

It also established, none of which was asked for: Arabic-Indic digits typed into a NUMBER cell
are parsed and stored as decimal `123` with the digits gone entirely; Numbers normalizes to
**precomposed** form on entry, so a long-pressed `é` stores as one character; and a
skin-toned emoji is a **base plus a separate modifier code point**, where neither half is
reliably astral.

**Two things `36` could NOT answer, needing one more fixture each:**

```
RTL run tables      All four RTL cells are PLAIN STRINGS, which have no
                    StorageArchive and therefore no run tables at all. So
                    table_para_bidi is still (0,0) and its two uint32 fields
                    remain unmapped, as does table_language beyond "en".
                    NEEDS: an RTL cell with MIXED FORMATTING, which is what
                    forces a rich-text payload to exist.

ZWJ sequences       The emoji cell covers skin-tone modifiers and variation
                    selectors but contains no zero-width-joiner sequence.
                    NEEDS: a family emoji or a profession emoji, which are
                    several code points joined by U+200D.
```

```
36-unicode-text         ONE cell per case, labelled as usual:
                          - accented Latin: naive, cafe with an acute, Straße   [DONE]
                          - CJK: see the paste-ready block below
                          - EMOJI, and more than one — this is the important case
                          - an emoji with a skin-tone modifier, and a family emoji
                            (those are multi-codepoint sequences)
                          - Hebrew or Arabic, for right-to-left
                          - a combining sequence: e + combining acute, typed so it
                            stays decomposed if Numbers allows it
                          - a cell mixing ASCII and emoji with DIFFERENT FORMATTING
                            on each side of the emoji

                        THE LAST ONE IS THE POINT. StorageArchive.table_char_style
                        indexes style runs by `character_index`, and Apple's text
                        stack is NSString, which counts UTF-16 code units. Python
                        counts scalars. For BMP text the two agree exactly, which is
                        why 02-text-rich validated perfectly and proved nothing. One
                        emoji makes a Python character two UTF-16 units, and every run
                        boundary after it drifts — silently, producing plausible wrong
                        runs rather than an error.

                        pybers currently ASSUMES the indices are Python offsets. That
                        assumption is untested and probably wrong.

                        It is not only the char style table. `33-textbox` showed a
                        StorageArchive carries TWENTY-ONE parallel run tables,
                        NINETEEN of them keyed by character_index — styles, language,
                        bidi, drop cap, dictation, tracked changes. All nineteen drift
                        together, and a structural edit has to reindex every one.
```

#### CJK — paste-ready, one cell each

The first five are BMP and prove nothing about indexing; they cover encoding, script mixing
and normalization. **The last four are the ones that matter**, because a Python scalar count
and a UTF-16 count disagree on every one of them.

```
你好世界                          py  4   utf16  4   Han, Simplified
漢字測試                          py  4   utf16  4   Han, Traditional
日本語のテスト、カタカナ混じり    py 15   utf16 15   kanji + hiragana + katakana
한국어                            py  3   utf16  3   Hangul, PRECOMPOSED
ＡＢＣ１２３                      py  6   utf16  6   full-width forms
𠀋𠮟𡈽                            py  3   utf16  6   CJK Extension B, astral
𪚲                                py  1   utf16  2   near the end of Ext B
AB𠮟CD                            py  5   utf16  6   THE DECISIVE CELL
```

Plus one that **cannot be written into this file**, for a reason that is itself the finding:

```
U+2F804    a CJK COMPATIBILITY ideograph, astral, py 1 / utf16 2
           renders identically to U+4F60, the first character of 你好世界
           produce it with:  python3 -c 'print("\U0002F804")'
```

Three of these are deliberately sly:

- **U+2F804 looks exactly like U+4F60 and is twice the length.** It is a compatibility
  ideograph with a canonical decomposition, so **any NFC normalization anywhere in the path
  silently replaces it with the ordinary BMP character** — which is what happened on the
  first attempt to write it into this README, turning a 2-unit astral character into a
  1-unit BMP one with nothing to show for it. Generate it at the terminal with the command
  above rather than copying it from anywhere, and check the cell afterwards. Visually
  indistinguishable, different length in the file: exactly the shape of error this format
  specializes in producing without complaint.
- **`한국어` tests whether Numbers NORMALIZES on entry.** Precomposed it is 3 characters;
  decomposed into jamo (`U+1112 U+1161 U+11AB U+1100 U+116E U+11A8 U+110B U+1165`) it is 8,
  and both display identically. If a decomposed paste comes back as 3, Numbers applied NFC,
  and a round trip must not silently reapply or undo that. The Japanese line has the same
  property in miniature — `じ` is one character in NFC and two in NFD.
- **`AB𠮟CD` is the whole experiment.** Format `AB` one way and `CD` another, leaving the
  astral character between them untouched. The second run's `character_index` will be **4**
  if Numbers counts UTF-16 code units and **3** if it counts Python scalars. Label which
  formatting is on which side — that label is the answer key, and without it the result is
  a number with nothing to check it against.

One cell, an unambiguous answer, and it decides how nineteen run tables are indexed.

#### Hebrew and Arabic — paste-ready, one cell each

Every one of these is BMP, so a Python count and a UTF-16 count agree and **none of them
tests the indexing question**. They are here for a different unknown: `table_para_bidi` is a
`ParaDataAttributeTable` carrying two `uint32` fields, `first` and `second`, and both are
`0, 0` in every fixture made so far. Mixed-direction text is the only thing that can populate
it.

```
שלום עולם            py  9  utf16  9  bidi R,WS      plain Hebrew
שָׁלוֹם                 py  7  utf16  7  bidi R,NSM     Hebrew WITH NIQQUD
مرحبا بالعالم        py 13  utf16 13  bidi AL,WS     plain Arabic
مَرْحَبًا                py  9  utf16  9  bidi AL,NSM    Arabic WITH HARAKAT
abc שלום def         py 12  utf16 12  bidi L,WS,R    direction changes TWICE
שלום 123 עולם        py 13  utf16 13  bidi R,WS,EN   European digits inside RTL
١٢٣                  py  3  utf16  3  bidi AN        Arabic-Indic digits
אב𠮟גד               py  5  utf16  6  bidi R,L       RTL *and* astral
```

What each is actually for:

- **`abc שלום def` and `שלום 123 עולם` should be the first cells in the corpus to make
  `table_para_bidi` non-zero.** Until something does, the meaning of `first` and `second`
  cannot be established at all.
- **The niqqud and harakat cells test what "one character" means.** `שָׁלוֹם` is 4 visible
  letters, 7 code points and 7 UTF-16 units, with 3 combining marks; the Arabic one carries
  4. If `character_index` should turn out to count grapheme clusters rather than code units,
  these are the only cells that can reveal it — Latin and CJK samples have no combining
  marks and would agree either way.
- **`١٢٣` is bidi class `AN`, not `EN`.** Arabic-Indic digits are a different directional
  class from the European digits one line above, so the two cells together separate "there
  are digits" from "there are digits of a particular class".

Arabic letters join contextually when rendered but are **stored as isolated code points**, so
a decode that shows unjoined forms is correct rather than broken. Do not chase it.

### The "More Text Options" panel — mostly covered now

`37` and `38` are done and both carried far more than their names suggested. What is left of
this panel is tabs and indents, specced below as `39`.

```
37-text-baselineshift   DONE, and it went well beyond the ask. Established that
                        baseline_shift is SIGNED POINTS and is the third route to a
                        raised character, alongside the synthetic superscript enum
                        and the real OpenType feature. Also: a uniform shift over a
                        whole cell stays a PLAIN STRING and puts the character
                        property on a ParagraphStyleArchive; a saved NAMED character
                        style is a root with no parent while an ad-hoc one is an
                        anonymous variation of the character style named 'None'; and
                        line_spacing has four modes (kExactLineSpacing,
                        kMinimumLineSpacing, kSpaceBetweenLineSpacing, unset) carried
                        as a mode-plus-amount sub-message rather than a bare number.

38-text-outline-shadow  DONE, and it covers BOTH checkboxes in one file plus two
                        findings neither was asked for.

                        It DECODED THE DASH ARRAY that 34-shape left unexercised:
                        text outline is a tsd_stroke, the same stroke message a
                        shape border uses, and the fixture carries solid, dotted,
                        dashed, wide-dashed and circular-dotted. count says how many
                        of the six slots are live (2 for a dash/gap pair), a solid
                        stroke uses its own TSDSolidPattern and leaves the array
                        empty, and circular dots are a ZERO-LENGTH dash with a round
                        cap rather than a distinct pattern kind.

                        It also settled what the *_null booleans mean. shadow_null =
                        True is an override to EXPLICITLY NOTHING, not "unspecified"
                        — it counts toward override_count exactly as setting a value
                        does. And its own label caught, and correctly diagnosed, that
                        text shadow is specified at BOTH the cell level and the
                        character-run level, so resolving one means walking both.

                        EXPANDED with the five brush strokes, which turn out to be
                        named rather than described: StrokeArchive.smart_stroke holds
                        a stroke_name string ('Chalk2', 'Feathered Brush',
                        'Calligraphy', 'Dry Brush', 'Pen') plus a random_seed. Their
                        `pattern` is an ordinary TSDSolidPattern, so a reader checking
                        only the pattern would call a chalk stroke solid.
```

Baseline Shift is worth having precisely because it is the manual way to fake a
superscript, so it needs to be distinguishable from both the synthetic `superscript`
enum and the real OpenType feature. Three routes to a similar look, three different
fields.

### Tabs, indents and paragraph borders

The "More Text Options" panel also offers indents, tab stops and paragraph borders. Indents
are partly covered by `31-style-inset-2pt`, which picked up the controls sitting beside the
inset, but tabs are not covered at all and they are common in real documents.

```
39-text-tabs-indents    TABS are the point. TabsArchive holds a repeated TabArchive,
                        each with a `position` float, an `alignment` of
                        left / center / right / DECIMAL, and a `leader` STRING.
                        None of that is exercised anywhere in the corpus.

                          - one cell using only the default tab stops, to see what
                            `default_tab_stops` (a float, 36.0 in the theme) means
                            when no explicit stop exists
                          - one cell with several EXPLICIT stops at different
                            positions, one of each alignment
                          - at least one stop with a LEADER, the dotted run-in used
                            in a table of contents. It is a string field, so what
                            actually goes in it is worth knowing.
                          - a DECIMAL tab with numbers that have differing digit
                            counts, since `decimal_tab` is a separate string field
                            holding "." in the theme and presumably follows the
                            locale

                        INDENTS: first_line_indent, left_indent and right_indent are
                        three separate floats. Set all three to DIFFERENT values in
                        one cell so they cannot be confused, and make one cell a
                        HANGING indent (first line further left than the body),
                        which should show as a negative first_line_indent.

                        PARAGRAPH BORDERS are rare — this developer has never used
                        one, nor seen one in a shared document — so they are the
                        lowest priority here and one cell is enough. They are worth
                        a single sample only because pybers must not damage what it
                        does not understand: `border_positions` (an int32 bitmask),
                        `stroke` plus `stroke_null`, and `rule_width` all sit on
                        every paragraph style already, reading 0 or unset. One cell
                        with a border proves whether carrying them through unchanged
                        is sufficient.

### Table bands and panes

Grouping is by section, not by adjacent numbers. The list was renumbered once, when
`unicode-text` was promoted from `45` to `36` — it is a correctness precondition rather
than coverage — so anything referring to the old numbers is stale.

```
40-table-bands          Set header rows = 1, header columns = 1, footer rows = 1,
                        all in one file. These are plain scalars on the table model
                        (number_of_header_rows / _header_columns / _footer_rows), so
                        one fixture covers all three.
41-table-frozen         Freeze the header row AND the header column. Note that
                        freezing (header_rows_frozen) is a SEPARATE field from
                        repeating-on-print (repeating_header_rows_enabled) — set only
                        freezing here so the two stay distinguishable.
42-style-band-vs-row    The important one. Give the HEADER row one fill and BODY row 3
                        a different fill, in the same file. The schema says a band has
                        a real style reference (header_row_style) while a body row has
                        none — so this should show one reference change for the header
                        and N per-cell styles for the body row. Confirms whether
                        "format a row" is a real operation or only sugar.
```

### Table geometry and placement — NOTHING covers this yet

Every fixture so far describes what is *in* a table. None describes the table as an object
on a canvas: where it sits, how big it is, or how wide its columns are. A round trip that
loses any of that has damaged the document just as surely as losing a value.

```
43-table-geometry       One table moved somewhere deliberate on the canvas, with
                        several column widths and row heights set BY HAND to
                        distinctly different values — not dragged approximately,
                        typed if the UI allows, so the numbers are recognizable in
                        the archive.
44-table-dimensions     Three tables on one sheet with clearly different row and
                        column COUNTS: one tall and narrow, one short and wide, one
                        single-cell. Dimensions are separate from placement and
                        should be confirmed separately.
45-table-titles         The table title and header settings that every other fixture
                        has had switched OFF. One table with its title shown, one
                        with header rows, header columns and a footer row all
                        present. This is the DEFAULT Numbers state, so it is what
                        most real documents look like — the fixtures so far are the
                        unusual ones.
```

**Note for every fixture already made:** table titles were unchecked and header rows,
header columns and footers were all set to zero, which is *not* the Numbers default. That
was the right call for isolating cell behavior, and it means these fixtures are
deliberately atypical. `45-table-titles` exists so the default shape is covered too, and
nothing assumes the stripped-down form is normal.

### Drawable gaps — one closed, one narrowed

`47-line-ends` was closed by expanding `34-shape` itself; what is left of it is the connector
question. `46-stroke-dashes` was answered from an unexpected direction, by text outlines in
`38`, and is now down to a single measurement.

```
46-stroke-dashes        NARROWED TWICE, now a single question. 38-text-outline-shadow
                        decoded the dash array from text outlines, and 29-style-border
                        confirmed CELL BORDERS USE THE IDENTICAL ENCODING — one stroke
                        message serves shapes, cells and text, and only the menus
                        differ.

                        Every dashed stroke in the corpus has width 1.0, so whether
                        the dash numbers are POINTS or MULTIPLES OF THE STROKE WIDTH
                        cannot be told apart. One line or cell border with a DASHED
                        stroke at two clearly different widths — say 1pt and 4pt —
                        settles it. Nothing else is needed.

47-line-ends            MOSTLY DONE. 34-shape was expanded with ten lines carrying
                        arrowheads, which mapped TSD.LineEndArchive completely: an
                        `identifier` name, the FULL path, `is_filled`, and an
                        `end_point` that MAY BE NEGATIVE so the line stops short of
                        the marker. Ten presets observed — simple / filled / inverted
                        / open arrow, filled / open circle, filled / open square,
                        filled diamond, and line — every one authored in a 6x6 box.

                        Unlike smart_stroke, which gives only a name, a line end
                        carries its geometry, so pybers can render one without
                        Apple's engine. head and tail are independently settable; the
                        fixture holds head fixed and varies only the tail, which is
                        what proves which field is which.

                        WHAT REMAINS is only the connector question: draw a connector
                        and actually ATTACH it to two shapes. The connector in 34
                        holds no reference to anything it connects, so either it was
                        unattached or attachment is recorded somewhere not yet found.
```

---

## Highest value first

Every fixture that could reshape the object model is made and read, with one exception.
What else follows adds coverage.

**`36-unicode-text` is the exception, and should be next.** It is the last fixture that can
still change a design decision. `32-named-styles` answered CLAUDE.md decision 2 and is done;
this one decides how `character_index` is counted, which nineteen run tables depend on.

**`40-table-bands` should be promoted well above its number.** Every fixture in this
directory has header rows, header columns, footers and titles switched OFF, which is *not*
the Numbers default. The most common table shape in the world is therefore the one shape
never tested here, and `HeaderStorageBucket-*.iwa` members appear in every file without ever
having been opened.

The floating objects `33`-`35` are done. After the two above, in rough order of value: the
remaining table settings (`41`-`44`), the two drawable gaps (`46`-`47`), and the last text
controls (`37`-`39`), which are lowest.

---

## Also worth reporting

- Numbers → Settings → General → *Save new documents as*: **Package** or **Single file**?
  Both are real container formats and the choice changes what is on disk.
- Any file where Numbers behaved unexpectedly, since that is itself a finding.

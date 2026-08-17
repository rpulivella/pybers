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

`10-text-ligatures` answered its own open question once its text was rewritten to say that
the paragraph is None *and* specific letters are overridden to Default. That layered case is
the most valuable thing in the set so far, and it exposed the next real gap: proving which
characters a style applies to needs the style **run table**
(`StorageArchive.table_char_style`), which pybers does not parse yet. Until then, findings can
say what styles exist and what they contain, but not which text they cover.

---

## To make

Each line is one Save As from `00-baseline`, one change, save. Nothing else touched.

### Text and formatting

```
04-text-monospace       One cell in a monospaced font, no other formatting
05-opentype             One cell using OpenType features only (onum, pnum, liga)
                        with no bold/italic/color, so the feature bits are alone
06-strikethrough        One cell struck through
07-text-superscript     Superscript and subscript done with the OpenType features
                        (sups, subs) and an ordinal with ordn — NOT the app's
                        synthetic raise-and-shrink. If Numbers offers both, put
                        the real feature version in this file. Add one synthetic
                        one too, in a separate cell, purely so the two are
                        distinguishable in the archive.
08-text-para-backgrounds  DONE, and it corrected a wrong expectation. The UI calls
                        this "Text Background" and offers it in the character
                        panel, but it writes to TWO DIFFERENT FIELDS by scope:
                        paragraph scope -> ParagraphStylePropertiesArchive.fill,
                        character scope -> CharacterStylePropertiesArchive
                        .background_color. This fixture carries one of each and
                        says which is which in its own text, which is what made
                        the difference findable. See FINDINGS.md.
09-text-capitalization  All caps via the real feature, plus a small-caps run if
                        the font has true small caps (smcp). Never the fake kind
                        — scaled-down capitals are not small caps.
                        LEARNED WHILE MAKING THIS: Numbers' own all-caps setting
                        alone renders badly. It needs both OpenType capital
                        features enabled alongside it — case-sensitive forms and
                        capital spacing — because capitals set with lowercase
                        sidebearings and lowercase-height punctuation look wrong.
                        So all caps is TWO settings in two different places, and
                        pybers must carry both or it will produce ugly output
                        while believing it matched.
10-text-ligatures       DONE, and it also corrected an expectation: ligatures are
                        NOT stored as AAT feature pairs at all. Numbers uses its
                        own LigaturesType enum, and "Use Default" writes nothing.
                        See FINDINGS.md. The screenshot of "More Text Options" is
                        what identified the other unexplored controls now listed
                        as 36-39 below.
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

### Numbers and formats

```
11-number-currency      One cell = 1234.5 as currency
12-number-percent       One cell = 0.25 as percent
13-number-date          One cell holding a date
14-number-scientific    One cell in scientific notation
15-number-custom        One cell using a custom format you define
```

Note these are *number formats*, not typography — but `onum` versus `lnum` (oldstyle
versus lining figures) is typography applied to numerals, and the two are stored in
different places. Keep them in separate fixtures so that stays visible.

### Formulas

```
16-formula-sum          A1:A3 = 1,2,3 and A4 = =SUM(A1:A3)
17-formula-sumifs       A SUMIFS with a range argument
18-formula-crosssheet   A formula referencing a cell on a second sheet
19-formula-error        A formula that deliberately errors (=1/0)
```

### Structure

```
20-merge-2x2            Merge A1:B2. Nothing else.
21-row-inserted         One row inserted
22-column-inserted      One column inserted
23-two-tables           A second table on the same sheet
24-two-sheets           A second sheet added
25-big-table            ~2000 rows of any values — enough to push one .iwa past
                        64 KB and force multi-frame chunking
```

### Cell styling

```
26-style-fill           One cell with a background fill color. This is
                        TST.CellStylePropertiesArchive.cell_fill — a THIRD thing,
                        distinct from both backgrounds in 08. See FINDINGS.md.
27-style-border         One cell with a border on one edge only
28-style-align          One cell set to centered
29-style-inset-2pt      One cell with the text inset reduced from the 4 pt default
                        to your usual 2 pt
30-style-inset-uneven   One cell with FOUR DIFFERENT insets if the UI allows it —
                        the archive stores left/top/right/bottom as independent
                        floats (TSWP.PaddingArchive), so this checks whether the
                        single-value UI control is a real constraint or just a
                        convenience. If Numbers will not let you, say so and skip.
31-named-style          One cell using a built-in NAMED style rather than manual
                        formatting — drives the named-styles decision in CLAUDE.md
```

### Floating objects

```
32-textbox              One floating text box with a word in it
33-shape                One drawn shape, a rectangle is fine
34-image                One small embedded image
35-image-and-shape      Both, to check they are independent
```

### Still unexplored from the "More Text Options" panel

That panel holds several controls no fixture covers yet, and each is a separate field:

```
36-text-charspacing     Character Spacing set to something other than 0%
37-text-baselineshift   Baseline Shift set to something other than 0 pt
38-text-outline         The Outline checkbox
39-text-shadow          The Shadow checkbox
```

Baseline Shift is worth having precisely because it is the manual way to fake a
superscript, so it needs to be distinguishable from both the synthetic `superscript`
enum and the real OpenType feature. Three routes to a similar look, three different
fields.

---

## Highest value first

If you want to stop early, these cover every distinct *kind* of thing, and the rest only
sharpen the mapping:

**`16-formula-sum`, `20-merge-2x2`, `31-named-style`, `32-textbox`, `25-big-table`.**

`25-big-table` is the odd one out — it tests the container rather than the model, and it is
the only fixture that exercises the multi-frame path with real user data.

---

## Also worth reporting

- Numbers → Settings → General → *Save new documents as*: **Package** or **Single file**?
  Both are real container formats and the choice changes what is on disk.
- Any file where Numbers behaved unexpectedly, since that is itself a finding.

# Cell records: where the formula key sits

A cell record ends in a run of 32-bit references, and which one holds the formula key
moves as the cell gains attributes. Measured for PYB-65, which PYB-66 shared a cause with.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## The key is not at a fixed position, and reading it as though it were deletes work

Byte 9 bit `0x02` says a cell is backed by a formula, and the key naming that formula is one
of the record's trailing references. Three bits in byte 8 and one in byte 9 each put a
reference **ahead** of it:

```
slot = popcount(byte8 & 0xE0) + (byte9 & 0x01)
```

A plain cell puts the key first. A cell with a fill and an alignment puts it third. Add
conditional highlighting and it is fifth.

Reading a fixed position fails in two different ways, and neither raises:

- the value there is **not a key the pool holds**, so the cell reads as though it never had
  a formula, and the writer then removes the formula from the file;
- the value there **is** a key, by accident, so the cell reads as a different formula than
  the file contains. A formula is a set of offsets from the cell holding it, so attributing
  one to the wrong cell moves every reference in it. In `47-formula-cell-attributes` that
  produced `=A-2*A-1`, a column two places before the first.

Across one real five-sheet document, 416 formulas were dropped and removed on save, and 66
resolved to a column at or before zero.

## How the rule was validated

A pooled formula carries a `refcount` recording how many cells name it. For each table,
take the key each record names under a candidate rule, count them, and compare the histogram
against the pool's own refcounts. A wrong rule almost never reproduces one by accident.

```
rule                                       pools reproduced
1 if byte8 & 0x40 else 0                        11 / 22
popcount(byte8 & 0x60)                          21 / 22
popcount(byte8 & 0xE0) + (byte9 & 0x01)         22 / 22
```

Twenty-two tables, roughly 1,700 formula records, eleven distinct flag shapes, across the
46 fixtures and one real document. The rule that shipped before this was fitted to a
set of fixtures where exactly one set `0x40`, so a constant slot read every other file
correctly.

## What each bit is

Named from the fixtures that label their own contents, which is why they were worth building:

```
byte 8  0x20   a cell style         98b-cell-box-styles: set by a fill, a vertical
                                    alignment, wrap cleared and a 6pt inset alike
        0x40   a paragraph style    98b-cell-box-styles: set by a horizontal
                                    alignment and by bold alike
        0x80   conditional          47: the one highlighted cell is the only cell
               highlighting         with the bit, and the reference it contributes
                                    is the table's single conditionalstyletable key

byte 9  0x01   always set with 0x80, contributing one more reference
        0x02   the formula flag itself
```

**A comment adds a reference BEHIND the key**, so it does not move it. Measured on the one
real document: of twenty cells sharing flags `0x61` / `0x52`, exactly two carry an extra
reference, and those two are the two cells with comments.

## What is still unknown

~~**Bytes 8 and 9 do not fully determine how many trailing references a record carries.**
The two commented cells above share their flag bytes with eighteen others and carry one
more reference than they do, so at least one more gate lives somewhere else.~~ **Answered
for PYB-61 on 2026-09-14: the gate is byte 10.** The count is
`popcount(byte8 & 0xE0) + popcount(byte9) + popcount(byte10)`, with no exceptions in
11,760 records. See [findings-01-values.md](findings-01-values.md).

## Which style each of `0x20` and `0x40` names

Measured for PYB-265 on 2026-11-12 in `98b-cell-box-styles`, ten cells each holding `1`, styled
by hand in Numbers 15.4 with one change per column. **A table keeps its cell styles and its
paragraph styles in one `styleTable`**, keys unique across both, so a key alone does not say
which kind it names. The slot does, and the archive type each key resolves to confirms it:

```
cell  styled with                     byte 8  references   resolves to
A1    nothing                         0x01    1 1          (the two format slots only)
B1    fill 255 214 10                 0x21    2 1 1        2 CellStyleArchive, cell_fill
C1    fill 255 0 0                    0x21    3 1 1        3 CellStyleArchive, cell_fill
D1    vertical alignment Center       0x21    1 1 1        1 CellStyleArchive, vertical_alignment 1
E1    Wrap Text in Cell cleared       0x21    4 1 1        4 CellStyleArchive, text_wrap false
F1    Text Inset 6 pt                 0x21    6 1 1        6 CellStyleArchive, padding 6 on all four sides
G1    horizontal alignment Right      0x41    5 1 1        5 ParagraphStyleArchive, alignment
H1    Bold                            0x41    7 1 1        7 ParagraphStyleArchive, bold
I1    fill and Right                  0x61    2 5 1 1      cell style, then paragraph style
J1    as I1, and highlighting         0xE1    2 5 2 0 1 1  cell, paragraph, conditional set, matched rule 0
```

The references follow the bits in ascending order: cell style, paragraph style, conditional
style set, then byte 9's. Every style is an unnamed variation of the table's own style of
its kind. Numbers shares one variation among cells styled alike: B1, I1 and J1 name cell
style 2, refcount 3, and G1, I1 and J1 name paragraph style 5, refcount 3.

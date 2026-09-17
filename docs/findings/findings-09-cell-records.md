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

A pooled formula carries a `refcount` recording how many cells name it. So for each table,
take the key each record names under a candidate rule, count them, and compare the histogram
against the pool's own refcounts. A wrong rule almost never reproduces one by accident.

```
rule                                       pools reproduced
1 if byte8 & 0x40 else 0                        11 / 22
popcount(byte8 & 0x60)                          21 / 22
popcount(byte8 & 0xE0) + (byte9 & 0x01)         22 / 22
```

Twenty-two tables, roughly 1,700 formula records, eleven distinct flag shapes, across the
46-fixture corpus and one real document. The rule that shipped before this was fitted to a
corpus where exactly one fixture set `0x40`, so a constant slot read every other file
correctly.

## What each bit is

Named from the fixtures that label their own contents, which is why they were worth building:

```
byte 8  0x20   a cell fill          28-style-fills: A1 "No fill" has it clear,
                                    every filled cell has it set
        0x40   explicit horizontal  30-style-align: B1 "h: auto" clear,
               alignment            C1 "h: left" and E1 "h: right" set
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

The reference each preceding bit contributes is identified only for `0x80`. The values
`0x20` and `0x40` contribute are plausible keys in more than one per-table list at once, so
naming them would take a fixture built to separate those lists.

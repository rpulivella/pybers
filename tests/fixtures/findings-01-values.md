# Cell values and number formats

The cell record layout, the value encodings, and how formats attach to a value without
changing it. This is the part of the format the protobuf schemas do not describe.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## Cell values: the one place the schemas stop helping

`TST.Tile` holds rows as `TileRowInfo`, and the values are **not protobuf**. They live in an
opaque `cell_storage_buffer`, indexed by a `cell_offsets` array. Everything below was
reverse-engineered against `11-value-types-noformats`, whose second row labels every cell in
text, which is the only reason the decode is verifiable rather than plausible.

```
cell_offsets           uint16 always; 0xFFFF means NO CELL, and an empty cell has
                       no record at all. 255 entries in a table of 255 columns or
                       fewer, one per column past that. See below.
cell_storage_buffer    records laid end to end; a record runs to the next live offset
```

### A wide table counts its offsets in words, and the width never changes

`has_wide_offsets` does **not** select a `uint32`. Measured 2026-09-06 against
`45-columns-over-255`, a 300-column table: each row carries 600 bytes of offsets for 300
cells, which is two bytes each and can be nothing else. Reading them as `uint32` gives 150
slots for 300 cells and puts every one of them past the end of a 7,200-byte buffer, which
is what pybers did until #48.

Two things change once a table passes 255 columns, and the offset width is not one of them:

| | 255 columns or fewer | wider |
| --- | --- | --- |
| slots | fixed 255, the surplus marked `0xFFFF` | one per column |
| offset counts | bytes: `0, 24, 48, 72` | four-byte words: `0, 6, 12, 18` |

Scaling by four is lossless because every record is already aligned: all 9,497 offsets in
the 46 fixtures that predate `45-columns-over-255` are multiples of four. Spending the two
bits Numbers already had keeps the offset a `uint16` while a row grows toward the
1000-column limit.

`should_use_wide_rows` is sticky and the array is sized to the table, so a table that once
exceeded 255 columns keeps the wide form after they are deleted. `TSTables` carries
`-[TSTTableTileStorage widenTilesForUpgrade]` and `-[TSTTableTile widenAllRowsForUpgrade]`
and nothing that narrows one back.

Both `TileRowInfo.has_wide_offsets` and `Tile.should_use_wide_rows` are set together in
every document measured. `pybers._persistence.cells.offsetUnitFor` honors either alone,
since which one is authoritative has not been established.

Record layout, as far as it is needed to read a value:

```
byte  0      storage version (5 in every file seen)
byte  1      value TYPE (below)
bytes 4-7    flags bitmask, NOT decoded
bytes 8-11   purpose unknown, NOT decoded
bytes 12+    the value
```

### Byte 1 is NOT simply `TST.CellType`

It coincides with `TST.CellType` for every type in `11-value-types-noformats`, which made
that look settled. `12-number-currency` disproved it: **every currency cell carries type
`10`, and 10 is outside the `CellType` enum entirely**, that enum stops at 9, and
`CellValueType` puts currency at 9, not 10.

So the storage byte is its own numbering that happens to agree with `CellType` over the
common types. Treat the enum as a useful guide and **not** as an exhaustive list, and expect
further values that neither enum names. Anything reading this byte must handle an unknown
value by preserving it rather than rejecting the cell.

The table below is what has been *measured*, with the enum names attached where they match:

| value | name | status |
|---|---|---|
| 0 | `genericCellType` | not seen |
| 1 | `spanCellType` | not seen. This is how the cells *covered by a merge* are marked |
| 2 | `numberCellType` | **decoded**, IEEE-754 decimal128, little-endian, 16 bytes |
| 3 | `textCellType` | **decoded**, uint32 key into the `STRING` `TableDataList` |
| 4 | `formulaCellType` | not seen |
| 5 | `dateCellType` | **decoded**, float64 seconds since 2001-01-01 UTC |
| 6 | `boolCellType` | **decoded**, float64, zero is false |
| 7 | `durationCellType` | **decoded**, float64 seconds |
| 8 | `formulaErrorCellType` | not seen |
| 9 | `automaticCellType` | not seen |
| 10 | *(named by neither enum)* | **decoded, currency.** Value is decimal128 at bytes 12-27, identical to a plain number |

## How many trailing references a record carries, and what byte 8 says about its value

Measured for PYB-61 across every record in the corpus, 11,760 of them spanning all nine
cell types. Writing text over a number moves every trailing reference, because a
decimal128 value is sixteen bytes and a pooled string key is four, so the count and the
placement both have to be right before a type can change.

### The count

```
references = popcount(byte8 & 0xE0) + popcount(byte9) + popcount(byte10)
```

**No exceptions in 11,760 records.** Bytes 9 and 10 are a bitfield of which optional
references a record carries, each set bit contributing exactly one.

This answers the question [findings-09-cell-records.md](findings-09-cell-records.md) left
open, which recorded that bytes 8 and 9 do not fully determine the count and that at least
one more gate lived somewhere else. **Byte 10 is that gate.** Grouping every record by
byte 8 and byte 9 alone leaves 2 of 41 shapes ambiguous; adding byte 10 leaves 0 of 43.

### Byte 8's low nibble names the value

One value per cell type, with no exceptions:

```
0   no inline value          0 empty, 8 formula error, 9 rich text
1   decimal128, 16 bytes     2 number, 10 currency
2   a double, 8 bytes        6 boolean, 7 duration
4   a date double, 8 bytes   5 date
8   a pooled key, 4 bytes    3 string
```

They behave as one bit per width rather than as an enum, which is what makes
`byte8 & 0xE0` the right mask for the references above.

**Bit `0x10` belongs to the value, not to the references.** It is set on every rich-text
record, whose four-byte payload key the low nibble does not describe. Counting it as a
reference misses exactly the five rich-text shapes and over-counts each by one, which is
why the `0xE0` mask `findings-09` uses for the formula key slot is correct here as well.

### Which list each reference-bearing bit points into

Measured for PYB-61 across the corpus. A bit is named by the `format_type` its key
resolves to, since a format entry states its own kind and a small key is otherwise a
plausible entry in several lists at once.

| bit | what its reference is | evidence |
| --- | --- | --- |
| byte 8 `0x20` | a `styleTable` key | 349 of 349 unambiguous |
| byte 8 `0x40` | a `styleTable` key | 395 of 395 unambiguous |
| byte 9 `0x02` | a `formula_table` key | 63 of 63 unambiguous |
| byte 9 `0x20` | the **number** format | 6105 name `256`, the rest `258`, `259`, `269`, `270` |
| byte 9 `0x40` | the **currency** format | 34 of 34 name `257` and nothing else |
| byte 9 `0x80` | the **date** format | 24 of 24 name `261` and nothing else |
| byte 10 `0x01` | the **duration** format | 19 of 19 name `268` and nothing else |
| byte 10 `0x02` | the **text** format | 5427 of 5427 name `260` and nothing else |
| byte 10 `0x04` | the **checkbox** format | the one checkbox in `11-value-types-noformats` names `263`; found by the refcounts below |

**The slots are per format kind, not per cell.** A cell carries the slot its display
needs, which is why a number and a string of the same table put their format reference
in different places and why bytes 9 and 10 differ between them. Byte 9 `0x02` landing on
`formula_table` is the bit
[findings-09-cell-records.md](findings-09-cell-records.md) identified as the formula
flag, reached from the other direction.

The format types themselves: `256` number, `257` currency, `258` percent, `260` text,
`261` date, `263` checkbox, `267` star rating, `268` duration. A text format entry
carries nothing but its `format_type`, so one can be created where a table has none.

**Byte 9 bit `0x10` is the format the cell currently displays with**, as against the
per-kind slots above, which remember one format per kind so that switching a cell back
restores what it had. Named on 2026-09-14 by a golden rather than by the corpus, which
could not separate it: two text cells with identical slots read differently in Numbers,
`Text` where this named the text format and `Automatic` where it still named the number
format the cell had been. A plain number puts the same key in this slot and in byte 9
`0x20`, which is why counting alone never told them apart.

**Superseded 2026-09-15: byte 9 `0x10` holds a kind, not a key.** The paragraph above
reads it as a format key, and it is not one. Its value is the position of a per-kind
slot, counted from 1 in slot order: 1 number, 2 currency, 3 date, 4 duration, 5 text,
6 checkbox. In all 11,581 records the fixtures carry, it names a kind slot the record
holds. `54-format-star-rating` settles it, because its text cell stores 5 there and no
data list in that table holds a key 5. The reading above survived because
`11-value-types-noformats` keys its number format 1 and its text format 5, the same
numbers as the kinds. `Text` and `Automatic` in the inspector were 5 and 1.

**Byte 6 bit `0x80` marks a format a person chose** rather than one Numbers decided.
4515 text records leave it clear against 108 that set it, and the Data Format inspector
reads `Automatic` without it and `Text` with it. Typing text into Numbers leaves it
clear, which is why writing a string leaves it clear here.

Setting it is a deliberate act with one purpose: forcing a number to render as text, or
stopping a formula from evaluating so its own text shows. That is a capability of its
own rather than a side effect of writing a string, and nothing in this library offers it
yet.

**Byte 9 bit `0x04` is the control a cell presents as**, a `control_cell_spec_table` key.
`11-value-types-noformats` settles it: its checkbox, star rating, slider, stepper and
pop-up menu carry keys 1 to 5 in the order that table lists them, and every plain cell
carries no such slot. A control describes the value it was built for, so it does not
survive that value being replaced. Leaving one in place makes Numbers render a sentence
as a star rating.

### What this settles for writing

A record whose type changes keeps its references and therefore keeps the count, so bytes
9 and 10 are never rewritten and the slots keep their meanings. What that leaves is a
text cell naming the format its number had, which Numbers accepts: confirmed in Numbers
15.3.1 on 2026-09-14, where a cell converted from a number displays as text with a Data
Format of Automatic, and one converted from a star-rating control displays as plain text
with no control.

### What a format's refcount counts

Measured 2026-09-15 for PYB-89 across all 89 tables in the fixtures that carry a format
list. **A format entry's `refcount` is the number of times its key appears in the six
per-kind slots**: number, currency, date, duration, text and checkbox. Each occurrence
counts once, so a cell naming one format in two kind slots would count twice. That rule
reproduces every declared refcount in every table.

**Byte 9 `0x10` is not counted**, and cannot be: it holds a kind rather than a key, as
recorded above. Counting it as a key breaks 22 of the 89 tables.

`54-format-star-rating` and `54b-format-star-rating-released` agree with the rule. `54`
counts its star-rating format twice, once for `A1` and once for the text label below
it, which remembers the format in its number slot.

An earlier audit, recorded in PYB-89, concluded that `11-value-types-noformats` and
`12-number-currency` disagree with their cells around dates, checkboxes and currency.
Under this rule neither does. That audit read fewer slots than Numbers counts.

What pybers does with it: a written record moves counts by the difference between the
format slots it held and those it holds now, so an entry no written record names keeps
the count Numbers wrote, even one that disagrees with its cells. A shape borrowed from a
sibling holds no claim before the write, and it keeps only its own kind's format slot.

### What Numbers does with a format nothing names

**Numbers removes it on save.** Measured 2026-09-15 against
`54c-format-star-rating-cleared`, made from `54` by Clear All on `A1:A2`, which were the
only two cells naming the star-rating format. Key 2 is absent from the saved format list,
and `nextListID` stays at 3.

The rest of the fixtures agree. None of their 4,899 data-list entries has a refcount of
0, and nine format lists skip keys below `nextListID`, for example `18-formula-literals`
holding keys 1 and 5 with `nextListID` 9.

Its string list is not as simple. The label typed into `B1` after the clear sits at key
1 with `nextListID` still 2, the key the cleared `A2` label held. Whether Numbers reused
the key or rewrote the entry in place cannot be told from the saved file.

`54b-format-star-rating-released` measures it for two other lists in the same table.
Setting `A1`'s Data Format from Star Rating to Text dropped its control, and the control
entry, whose count reached 0, is gone. Relabeling `A2` did the same to its old string.
Both lists keep their `nextListID`, so neither key is reused.

The format count did not reach 0 in that fixture, because Numbers kept the star rating in
`A1`'s number slot and counted it there. Changing to Text also converted the value to the
string `****` and set byte 6's chosen-format bit. pybers drops the slot a retype leaves,
which is what releases the count, and Numbers accepted that in
`11-text-written-and-retyped`.

pybers keeps an entry whose count reaches 0, as its string and formula pools do.
`11-text-written-and-retyped` carries one: the star-rating format, after `F1` became
text.

**Superseded 2026-09-15 for PYB-89: pybers now removes it**, as Numbers does, and leaves
`nextListID` alone. An entry whose count Numbers wrote too low can reach 0 while cells
still name it, so the table's records are read before an entry goes, and one still named
stays. The string and formula pools still keep theirs, which PYB-92 takes up for strings.

## Currency is a distinct cell type, but not a distinct value encoding

Measured across `12-number-currency`, which carries nine currency variants beside a plain
`1234.5` for comparison. All nine are **type 10**; the plain number is type 2. Yet the value
sits at the same offset in the same decimal128 encoding in both, signs included, the three
negative variants decode to `-1234.5` correctly from decimal128's sign bit.

So currency is a **type marker plus a format reference over an ordinary number**. It needs no
new value type in the model: `Decimal` already covers it. What it needs is somewhere to carry
the currency code and the presentation, because those are not in the value.

Every one of these is type 10 with the same value, differing only in trailing references:
basic currency, thousands separator, accounting style, zero decimal digits, negatives as
`(-100)`, negatives in red, negatives combined with accounting style, and Euros rather than
dollars. **The currency code itself is part of the format, not the value**, `1234.5` in
Euros and `1234.5` in dollars are the same cell value.

## Percent is NOT a distinct type, and the asymmetry with currency is the point

Every cell in `13-number-percent` is **type 2**, an ordinary number, with `flags 0x0003` plus
format references. Currency gets its own type byte; percent does not.

The distinction is meaningful rather than arbitrary. **Currency carries semantic data the
value cannot hold**, the currency code. `1234.5` in Euros is different information from
`1234.5` in dollars, and no amount of formatting recovers which was meant. Percent carries
none: the value is a fraction and the format multiplies by 100 to display it.

The stored value is always the fraction, never the displayed number:

```
displays  0.25     stores  25 x 10^-2  =  0.25
displays  25%      stores  25 x 10^-2  =  0.25
displays  1,000%   stores  1000 x 10^-2 = 10.0
displays  -0.25%   stores  25 x 10^-4, sign set = -0.0025
```

**Anything reading a percent cell must not report the displayed number**, and anything
writing one must not hand over a display value. It is a factor-of-100 error that looks
entirely reasonable in isolation.

### A caution about authoring fixtures, not about the library

In this fixture the positive cells hold `0.25` while the negative ones hold `-0.0025`,
despite the same described action. Numbers decided differently for the two, and the exact
mechanism was not pinned down, order of operations and a sign-dependent parse are both
consistent with what is on disk.

This does **not** affect pybers, which stores and returns the underlying value and does not
emulate how Numbers interprets typing. It affects *fixtures*: when a file is built by typing
into Numbers, what ends up stored may not be what was typed. So a fixture label should record
**what is displayed**, which is checkable against a screenshot, rather than what was entered,
which is not recoverable from the file.

## Dates: the time is in the value, and the tail offset is not fixed

From `14-number-date`. Every cell is **type 5** whatever format is applied, so dates behave
like percent and unlike currency, formatting never changes the type.

**A date-time is a single number, not a date plus a time field.** `11:00` is stored inside
the same float64 as `11:00:00` past midnight; cells with no time hold exactly `00:00:00`.
There is nowhere else for a time to live.

Flags record which format layers exist:

```
0x0000   no format applied
0x0008   a date format
0x000b   a date format and a time format
```

### The trailing references do NOT start at a fixed offset

They begin immediately after the value, and the value's width depends on the type:

```
decimal128 (types 2, 10)   16 bytes   tail starts at 28
float64    (types 5, 6, 7)  8 bytes   tail starts at 20
string key (type 3)         4 bytes   tail starts at 16
```

Reading the tail at a constant 28 silently skipped two fields on every date, boolean and
duration cell while looking perfectly plausible, because the remaining fields still parsed as
integers. Nothing raised. This is the failure mode to expect throughout this format: a wrong
offset yields wrong numbers rather than an error, so every layout claim needs a fixture whose
expected content is known independently.

## Durations, and what finally settles the type-versus-format question

From `15-duration-formats`. Every duration cell is **type 7** regardless of format, automatic
units, weeks only, milliseconds abbreviated, no unit shown. So durations behave like percent
and date.

**Currency is therefore the only type in the entire set that changes its type byte for a
format.** That is consistent with the reason: currency carries a code the value cannot hold,
while every other format is presentation over an unchanged value.

### The format key is the LAST trailing reference

`15` provides the controlled experiment: five cells holding the *identical* duration with five
different formats. Only the final tail element changes.

```
value 71 days 11:00:00.010000, five presentations:
  tail=[4, 3, 9]    tail=[4, 3, 7]    tail=[4, 3, 12]    tail=[4, 3, 6]
```

Value fixed, format varying, one slot moving.

**`tail[0]` is the formula key when a formula is present**, confirmed four times in one file.
`15` holds four formulas, and the two `DURATION()` calls differ only in which argument slot
receives the value:

```
key 3  [22,22, 36, 23,23,22, 16]   two placeholders before the coordinate  -> 3rd argument
key 4  [22,22,22, 36, 23,23, 16]   three placeholders before it            -> 4th argument
```

The cells using them carry `tail[0] = 3` and `tail[0] = 4`, and their values confirm the
reading independently: the third argument is hours (370,440,000 s) and the fourth is minutes
(6,174,000 s). Nodes `22` and `23` are placeholders for omitted arguments; the distinction
between the two is not established.

**The middle slots remain unidentified.** A plain unformatted number carries `tail=[1, 1]`
with no formula anywhere, so slot meaning depends on the flags bitmask, and mapping bit to
slot is still open work.

### Arithmetic on a duration is lossy, and Numbers only warns

`15` captures the accident and the deliberate version side by side. `I1+10` demotes the cell
to **type 2** and discards the duration format, with nothing but a corner indicator saying so.
`DUR2MINUTES(I1)` does the same conversion on purpose, and `DURATION()` converts back.

For pybers this is a case to be careful about rather than to replicate: a caller adding a
number to a duration through this library should not silently lose the type the way the
application does.

**That warning indicator is not stored in the file.** Measured: no archive type appears in
`15` that is absent from `16`, the `IMPORT_WARNING` and `COMMENT_STORAGE` data lists are both
empty, and the flagged cell carries no flag bit its unflagged neighbor lacks, the neighbor
has an extra bit, not one fewer. Numbers recomputes the indicator when it recalculates,
knowing the operand was a duration and the result is not.

So a round trip cannot drop it, which is one less thing to preserve. It also means pybers
cannot surface it without performing the same inference, and that requires evaluating
formulas, which is Numbers' job, not this library's.

### Three duration behaviors worth knowing

**A leading apostrophe is an input directive and is not stored.** `'10 minutes` becomes an
ordinary text cell holding `10 minutes`, the quote is consumed by input handling and leaves
no trace, so it cannot be recovered or round-tripped.

### Durations are float64 SECONDS, and that is a trap

The stored value is a plain float64 counting **seconds**, verified against three cells whose
contents are known: `10 minutes` is `600.0`, `1h 10m` is `4200.0`, and the long one is
`6174000.01`.

**This is a different numeric system from cell values, and only one of the two is safe.**
Numbers are decimal128 and exact. Durations and dates are binary float64 and are not. A
currency amount survives arithmetic unharmed; a duration does not.

`15` demonstrates the loss in its own cells. The same duration, typed directly and then
round-tripped out to a number and back with `DUR2MINUTES()` / `DURATION()`:

```
typed directly                     6174000.01
DURATION(,,,K1,,)   via minutes    6174000.01000002       drifted
DURATION(,,K1,,,)   via hours      370440000.6000012      drifted
```

Divide by 60 and multiply by 60 and the value does not come back. The `DUR2___` and
`DURATION()` functions exist precisely to leave duration space for arithmetic and return,
and every trip through them compounds binary rounding.

**It is UNIT CONVERSION that loses precision, not duration arithmetic.** The same fixture
subtracts two dates and the result is exact:

```
O1 - N1   ->   55320.0     exactly 15h 22m, no drift
N1 - O1   ->  -55320.0     exact, and negative
```

Adding and subtracting are safe because no scaling happens. Dividing to reach another unit
and multiplying back is where the error enters. That is the rule worth carrying: **avoid
round-tripping a duration through a different unit**, not "avoid duration arithmetic".

### Date minus date yields a duration, automatically

Two type 5 cells subtract to a type **7** cell. Numbers infers the result type, the exact
opposite of what it does when a duration is added to a plain number, where the duration
format is silently discarded. Subtraction promotes; addition with a bare number demotes.

**Durations may be negative**, stored as an ordinary negative float64 with nothing
special-cased.

**A caution for whatever pybers returns to callers:** Python renders
`timedelta(seconds=-55320)` as `-1 day, 8:38:00`. That is arithmetically identical to minus
fifteen hours twenty-two minutes, and it reads like a defect. Any user-facing representation
of a negative duration needs formatting of its own rather than relying on `timedelta.__str__`.

**The hazard this creates for pybers is our own.** Python's `timedelta` is microsecond
resolution, so reading `6174000.01000002` into one and writing it back produces
`6174000.01`, silently "correcting" the drift and changing a file nobody asked us to change.
The discipline is the same as for IWA members: **keep the original bytes and re-encode only
what was actually modified.** Tidying a value we were not asked to touch is a defect, not an
improvement.

**Duration arithmetic coerces to hours.** `I1+10` over `71 days 11:00:00.01` yields
`1725.0000027777799`, and 71 days plus 11 hours is 1715 hours, so `+10` added ten *hours*.
The cell also demotes to **type 2** with Numbers reporting that the duration format was
removed. Storage remains **seconds** in the float64, only the calculation engine works in
hours, so a reader must not infer the unit from arithmetic behavior.

**`DURATION()` promotes a number back to type 7**, and the fixture pins its argument order by
feeding the same value into two different slots:

```
DURATION(,,,K1,,)   ->  6,174,000.01 s      K1 read as MINUTES
DURATION(,,K1,,,)   ->  370,440,000.6 s     K1 read as HOURS
```

So the signature is `DURATION(weeks, days, hours, minutes, seconds, milliseconds)`, derived
from two measurements rather than from documentation. It also corroborates the hours finding
above independently.

## Numbers has numeral systems, and they are display only

From `16-number-scientific`. Beyond scientific notation, Numbers formats a number in **base 2,
10 or 16** with a configurable number of places, and offers **two's complement** for negative
values in the non-decimal bases.

Every one of those cells is **type 2** holding an unchanged `1234.5` or `-1234.5`. The base,
the places, and the two's-complement choice are entirely presentational. A reader that reported
the displayed hex string as the value would be wrong in the same way as reporting a displayed
percentage.

## One custom format holds its positive, negative and zero forms together

From `17-number-custom`. Three cells holding `1234.5`, `-1234.5` and `0` share the **same
format key**:

```
value  1234.5   tail=[1, 4, 2]
value -1234.5   tail=[1, 4, 2]
value  0        tail=[1, 4, 2]
```

So a custom format with distinct presentations for positive, negative and zero is a **single**
format archive containing all three, not three formats selected by sign. Anything modeling
number formats needs that shape: one object, several conditional presentations.

### Format is carried by reference, gated by a bitmask

Bytes 6-7 are a flags bitmask that decides which trailing `uint32` references are present:

```
type  2, flags 0x0000 -> tail [1, 1]
type 10, flags 0x0802 -> tail [2, K]        the common currency case
type 10, flags 0x0803 -> tail [2, 1, K]     bit 0 adds one field
type 10, flags 0x0882 -> tail [2, 11, 5]    bit 7 adds a different one
```

The last element varies with the format variant, so it reads as a key into the `FORMAT`
`TableDataList`. **The individual flag bits are not decoded**, which bit implies which
field is unknown, and guessing would be worse than saying so. A writer must not synthesize
this bitmask until each bit is understood; round-tripping the original bytes is safe, and
inventing them is not.

### There are TWO cell type enums and they do not agree

`TST.CellType` is the one in the storage byte. `TST.CellValueType` is a **different** enum
used elsewhere, and its numbering is offset:

```
CellValueType  0 empty  1 number  2 string  3 provided  4 date
               5 bool   6 duration  7 error  8 richText  9 currency
```

`date` is **5** in `CellType` and **4** in `CellValueType`. Confusing the two shifts every
type by one and would misread whole columns silently. Always name which enum is meant.

`CellValueType` also carries two entries `CellType` does not: `richTextCellType`, consistent
with the separate rich-text payload, and **`currencyCellValueType`**, so **currency appears
to be a value type in its own right rather than a display format over a number.** That is
worth confirming with a fixture rather than assuming either way, and it makes
`12-number-currency` a real unknown rather than a variation on `11`.

Verified end to end: the fixture decodes to `1234.5`, `42`, `2027-06-15`, `0:20:00`, `True`,
`3`, `50`, `1`, `'Item 1'`, matching all nine of its own labels, with the tenth cell empty
and carrying no record.

### Numbers are decimal128, and this matters more than anything else here

Not float64. `1234.5` is stored exactly, as mantissa `12345` with exponent `-1`. A spreadsheet
library that round-trips values through Python's `float` **will corrupt them**: reading `0.1`
and writing it back would introduce binary-representation error into a document that never had
any. `decimal.Decimal` is the correct type for `Cell.value`, and this decides that part of the
model rather than leaving it to taste.

### Interactive controls are ordinary values plus a presentation reference

A checkbox, star rating, slider, stepper and popup menu all store a **normal value**, bool,
number, or string, and reference a `CONTROL_CELL_SPEC` separately. The control is how the
value is edited, not what it is. So they need no new value type, only a reference to carry.

### Two storage strategies by type

Strings are **pooled and deduplicated** into a `TableDataList` and referenced by key; numbers,
dates, booleans and durations are stored **inline** in the record. There is no `NUMBER` list
type. Any writer has to maintain the string pool, not just the cell.

### Do not trust `numCells`, `maxColumn` or `maxRow`

All three read **0** in a tile holding 19 real cells across two rows. They are not maintained.
The row count comes from `rowInfos`, and the populated columns come from the offsets array.
This cost a debugging cycle: a filter skipping tiles where `numCells == 0` skipped everything.

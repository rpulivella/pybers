# Format archives, family by family

What each format family stores in its `TSK.FormatStructArchive`, which bits the format
sets in the cell record, and which fields pybers writes or carries through. Measured
2026-10-20 and 2026-10-21 for PYB-219, and every count below is across all 74,304 records
in 161 documents.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic. How a cell names its format,
through the per-kind slots and the displayed kind, is in
[findings-01-values.md](findings-01-values.md).

---

## The bits a format sets in the cell record

### Byte 6: which remembered formats were set explicitly

Each per-kind format slot has one bit in byte 6. A slot whose bit is set holds a format
someone set explicitly. A slot whose bit is clear holds the Automatic format Numbers
inferred from what was typed. **All 74,304 records agree: no bit is ever set without
its slot.** Bits `0x10` and `0x40` are never set.

| bit | kind slot | records | named by |
| --- | --- | --- | --- |
| `0x01` | number | 809 | `13-number-percent` `B1` to `G1`, beside `A1` "plain number" clear |
| `0x02` | currency | 319 | every currency cell of `12-number-currency` |
| `0x04` | duration | 30 | `15-number-duration-formats` `E1` to `I1`, "format set to duration", beside `D1`, "numbers picked duration with automatic units", clear |
| `0x08` | date | 486 | `14-number-date` `C1` to `G1`, a chosen pattern, beside `A1`, "plain date", clear |
| `0x20` | checkbox | 14 | `11-value-types-noformats` `E1`, beside the typed TRUE of `73-values-typed-over-controls` `J1`, clear |
| `0x80` | text | 183 | the chosen Text format the Data Format inspector reads, see [values](findings-01-values.md) |

The bits are per slot, so a cell remembers which of its kinds were chosen as well as
which formats they were. `14-number-date` `B1` stores `0x0b`: its date pattern was
chosen, and so were the number and currency formats it was given on the way there.

One record holds an explicit bit over an archive identical to Automatic:
`15-number-duration-formats` `K1`, `DUR2MINUTES(I1)`, sets `0x01` over format `256` with
253 decimal places, where `J1`, `I1+10`, leaves it clear over the same entry.

### Byte 7 `0x08`: a currency format chosen for a currency amount

Set on all 296 records that are type 10 and carry byte 6 `0x02`, and on no other record.
The 25 records holding a chosen currency format without being type 10, a percent that
remembers a currency, leave it clear, and so do the two type 10 records whose currency
came from a formula rather than a choice, `88-formula-currency-results` `C1` and `D1`.
Every type 10 record displays with the currency kind. A currency amount a person
formatted is therefore four things written together: type 10, byte 6 `0x02`, byte 7
`0x08`, and the currency kind in the displayed slot.

Byte 7 `0x80` is set on one record, `88-formula-currency-results` `D1`, `=SUM(A1,A1)`,
and on no other, so what it records is not established.

### Byte 4 `0x02`: a custom format

Set on all 86 records that display with a custom format of any type, 270 to 274, in
seven documents, and on none of the other 74,218 records.
`17-number-custom` `A1`, a plain number beside six custom cells, leaves it clear.

### Byte 5 `0x02`: a format Numbers removed

Set on one record, `15-number-duration-formats` `J1`, `I1+10`, which Numbers marks with
a corner indicator reading that the duration format was removed. `K1` converts the same
duration on purpose with `DUR2MINUTES` and leaves it clear. One record names the bit and
does not settle it.

### Byte 4 `0x01` is not a format bit

Set on 50 text, 12 rich-text and 5 empty records, none of them through a format. They
are the multi-line cells and the wrap labels of `30-style-align`, `32-named-styles` and
`36-unicode-text`. What it records is not established.

---

## The families

A field absent from a family's table is never set in any document. pybers writes a
family's format only as Numbers stores it, so an absent field stays absent.

### Number, `256`

| field | measured | named by |
| --- | --- | --- |
| `decimal_places` | 253 for Automatic, 0, 1, 2, 4 and 6 | `11-value-types-noformats` `A1`, `74-number-negatives` `A1` |
| `negative_style` | 0 to 3 | `74-number-negatives` `A1` to `D1` |
| `show_thousands_separator` | both | `74-number-negatives` `E1` |

**`negative_style` is shared by number, currency and percent**, measured in
`74-number-negatives` and in the preview Numbers saved with it:

| value | menu item | renders -1234.5 as |
| --- | --- | --- |
| 0 | `-100` | -1234.50 in black |
| 1 | `100` | 1234.50 in red |
| 2 | `(100)` | (1234.50) in black |
| 3 | `(100)`, the second item | (1234.50) in red |

The menu titles 2 and 3 alike, so the color is the only difference between them.

### Currency, `257`

| field | measured | named by |
| --- | --- | --- |
| `decimal_places` | 253 for Auto, 0, 2 and 5 | `12-number-currency` `E1`, "0 digits after decimal", `82-currencies` `F1` |
| `currency_code` | `USD`, `EUR`, `JPY`, `KRW`, `GBP`, `CHF` and `INR` | `12-number-currency` `H1`, "in Euros", `82-currencies` `A1` to `E1` |
| `negative_style` | 0 to 3 | `12-number-currency` `G1` and `F1`, `74-number-negatives` `F1` |
| `show_thousands_separator` | both | `12-number-currency` `C1` |
| `use_accounting_style` | both | `12-number-currency` `D1` |

**A formula's currency result is stored as a currency amount only when currency
survives the arithmetic.** Measured in `88-formula-currency-results`, over a euro amount
in `A1` and a dollar amount in `B1`:

| formula | stored as | shows |
| --- | --- | --- |
| `=A1*2`, `=SUM(A1,A1)` | type 10, naming `A1`'s euro format | €2469.00 |
| `=A1+10`, `=A1/B1` | type 2, the Automatic number format | 1244.5, 12.345 |
| `=A1+B1` | type 8, a formula error | nothing |
| `=DOLLAR(1234.5)` | type 3, text | $1,234.50 |

A result that stays currency names the same format entry as the amount it came from,
so its code is that amount's code, and byte 6 is clear, since nobody chose it. Adding
euros to dollars is refused by Numbers as an error. `CURRENCYCONVERT` stored a formula
error in this run and in a second given a minute to resolve, so a converted result is
not measured.

**A currency's symbol comes from the document's locale.** The snapshot holds 23 symbols
by code in `formatting_symbols.currency_symbols`, and they differ by region: the yen is
`¥` under `en_US` in `82-currencies` and `JP¥` under `en_IT` in
`72b-date-time-zones-region`. A currency with no entry, such as the Swedish krona, has
no symbol there.

**Choosing a currency does not choose its decimals.** `82-currencies` gives the yen and
the won 2 decimal places, as it gives every currency measured, where neither is
customarily written with any. The menu offers 37 currencies, each stored as
its ISO 4217 code.

Two labels disagree with their archives. `12-number-currency` `G1` reads "with thousands
separator" over a format without one, and `I1` reads "(-100) combined with accounting
style" over 5 decimal places and style 0. The negative styles are settled by
`74-number-negatives`, not by those labels.

### Percent, `258`

The fields of a number, with the same meanings. Measured: `decimal_places` 0, 2 and 253,
`negative_style` 0 to 3, and the separator both ways, named by `13-number-percent` `B1`
to `G1` and `74-number-negatives` `G1` and `H1`.

### Scientific, `259`

Only `decimal_places` varies: 2, 0 and 253, named by `16-number-scientific-numeralsystems`
`C1`, `D1` and `B1`. `negative_style` is 0 and the separator false in all five entries.

### Fraction, `262`

One field, `fraction_accuracy`, a `uint32` holding a signed value. Measured in
`75-fraction-accuracy`, whose columns take each choice in the order the menu lists them:

| stored | read as signed | menu item |
| --- | --- | --- |
| `4294967295` | -1 | Up to 1 digit (7/8) |
| `4294967294` | -2 | Up to 2 digits (23/24) |
| `4294967293` | -3 | Up to 3 digits (445/553) |
| 2, 4, 8, 16 | the denominator | Halves, Quarters, Eighths, Sixteenths |
| 10, 100 | the denominator | Tenths, Hundredths |

A negative value is a number of digits, and a positive one is the denominator itself.
A custom number form with no fraction stores -3.

### Numeral system, `269`

| field | measured | named by |
| --- | --- | --- |
| `base` | 2, 3, 8, 10, 16 and 36 | `16-number-scientific-numeralsystems` `I1`, `E1` and `G1`, `80-numeral-systems` `A1` to `C1` |
| `base_places` | 0, 4, 7, 8, 9 and 16 | the same cells, "0 places" to "16 places" |
| `base_use_minus_sign` | both | false for two's complement, `H1` and `J1`, `80-numeral-systems` `D1` and `F1` |

The base is a field, so `80-numeral-systems` sets it rather than choosing it, and 36 is
taken. Whether a larger base is refused is not measured. The value stays the stored number:
`G1` holds 1234.75 under base 16.

### Custom formats, `270` to `274`

Numbers' Create Custom Format dialog offers three types, Number, Date & Time and Text, and
the table entry's `format_type` names which, with currency as a fourth:

| table entry | `format_type_pre_bnc` | custom type | named by |
| --- | --- | --- | --- |
| 270 | 270 | Number | `17-number-custom`, `76-custom-number-scales`, `78-custom-number-digits`, `87-custom-number-rules` |
| 271 | 271 | Text | `86-custom-text-and-currency` `A1` to `C1` |
| 272 | 272 | Date & Time | `84-custom-date-tokens`, `85-custom-time-tokens` |
| 274 | 270 | Number holding a Currency token | `86-custom-text-and-currency` `D1` to `F1` |

273 is not seen. No custom type exists for a duration.

**The table entry holds only `custom_uid`.** The format itself is a
`TSK.CustomFormatArchive` in `TSA.DocumentArchive.custom_format_list`, the `super` of
the root `TN.DocumentArchive`, whose own `custom_format_list` is unset. The list is type
222, a `TSK.CustomFormatListArchive` whose `uuids` and `custom_formats` run in parallel.
Measured in `17-number-custom`, whose four formats are named by `B2` to `E2`, and in
the custom measurements from `76` to `87`, whose labels name each format.

| field | what it holds |
| --- | --- |
| `name` | the name typed when the format was created |
| `format_type_pre_bnc` | the custom type: 270, 271 or 272 |
| `default_format` | the form that shows when no rule matches, a `FormatStructArchive` of that type |
| `conditions` | one per rule, each a `condition_type`, a `condition_value_dbl` and a `condition_format` |

**Positive, negative and zero are one archive.** `E1`, `F1` and `G1` hold 1234.5,
-1234.5 and 0 and name the same format, whose default form is `'+'#,###.0 K'g'`. Its
first condition, type 1 at 0, is `'–'#,###.0 K'g'`, the negative form. Its second, type
0 at 0, is `'Thin Air'`, the zero form.

**A rule is a condition, a threshold and a form of its own.** Measured in
`87-custom-number-rules`, one column per condition the rule menu offers, each at 100:

| `condition_type` | menu item | named by |
| --- | --- | --- |
| 0 | If equal to | `E1` |
| 1 | If less than | `A1` |
| 2 | If less than or equal to | `B1` |
| 3 | If greater than | `C1` |
| 4 | If greater than or equal to | `D1` |

The threshold is `condition_value_dbl`, a double, so `F1` holds 2.25, and the float
`condition_value` is never set. **Rules are tried in order and the first that matches
wins**: `G1` holds 1500 under a rule above 100 and a later one above 1000, and shows
`1,500 big`, the first rule's form. The default form shows when no rule matches.

**The scale is `scale_factor`, and its symbol is a letter in the string.** Measured in
`76-custom-number-scales`, one column per choice the Scale token offers, each showing
1234567.891 as its preview Numbers saved reads:

| Scale choice | `custom_format_string` | `scale_factor` | shows |
| --- | --- | --- | --- |
| Percent | `#,###` | 100 | 123,456,789 |
| Percent (%) | `#,###%` | 1 | 123,456,789% |
| Hundreds, Hundreds (C) | `#,###`, `#,###C` | 0.01 | 12,346, 12,346C |
| Thousands, Thousands (K) | `#,###`, `#,###K` | 0.001 | 1,235, 1,235K |
| Millions, Millions (M) | `#,###`, `#,###M` | 1e-06 | 1, 1M |
| Billions, Billions (B) | `#,###`, `#,###B` | 1e-09 | 0, 0B |
| Trillions, Trillions (T) | `#,###`, `#,###T` | 1e-12 | 0, 0T |
| Scientific | `0E+00` | 1 | 1E+06 |

**Percent with its symbol is the exception**: it stores a factor of 1 and leaves the
multiplying to the `%` in the string, where every other symbol leaves the factor in place.
`17-number-custom` agrees: `B1` writes `#,###.0 K'g'` and `C1`, "kilograms no K", writes
`#,###.0 'g'`, both over 0.001.

**A suffix or prefix is a quoted literal** in `custom_format_string`: `' units'` and
`'about '` in `76-custom-number-scales` `N1` and `O1`, and `'g'`, `'+'` and `'Thin Air'`
in `17-number-custom`. A space typed as the separator is stored as itself, and the
flexible space of `17-number-custom` `D1` as a tab.

**`index_from_right_last_integer` counts the characters after the last integer token,
quotes excluded**: 6 for `#,###' units'`, 1 for `#,###K`, 0 for `'about '#,###`, 4 for
`0E+00`, and 5 and 4 for the two kilogram strings of `17-number-custom`.

**The Integer and Decimal tokens' options are digit counts beside the string.** Measured
in `78-custom-number-digits`, one column per option, each holding 1234.5:

| token option | `custom_format_string` | fields that change | shows |
| --- | --- | --- | --- |
| Integer, Hide Separator | `#,###` | `show_thousands_separator` false | 1235 |
| Integer, 6 digits, zeros | `000,000` | `min_integer_width` 6, `num_nonspace_integer_digits` 6 | 001,235 |
| Integer, 6 digits, spaces | `000,000` | `min_integer_width` 6 | 1,235 padded with spaces |
| Decimal, 3 digits | `#,###.###` | none | 1,234.5 |
| Decimal, 3 digits, zeros | `#,###.000` | `num_nonspace_decimal_digits` 3 | 1,234.500 |
| Decimal, 3 digits, spaces | `#,###.000` | `decimal_width` 3, `total_num_decimal_digits` 3 | 1,234.5 padded with spaces |
| Decimal, Fractions | `#,###` and U+E420 | `requires_fraction_replacement` true, `fraction_accuracy` 2 | 1,2341/2 |

**Zeros and spaces store the same string**, so the counts tell them apart: a digit shown
as a space is counted in the width and not among the non-space digits. A hidden separator
keeps its comma in the string. Each option that pads, and the fraction, sets `is_complex`.

**A fraction is the private-use character U+E420 in the string**, which Numbers replaces
when it renders. Its accuracy is `fraction_accuracy`, encoded as the Fraction format
encodes it: columns `H1` to `O1` hold -1 to -3 and the denominators 4 to 100, Halves being
the default. The Space token is a plain U+0020.

Across all 36 number forms in `17`, `76` and `78`, `num_hash_decimal_digits` is 0, even
for `.###`, and `contains_integer_token` is false only for the zero form `'Thin Air'`,
which holds no digits.

**A Currency token is `¤` in the string, and its currency is `currency_code`.**
`86-custom-text-and-currency` `D1` stores `¤#,###.##` with `EUR` and shows €1,234.5, and
`E1` stores `#,### ¤` with `JPY` and shows 1,235 ¥, so the symbol sits where the token
was dropped. Its menu lists the same 37 currencies as the Currency format.

**A custom Text format is the cell's text, U+E421, with literals around it.**
`86-custom-text-and-currency` `A1` to `C1` store U+E421 alone, U+E421 followed by
` (note)`, and `Note: ` followed by U+E421, unquoted, and show `hello`, `hello (note)` and `Note: hello`. The Text
type's field starts with that one token and its palette is empty, so a format that loses
it cannot regain it.

**A custom Date & Time format is a Unicode date pattern** in `custom_format_string`, not
in `date_time_format`, with literal text quoted. `84-custom-date-tokens` and
`85-custom-time-tokens` give one column per style of each token:

| token | styles and the pattern each stores |
| --- | --- |
| Day of Week | Sun `EEE`, Sunday `EEEE` |
| Month | 1 `M`, 01 `MM`, Jan `MMM`, January `MMMM` |
| Day of Month | 5 `d`, 05 `dd` |
| Year | 14 `yy`, 2014 `yyyy` |
| Era | `G` |
| Day of Year | 5 `D`, 05 `DD`, 005 `DDD` |
| Week of Year | 2 `w`, 02 `ww` |
| Week of Month | `W` |
| Day of Week in Month | `F` |
| Hour | 1-12 `h`, 01-12 `hh`, 0-23 `H`, 00-23 `HH`, 0-11 `K`, 00-11 `KK`, 1-24 `k`, 01-24 `kk` |
| Minute | 8 `m`, 08 `mm` |
| Second | 9 `s`, 09 `ss` |
| AM/PM | `a` |
| Milliseconds | 0 `S` to 00000 `SSSSS` |

`85-custom-time-tokens` `S1` joins tokens with text, `yyyy-MM-dd' at 'HH:mm G`. The menu
writes each single-digit Hour style with U+2007, a figure space, before it.

### Date and time, `261`

One field, `date_time_format`, a Unicode date pattern. The inspector builds it from a
Date menu and a Time menu, each offering None, and stores the two joined by a space.
Measured in `79-date-time-formats`, one column per item of each menu with the other set
to None:

| Date item | pattern | | Time item | pattern |
| --- | --- | --- | --- | --- |
| Monday, January 5, 2026 | `EEEE, MMMM d, yyyy` | | 7 PM | `h a` |
| Mon, Jan 5, 2026 | `EEE, MMM d, yyyy` | | 7:08 PM | `h:mm a` |
| January 5, 2026 | `MMMM d, yyyy` | | 7:08:09 PM | `h:mm:ss a` |
| Jan 5, 2026 | `MMM d, yyyy` | | 19:08 | `H:mm` |
| January 5 | `MMMM d` | | 19:08:09 | `H:mm:ss` |
| January 2026 | `MMMM yyyy` | | | |
| January | `MMMM` | | | |
| 2026 | `yyyy` | | | |
| 1/5 | `M/d` | | | |
| 1/5/2026 | `M/d/yyyy` | | | |
| 01/05/2026 | `MM/dd/yyyy` | | | |
| 1/5/26 | `M/d/yy` | | | |
| 01/05/26 | `MM/dd/yy` | | | |
| 2026-01-05 | `yyyy-MM-dd` | | | |
| 2026-1-5 | `yyyy-M-d` | | | |

`U1` and `V1` join a date and a time: `EEE, MMM d, yyyy h:mm:ss a` and
`yyyy-MM-dd H:mm:ss`. **A time with minutes and an AM or PM marker is separated from the
marker by U+202F**, a narrow no-break space, as in `h:mm a`. `h a` keeps a plain space,
and the menu titles follow the same rule. A date shown without a time stores a pattern
without one, so `suppress_date_format` and `suppress_time_format` are never set. Each
pattern names its fields explicitly, so the document's region does not change it, as
the locale section below records.

### Duration, `268`

| field | measured | named by |
| --- | --- | --- |
| `duration_style` | 0 no unit, 1 abbreviated, 2 full word | `15-number-duration-formats` `I1`, `E1` and `F1` |
| `duration_unit_largest` | a unit bit | |
| `duration_unit_smallest` | a unit bit | |
| `use_automatic_duration_units` | both | `B1` true, `E1` false |

The unit bits run 1 weeks, 2 days, 4 hours, 8 minutes, 16 seconds and 32 milliseconds.
Weeks, hours, minutes and milliseconds are named by `15-number-duration-formats` `E1`
"only weeks", `I1` "hours minutes" and `G1` "only milliseconds", and days and seconds by
`77-duration-units` `A1` and `B1`. With automatic units the pair records the range Numbers last chose.

### Text `260`, checkbox `263`, star rating `267`, and boolean `1`

Each archive holds `format_type` and nothing else. A checkbox and a star rating are also
controls, so their formats are written with a control. A typed TRUE stores the boolean
format `1` without a control, as [values](findings-01-values.md) records.

### Controls are a format plus a cell spec

**A control never changes how its value is formatted.** Measured in `81-control-formats`:
a slider or a stepper displays through an ordinary format in its kind's slot, chosen
from its own Format menu of Number, Currency, Percentage, Fraction, Scientific and
Numeral System. A currency slider, `C1`, is a type 10 record with byte 7 `0x08`, as any
currency cell is. The `control_*`, `slider_*` and `multiple_choice_list_*` fields of the
format archive are never set.

The control is a `TST.CellSpecArchive` in the table's `control_cell_spec_table`, which
byte 9 `0x04` names:

| field | holds | named by |
| --- | --- | --- |
| `interaction_type` | 4 stepper, 5 slider, 6 star rating, 7 pop-up menu, 8 checkbox | `81-control-formats` `B1`, `A1`, `J1`, `I1` and `K1` |
| `range_control_min`, `_max`, `_inc` | the range and step, doubles | `A1` 0 to 200 by 5, `B1` -10 to 10 by 0.5 |
| `chooser_control_popup_model` | the pop-up menu's items, a `TST.PopUpMenuModel` | `I1` |
| `chooser_control_start_w_first` | false for Start with Blank | `I1`, true in `11-value-types-noformats` `I1` |

A star rating stores a range of 0 to 5 by 1, and a checkbox no range. Two cells with the
same control share one entry: `C1` and `F1`, both sliders from 0 to 100 by 1.

---

## The document's locale decides how a format renders

**Every format above is stored without reference to a locale**: an explicit date
pattern, an ISO currency code, a count of decimals. The document carries its own locale
in `TSA.DocumentArchive`, with `locale_identifier` and a `formatting_symbols` snapshot of
month names, separators, currency patterns and the calendar. Measured against
`72-date-time-zones` and `72b-date-time-zones-region`, the second set to English (Italy):

| | `72` | `72b` |
| --- | --- | --- |
| `locale_identifier` | `en_US` | `en_IT` |
| decimal and grouping separators | `.` and `,` | `,` and `.` |
| `currency_pattern` | `¤#,##0.00` | `#,##0.00 ¤` |
| default `currency_code` | `USD` | `EUR` |
| the cell's `date_time_format` | `yyyy-M-d H:mm` | unchanged |

Text that shows a value the way Numbers does therefore follows the document's stored
locale, never the machine's. The snapshot's `calendar` is `gregorian` in every document,
and a document made under another calendar is not measured.

---

## What pybers writes and what it carries through

| family | pybers writes | pybers carries through |
| --- | --- | --- |
| number | `decimal_places`, `negative_style`, `show_thousands_separator` | |
| currency | `decimal_places`, `currency_code`, `negative_style`, `show_thousands_separator`, `use_accounting_style`, with type 10 and bytes 6 `0x02` and 7 `0x08` | byte 7 `0x80` |
| percent | `decimal_places`, `negative_style`, `show_thousands_separator` | |
| scientific | `decimal_places`, with `negative_style` 0 and no separator | |
| fraction | `fraction_accuracy` | |
| numeral system | `base`, `base_places`, `base_use_minus_sign` | |
| custom, 270 to 274 | a reference to a custom format the document holds, with byte 4 `0x02`, and a new one only from the tokens measured here, its derived fields computed as the tables above record, confirmed by a golden | `num_hash_decimal_digits`, and every field of a form built from a token not measured |
| controls | the format in its kind's slot, and the cell spec's type, range and step | a pop-up menu's `TST.PopUpMenuModel` |
| date and time | `date_time_format` | `suppress_date_format`, `suppress_time_format` |
| duration | every field | |
| text, checkbox, star rating, boolean | `format_type` | the control a checkbox or a star rating names |

Every family writes its kind's bit in byte 6, since a format pybers sets is chosen.
pybers does not write byte 5 `0x02`, which only Numbers' recalculation sets, and carries
byte 4 `0x01` through.

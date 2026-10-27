# Findings: a document's language and region

What Numbers changes in a document when only File > Advanced > Language & Region
changes, measured for PYB-272 on 27 October 2026 in Numbers Creator Studio 15.4, which
saves `fileFormatVersion` `26.4.0`. Back to the [index](FINDINGS.md).

The origin is `95-region-base`, made under `en_US` by its recipe, and each measurement
is a copy of it with one change made in that dialog, at least one region per inhabited
continent:

| Measurement | Language | Region | `locale_identifier` |
| --- | --- | --- | --- |
| `95-region-base` | System – English | United States | `en_US` |
| `95b-region-de-de` | German | Germany | `de_DE` |
| `95c-region-en-gb` | System – English | United Kingdom | `en_GB` |
| `95d-region-language-english` | English | United States | `en_US` |
| `95e-region-ja-jp` | Japanese | Japan | `ja_JP` |
| `95f-region-en-za` | System – English | South Africa | `en_ZA` |
| `95g-region-pt-br` | Portuguese | Brazil | `pt_BR` |
| `95h-region-en-au` | System – English | Australia | `en_AU` |
| `95i-region-en-in` | System – English | India | `en_IN` |

Row 1 holds a number, two currencies, a date, a percentage and six formulas, and row 2
says what each was input as. The formula text and the values below are what Numbers
displays, read through AppleScript, since the file stores neither as text.

---

## The document archive holds the whole change

Every change Numbers makes to the document's own settings is in `TSK.DocumentArchive`,
reached as `TN.DocumentArchive.super.super`, and in `document_language` on
`TSA.DocumentArchive` between them:

- **`locale_identifier`** becomes the language and region chosen, `de_DE`, `en_ZA`.
- **`document_language`** becomes the language's code, `de`, `ja`, `pt`, and stays `en`
  for either English choice.
- **`creation_locale_identifier`** stays `en_US` in every measurement, recording where
  the document was made rather than what it uses.
- **`has_user_defined_locale`** becomes `true` for any choice but **System – English**.
  It is the one setting `95d` changes, so it is the whole difference between following
  the Mac's language and naming English explicitly.
- **`formatting_symbols`**, the snapshot findings-11-formats.md describes, is rewritten
  from macOS's locale data for the new locale.

| Locale | Decimal, grouping | `currency_pattern` | `currency_code` | `short_date_pattern` | `short_time_pattern` |
| --- | --- | --- | --- | --- | --- |
| `en_US` | `.` `,` | `¤#,##0.00` | `USD` | `M/d/yy` | `h:mm a` |
| `de_DE` | `,` `.` | `#,##0.00 ¤` | `EUR` | `dd.MM.yy` | `HH:mm` |
| `en_GB` | `.` `,` | `¤#,##0.00` | `GBP` | `dd/MM/y` | `HH:mm` |
| `ja_JP` | `.` `,` | `¤#,##0` | `JPY` | `y/MM/dd` | `H:mm` |
| `en_ZA` | `,` and a no-break space | `¤#,##0.00` | `ZAR` | `y/MM/dd` | `HH:mm` |
| `pt_BR` | `,` `.` | `¤ #,##0.00` | `BRL` | `dd/MM/y` | `HH:mm` |
| `en_AU` | `.` `,` | `¤#,##0.00` | `AUD` | `d/M/y` | `h:mm a` |
| `en_IN` | `.` `,` | `¤#,##,##0.00` | `INR` | `dd/MM/yy` | `h:mm a` |

The space inside a pattern is a no-break space, and the one before `a` a narrow
no-break space. `en_IN` groups in lakhs, its `percent_pattern` `#,##,##0%` too, which a
value of `1234.5` is too small to show. Month, weekday, quarter and era names, and the
`am_symbol`, follow the language: `午前` under `ja_JP`, `am` under `en_GB` and `en_AU`.

**A currency's symbol depends on the region** as well as the code, through the
snapshot's `currency_symbols`:

| Locale | USD | EUR | JPY |
| --- | --- | --- | --- |
| `en_US`, `de_DE`, `ja_JP`, `en_IN` | `$` | `€` | `¥`, or `JP¥` under `en_IN` |
| `en_GB`, `en_ZA`, `pt_BR` | `US$` | `€` | `JP¥` |
| `en_AU` | none, shown as `USD` | none, shown as `EUR` | none |

`en_AU` lists five symbols, none of them for these codes, so Numbers shows the code.

No cell's format changes, read through pybers in all nine. A cell's format names an ISO
code and a pattern, never a symbol or a separator, so it renders through the snapshot.

## Formula text: the region sets the separators, the language the names

Numbers stores the same formula nodes in every measurement, and pybers renders the same
text from each. Numbers displays that text with the region's separators and, for some
languages, translated function names:

| Cell | `en_US`, `en_GB`, `en_AU`, `en_IN`, `ja_JP` | `en_ZA` | `de_DE` | `pt_BR` |
| --- | --- | --- | --- | --- |
| F1 | `=1.5+2` | `=1,5+2` | `=1,5+2` | `=1,5+2` |
| G1 | `=SUM(1,2,3)` | `=SUM(1;2;3)` | `=SUMME(1;2;3)` | `=SOMA(1;2;3)` |
| H1 | `=DOLLAR(1234.5,2)` | `=DOLLAR(1234,5;2)` | `=EURO(1234,5;2)` | `=MOEDA(1234,5;2)` |
| I1 | `=FIXED(1234.567,1)` | `=FIXED(1234,567;1)` | `=FEST(1234,567;1)` | `=DEF.NÚM.DEC(1234,567;1)` |
| J1 | `=ROUND(A1,1)` | `=ROUND(A1;1)` | `=RUNDEN(A1;1)` | `=ARRED(A1;1)` |
| K1 | `=CONCATENATE(D1,"")` | `=CONCATENATE(D1;"")` | `=VERKETTEN(D1;"")` | `=CONCATENAR(D1;"")` |

- **The region's decimal separator decides both separators.** Where it is a comma, a
  number shows a comma and arguments are separated by `;`, under English (`en_ZA`) as
  much as under German.
- **The language decides a function's name**, and only some languages translate it:
  German and Portuguese do, Japanese does not.

pybers therefore keeps formula text in its English, `en_US` form whatever the document's
language and region, as the nodes it stores are the same, a rule recorded in
`docs/decisions.md`.

## Cached results that depend on the region are recalculated and saved

A formula whose result depends on the locale is recalculated when the region changes,
and the new result is written into the cell, so the cached value pybers reads changes:

| Cell | `en_US` | `de_DE` | `en_GB` | `ja_JP` | `en_ZA` | `pt_BR` | `en_AU` | `en_IN` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1, `DOLLAR` | `$1,234.50` | `1.234,50 €` | `£1,234.50` | `¥1,234.50` | `R 1 234,50` | `R$ 1.234,50` | `$1,234.50` | `₹1,234.50` |
| I1, `FIXED` | `1,234.6` | `1.234,6` | `1,234.6` | `1,234.6` | `1 234,6` | `1.234,6` | `1,234.6` | `1,234.6` |

- **`DOLLAR` shows the region's currency** with the decimals its argument asks for,
  `¥1,234.50` though the yen's own pattern has none.
- **A result that comes out the same is not rewritten.** `en_AU` leaves the string data
  list and the tile untouched, since its `$1,234.50` and `1,234.6` match `en_US`.
- **A date with an explicit pattern keeps its text.** `K1` reads `2026-10-27 14:30`
  everywhere, because `D1` carries a pattern no locale rewrites.

Rewritten text sits in the table's string data list and the cell's record in its tile,
and the calculation engine archive changes in every measurement.

## Values and the display of plain cells

No stored value changes: `1234.5`, `0.125` and the date read the same in every
measurement. What a cell displays changes through the snapshot alone:

| Cell | `en_US` | `de_DE` | `en_GB` | `ja_JP` | `en_ZA` | `pt_BR` | `en_AU` | `en_IN` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1, number | `1,234.50` | `1.234,50` | `1,234.50` | `1,234.50` | `1 234,50` | `1.234,50` | `1,234.50` | `1,234.50` |
| B1, euro | `€1234.50` | `1234,50 €` | `€1234.50` | `€1234.50` | `€1234,50` | `€ 1234,50` | `EUR 1234.50` | `€1234.50` |
| C1, US dollar | `$1234.50` | `1234,50 $` | `US$1234.50` | `$1234.50` | `US$1234,50` | `US$ 1234,50` | `USD 1234.50` | `$1234.50` |
| E1, percentage | `12.5%` | `12,5 %` | `12.5%` | `12.5%` | `12,5%` | `12,5%` | `12.5%` | `12.5%` |

The currencies show without grouping, as `B1` and `C1` were formatted with none.

## Not yet explained

- `95d`, `95e`, `95f`, `95g`, `95h` and `95i` changed their `documentUUID` and
  `DocumentIdentifier`, and `95d`, `95e`, `95h` and `95i` their theme archive, which
  `95b` and `95c` did not. `95e` to `95i` were saved with ⌘S, so the change follows
  from something other than the choice made, and it touches none of the locale's fields.
- Whether Numbers recalculates a document whose region pybers changed, leaving the
  cached results as they were, is not yet measured. The golden AC 10 asks for answers it.
- The rest of each change is view state, previews and tree nodes, which change on every
  save.

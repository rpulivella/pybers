<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo/pybers-lockup-dark.svg">
  <img src="docs/logo/pybers-lockup-light.svg" alt="pybers: a selected spreadsheet cell holding the Python prompt and a cursor, beside the name" width="272">
</picture>

# pybers

Read and write Apple Numbers documents from Python, with the aim that an edit made by script is as reliable as one made in Numbers by hand.

[![health](https://github.com/rpulivella/pybers/actions/workflows/health.yml/badge.svg?branch=develop)](https://github.com/rpulivella/pybers/actions/workflows/health.yml)
[![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/rpulivella/pybers/coverage/badge.json)](https://github.com/rpulivella/pybers/blob/coverage/README.md)
[![License](https://img.shields.io/github/license/rpulivella/pybers)](LICENSE)

> **Status, 28 October 2026:** pybers is early and unreleased. The Python library reads and writes real `.numbers` files, the command line has four commands, `pybers check`, `pybers show`, `pybers set` and `pybers locale`, and nothing is on PyPI yet.

## Command line

`pybers check FILE` says whether pybers can read a document, what it is running on, and the tree of its sheets and tables, each shown by its kind and size, in a form safe to paste into a public bug report. `--names` names each sheet, table and unrecognized cell, for the person holding the document.

`pybers set FILE SELECTOR VALUE` sets every cell a [selector](#selectors) matches, skipping a cell a formula backs, reading the value as a number, a currency amount, a boolean, a date, a duration or text unless `--as` names the kind. It prints each cell it wrote as `pybers show` prints it, and each it skipped on stderr with the reason. It changes FILE itself, `-o NEW` writes the change to a new document instead, and `--preview` shows the change without writing it:

```bash
pybers set budget.numbers "Summary::Costs::B4" 1250.00
pybers set budget.numbers "Summary::Costs::G4" "1250.00 EUR"
pybers set budget.numbers "Summary::Costs::C4" "2026-10-20 09:30"
pybers set budget.numbers "Summary::Costs::D4" "1h 30m"
pybers set budget.numbers "Summary::Costs::E4" TRUE
pybers set budget.numbers "Summary::Costs::F4" 1:30 --as duration
pybers set budget.numbers "Summary::Q*::B2" 0 --preview   # B2 of every quarter
```

A date is stored as wall-clock time, as Numbers stores it. One given with an offset, such as `2026-10-20T16:00Z`, is written as the time it was in the zone pybers is running in, or in the zone `--time-zone America/New_York` specifies.

`--as` specifies one of these kinds:

- `number`: `1250.00`, `-3.5`, `1e3`
- `currency`: an amount and the ISO 4217 code of a currency Numbers offers, `1250.00 EUR`
- `boolean`: `TRUE` or `FALSE`, in any case
- `date`: a date or a date and time in ISO 8601, `2026-10-20` or `2026-10-20 09:30`
- `duration`: Numbers' own units, `1h 30m` or `2d 4h`, or a clock, `1:30`
- `text`: anything, kept exactly as given

`pybers show FILE` prints a whole document, and `pybers show FILE SELECTOR` prints every part a [selector](#selectors) matches, each in full and one after another. Each part opens with a line naming it and folding what describes it, its children indented beneath it, and a count of zero is left out. `pybers show` never writes to the document.

```console
$ pybers show shapes.numbers
Locale: en_US

Sheet: Sheet 1  2 tables

  Table: Sheet 1::Table 1  12 rows × 8 columns  26 cells

    Cell: Sheet 1::Table 1::A1
      Value: 1   Kind: number   Formula text: none   Value cached: no
      Format: number (automatic)   Control: none
      Unrecognized type code: none
…
```

A cell folds the fields of its JSON form, in that form's order, onto three lines:

```console
$ pybers show shapes.numbers "Sheet 1::Table 1::A11"
Cell: Sheet 1::Table 1::A11
  Value: 55   Kind: number   Formula text: =SUM(A1:A10)   Value cached: yes
  Format: number (automatic)   Control: none
  Unrecognized type code: none
```

Several matches print each part exactly as it prints alone:

```console
$ pybers show shapes.numbers "::A11, *::Table 2[kind=number]"
Cell: Sheet 1::Table 1::A11
  Value: 55   Kind: number   Formula text: =SUM(A1:A10)   Value cached: yes
  Format: number (automatic)   Control: none
  Unrecognized type code: none

Cell: Sheet 1::Table 2::A1
  Value: 42   Kind: number   Formula text: none   Value cached: no
  Format: number (automatic)   Control: none
  Unrecognized type code: none
```

`--format json` prints the JSON form of what is selected, exactly as `pybers.formatJsonForm` writes it for a script, a selector's parts always as an array and a range as its table narrowed to it, and `pybers.parseJsonForm` reads it back, so a script and the command never disagree.

<details>
<summary>The JSON of the cell and of the table above</summary>

```console
$ pybers show shapes.numbers "Sheet 1::Table 1::A11" --format json
[
  {
    "jsonFormVersion": 5,
    "sheetName": "Sheet 1",
    "cell": "A11",
    "table": {
      "name": "Table 1",
      "identifier": "f3617f67f94a592f36e14fa6cc9846f8",
      "rowCount": 12,
      "colCount": 8,
      "headers": {
        "headerRows": 0,
        "headerColumns": 0,
        "footerRows": 0
      },
      "mergeRanges": [],
      "cells": [
        {
          "address": "A11",
          "value": 55,
          "kind": "number",
          "formulaText": "=SUM(A1:A10)",
          "valueCached": true,
          "presentation": {
            "format": {
              "formatFamily": "automatic",
              "shown": {
                "formatFamily": "number"
              }
            },
            "control": null
          },
          "unrecognizedTypeCode": null,
          "formula": "WITHHELD"
        }
      ]
    },
    "documentTables": [
      {
        "sheetPosition": 1,
        "sheetName": "Sheet 1",
        "name": "Table 1",
        "identifier": "f3617f67f94a592f36e14fa6cc9846f8",
        "rowCount": 12,
        "colCount": 8
      },
      {
        "sheetPosition": 1,
        "sheetName": "Sheet 1",
        "name": "Table 2",
        "identifier": "7fc8ce14cf4a692b380f869beca4f9ce",
        "rowCount": 10,
        "colCount": 5
      },
      {
        "sheetPosition": 2,
        "sheetName": "Sheet 2",
        "name": "Table 1",
        "identifier": "25e772dc0a40af2e3961d79e7e3be9ad",
        "rowCount": 10,
        "colCount": 5
      }
    ]
  }
]
```

```console
$ pybers show shapes.numbers "*::Table 2" --format json
[
  {
    "jsonFormVersion": 5,
    "sheetName": "Sheet 1",
    "table": {
      "name": "Table 2",
      "identifier": "7fc8ce14cf4a692b380f869beca4f9ce",
      "rowCount": 10,
      "colCount": 5,
      "headers": {
        "headerRows": 0,
        "headerColumns": 0,
        "footerRows": 0
      },
      "mergeRanges": [],
      "cells": [
        {
          "address": "A1",
          "value": 42,
          "kind": "number",
          "formulaText": null,
          "valueCached": false,
          "presentation": {
            "format": {
              "formatFamily": "automatic",
              "shown": {
                "formatFamily": "number"
              }
            },
            "control": null
          },
          "unrecognizedTypeCode": null,
          "formula": null
        }
      ]
    },
    "documentTables": [
      {
        "sheetPosition": 1,
        "sheetName": "Sheet 1",
        "name": "Table 1",
        "identifier": "f3617f67f94a592f36e14fa6cc9846f8",
        "rowCount": 12,
        "colCount": 8
      },
      {
        "sheetPosition": 1,
        "sheetName": "Sheet 1",
        "name": "Table 2",
        "identifier": "7fc8ce14cf4a692b380f869beca4f9ce",
        "rowCount": 10,
        "colCount": 5
      },
      {
        "sheetPosition": 2,
        "sheetName": "Sheet 2",
        "name": "Table 1",
        "identifier": "25e772dc0a40af2e3961d79e7e3be9ad",
        "rowCount": 10,
        "colCount": 5
      }
    ]
  }
]
```

</details>

`pybers locale FILE` prints a document's language and region as `pybers show` prints it, and `pybers locale FILE LOCALE` changes it as Numbers' Language & Region does, printing the region it holds afterward and writing as `pybers set` writes:

```console
$ pybers locale budget.numbers de_DE
Locale: de_DE
```

The document then shows its numbers, dates and currencies as Germany writes them, `1.234,50 €`, and Numbers recalculates every formula when it opens it, since a result such as `DOLLAR` follows the region. pybers builds each locale field from macOS's own locale data, read into pybers before a release, so it writes a region exactly as Numbers would, on any system pybers runs on.

All four install with the `cli` extra, `pip install -e ".[cli]"`. Next in the [planned work](#planned), a command will export any document as JSON, for inspecting, diffing and scripting a file without opening Numbers ([PYB-142](https://github.com/rpulivella/pybers/issues/142)), and a terminal interface for browsing a document read-only is planned after it ([PYB-171](https://github.com/rpulivella/pybers/issues/171)).

## Python library

pybers needs the Python that `requires-python` in `pyproject.toml` specifies, and its one runtime dependency is `protobuf`. Until the first release, install it from a clone:

```bash
pip install -e .
```

A new document starts with `pybers.create`, naming its language and region, and holds one sheet and no table until a script adds its own. Its archives are composed when it is first saved, so it holds nothing Numbers wrote:

```python
import pybers
from decimal import Decimal

document = pybers.create("en_US")
budget = document.sheet("Sheet 1").tableAdd("Budget", rows=4, cols=2)
budget.headersSet(headerRows=1)  # a header row, styled by Numbers
budget.cell("A1").value = "Rent"
budget.cell("B1").value = Decimal("1250.00")
budget.cell("B4").formulaText = "=SUM(B1:B3)"
document.save("budget.numbers")
```

An existing document opens with `pybers.open`, and every edit goes through it in the same way:

```python
import datetime
import pybers
from decimal import Decimal

document = pybers.open("budget.numbers", timeZone="America/New_York")

for sheet, table, cell in document.cellsIterate():
    print(sheet.name, table.name, cell.address, cell.value, cell.kind)

costs = document.sheet("Summary").table("Costs")
print(len(costs.cells), "cells hold something")
costs.cell("B4").value = Decimal("1250.00")
costs.cell("C4").value = datetime.datetime(2026, 10, 20, 9, 30)
costs.cell("D4").value = datetime.timedelta(hours=1, minutes=30)
costs.cell("E4").value = True
document.cellSet("Summary::Costs::B6", Decimal("300.00"))
costs.cell("B5").formulaText = "=SUM(B1:B4)"
costs.rowAdd(6)
document.localeSet("de_DE")  # Numbers' Language & Region, one of pybers.locales

document.save()
```

Any document, sheet, table, range or cell has one JSON form, and reads back from it:

```python
import json

text = pybers.formatJsonForm(costs)
form = json.loads(text, parse_float=Decimal, parse_int=Decimal)  # every number exact
assert pybers.parseJsonForm(text) == costs
```

A whole document read from its JSON form saves as a created document holding what the form describes. A cell holding something pybers cannot yet create, rich text, a control or a format such as a percentage, is refused by name before anything is written.

### Colors

A `Color` specifies its space and always includes an alpha (opacity). pybers does not convert it to another space. No call applies a color to a document yet, and [PYB-265](https://github.com/rpulivella/pybers/issues/265) adds the first. Build one through `import pybers` or read one from its text:

| System | Through `import pybers` | As text |
| --- | --- | --- |
| sRGB | `pybers.Color(pybers.ColorSpace.SRGB, (1, 0.5, 0), 1)` | `#ff8000ff` or `color(srgb 1 0.5 0 / 1)` |
| Display P3 | `pybers.Color(pybers.ColorSpace.DISPLAY_P3, (1, 0.5, 0), 1)` | `color(display-p3 1 0.5 0 / 1)` |
| CMYK | `pybers.Color(pybers.ColorSpace.DEVICE_CMYK, (0, 0, 0, 1), 1)` | `device-cmyk(0 0 0 1 / 1)` |
| grayscale | `pybers.Color.gray(0.5, 1)` | `device-gray(0.5 / 1)` |
| `black` token | `pybers.Color.black` | `black` |
| `white` token | `pybers.Color.white` | `white` |

`pybers.Color.parse(text)` reads each form and `str(color)` prints it. Text leaving out its alpha is refused, naming the form that carries it, and so is a model Numbers does not store, such as HSL or OKLCH. Components run from 0.0 to 1.0. Numbers stores every color as RGB, so a gray is three equal sRGB components, and `device-gray(0.5 / 1)` prints back as `color(srgb 0.5 0.5 0.5 / 1)`, which is what pybers stores. A document pybers creates holds RGB alone, and pybers reads and prints a CMYK color but creates none. `pybers.formatJsonForm(color)` writes a color's fields, and `pybers.parseJsonForm` reads them back equal.

### Selectors

One selector syntax reaches any sheet, table, range or cell, in the library, at the command line and for an agent alike, in the manner of CSS. It has three positions, sheet, table and cells, joined by `::`, and an empty position means any:

| Selector | Matches |
| -------- | ------- |
| `Budget` | The sheet `Budget` |
| `Budget::Q3` | The table `Q3` on `Budget` |
| `Budget::Q3::B2:D9` | A range of that table, and in the same place a cell `B3`, a column `B` or a row `3` |
| `*::Q3` | Every table named `Q3`, on any sheet |
| `::Q3::B4` | Cell `B4` of every table named `Q3`, filled from the right after a leading `::` |
| `::B3` | Cell `B3` of every table |
| `[kind=number]` | Every number in the document |
| `Budget::Q*[kind=number]` | Every number in the tables on `Budget` whose names start with `Q` |
| `Budget::Q*:not(Q4)::B:nth-row(2n):not(:empty)` | Every second row of column `B` holding something, in each quarter but the fourth |
| `Budget::*, Notes::Table 1` | Several selectors at once |

A condition reads what pybers models, `[kind=duration]`, `[format=currency]`, `[control=slider]` or `[conditional]`, and a pseudo-class a cell's state or place: `:empty`, `:formula`, `:merged`, `:header`, `:footer`, `:nth-row(2n+1)` and `:nth-column(3n)`. A backslash takes a character literally, so a sheet named `Q3, draft` is `Q3\, draft`. `document.select`, `sheet.select` and `table.select` read a selector relative to their owner, as a path is read, and return a tuple of references, changing nothing:

```python
for found in document.select("Summary::Costs[kind=number]"):
    print(found)  # Summary::Costs::B4, one reference per cell

print(document.sheet("Summary").select("Costs::B2:B6"))  # a tuple holding one CellRange
print(len(costs.select(":header")), "header cells")
```

An exact name matching nothing is refused, listing what the document holds, while a pattern or a condition matching nothing returns nothing. The full rules are in [`docs/library-design.md`](docs/library-design.md), under Addresses.

A table's `cells` maps each address to its cell and is read-only: a cell changes through the table, as `costs.cell("B4")` does above, so no edit can leave a table holding something that is not one of its cells.

A cell takes a value of any kind, whatever it held, and reads it back as the same Python type: `Decimal` for a number, `str`, `bool`, `datetime` for a date and time, and `timedelta` for a duration. Numeric values are `Decimal`, never `float`, because Numbers stores them as decimal128 and a binary float would add rounding error the document never had. A date is read as a naive `datetime`, the wall-clock time Numbers stores, and an aware one is written as the time it was in the document's zone, the one pybers is running in unless `pybers.open` specifies another.

## Capabilities

- Creating a document from nothing, in any region, which Numbers opens and into which a person can add any kind of object
- Opening a document and saving it back, with everything pybers does not change left exactly as it was
- Reading every cell's value, its kind (number, currency, text, date, duration and more) and its display format
- Writing numbers, text, dates and times, durations and booleans into any cell, and formulas as the text Numbers shows
- Adding and deleting rows and columns, with every formula and merge following
- Moving, copying and filling blocks of cells, a fill continuing a series as Numbers does
- Merging and unmerging cells, and creating sheets and tables
- Selecting any sheet, table, range or cell by one selector syntax, in the manner of CSS, by name, wildcard, a cell's kind, format or state, position pattern and negation
- Reading and setting a table's header rows, header columns and footer rows
- Showing any sheet, table, range or cell at the command line, as text or as its JSON form
- Changing a document's language and region as Numbers does, in any of 335 regions
- Writing a document or any part of one as JSON, and reading it back exactly
- Stating a color exactly as Numbers stores it, with its color space and alpha, in CSS syntax or as its fields

### Planned

- A command-line app that exports a document as JSON ([PYB-142](https://github.com/rpulivella/pybers/issues/142))
- A terminal interface for browsing a document read-only ([PYB-171](https://github.com/rpulivella/pybers/issues/171))
- Showing a value in any format the Data Format menu offers ([PYB-145](https://github.com/rpulivella/pybers/issues/145))
- Cell styling: fills, padding and alignment, borders, and named cell styles ([PYB-265](https://github.com/rpulivella/pybers/issues/265), [PYB-266](https://github.com/rpulivella/pybers/issues/266), [PYB-128](https://github.com/rpulivella/pybers/issues/128))
- Rich text: styled runs inside a cell, named paragraph styles, OpenType features, tracking and leading ([PYB-270](https://github.com/rpulivella/pybers/issues/270), [PYB-268](https://github.com/rpulivella/pybers/issues/268), [PYB-129](https://github.com/rpulivella/pybers/issues/129), [PYB-131](https://github.com/rpulivella/pybers/issues/131))
- Table appearance: banding, gridlines and outlines ([PYB-266](https://github.com/rpulivella/pybers/issues/266), [PYB-267](https://github.com/rpulivella/pybers/issues/267))
- Text boxes and the other objects floating on a sheet ([PYB-271](https://github.com/rpulivella/pybers/issues/271))
- Placing anything on a sheet by a named anchor, at the sizes Numbers draws ([PYB-87](https://github.com/rpulivella/pybers/issues/87))
- Calculating formula values, so a document read without opening Numbers shows what Numbers would ([PYB-196](https://github.com/rpulivella/pybers/issues/196), [PYB-197](https://github.com/rpulivella/pybers/issues/197), [PYB-198](https://github.com/rpulivella/pybers/issues/198))
- A release on PyPI ([PYB-148](https://github.com/rpulivella/pybers/issues/148))

### Not planned

- Charts
- Pivot tables
- Password-protected documents

## Verification

Every claim about the format is measured against real `.numbers` files that label their own contents, because a misread offset yields a wrong number rather than an error. Each of those files reads and writes back unchanged, and every golden file in [`tests/golden/`](tests/golden/) was confirmed in Numbers before becoming a permanent check. The measurements are in [`docs/findings/`](docs/findings/FINDINGS.md).

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers the setup, the four gates every pull request passes, the workflow and the repository layout.

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).

Contributing with an AI tool is welcome under the [AI policy](docs/ai-policy.md).

## Credits

pybers stands on [`numbers-parser`](https://github.com/masaccio/numbers-parser) by [masaccio](https://github.com/masaccio), which reverse-engineered Apple's undocumented archive format from nothing. No code from it is used here, and [`NOTICE`](NOTICE) records the debt.

## License

[Apache-2.0](LICENSE).

pybers is not affiliated with, endorsed by or sponsored by Apple Inc. Numbers is a trademark of Apple Inc.

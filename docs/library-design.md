# Library design

How pybers presents itself to Python: the shape every public call follows, so that a script, an agent and the command line all meet one library. What a command adds on top of a call is in [the command-line design](cli-design.md). The reasoning behind either belongs in `decisions.md`. This is the shape pybers is built toward, and a part not yet built is built to it by its own ticket.

## Users

- **A script author** keeps a budget or a report in Numbers, has code read it and write values back, and still opens it in Numbers by hand.
- **An agent** reads, changes and creates Numbers documents for a person, on any system Python runs on, with neither Numbers nor a Mac.

The library offers everything pybers can do. The command line offers the transactions and conversions a person or an agent runs one at a time.

## Types

A document is a tree of mutable owners, and everything a caller holds as a value is frozen. Numbers shares a style between cells by reference, so a value that could change in a caller's hands would restyle cells the caller never touched.

| Type | What it is | Kind |
| ---- | ---------- | ---- |
| `Document` | The handle: its sheets, and the one place a save starts | Owner |
| `Sheet` | A tab, holding its tables in the order Numbers shows them | Owner |
| `Table` | A grid of cells, with its size, its header and footer counts and its merges. `cells` is a read-only view, and a cell changes through the table | Owner |
| `TableHeaders` | How many header rows, header columns and footer rows a table holds | Frozen |
| `TableRows`, `TableRow` | The rows of a table, and one row's cells | View |
| `Cell` | One cell: its value, kind, formula and presentation | Owner |
| `CellPresentation` | How a cell shows its value: its format, whether a person chose it, and its control | Frozen |
| `CellControl` | The control a cell presents its value through, beside its format: one dataclass per control under `CellControlBase`, `CellControlUnknown` included | Frozen |
| `CellChange` | What a write did to one cell: value and kind before and after, and how far the table grew | Frozen |
| `CellChanges`, `CellSkip` | What a write did to every cell its selector matched, and each part it skipped, and why | Frozen |
| `LocaleChange` | What a region change did to a document: its locale before and after | Frozen |
| `CellValue` | `Decimal`, `CurrencyAmount`, `str`, `bool`, `datetime`, `timedelta` or `None`, never `float` | Value |
| `CellFormat` | How a cell shows its value: one dataclass per family, `CellFormatAutomatic` and `CellFormatUnknown` included, belonging to no document | Frozen |
| `Color` | A color in Numbers' own terms: its color space, its components, its alpha and its headroom, never converted | Frozen |
| `Formula` | A formula's tree of nodes, turned into text only on request | Frozen |
| `CellAddress` | Where a cell is in any table: a row and a column, counted from one, with no table and no `$` | Frozen |
| `CellOffset` | A signed distance between two addresses, in rows and columns | Frozen |
| `CellReference` | How something points at a cell: an address, `$` per axis, and the table it specifies when its context needs one | Frozen |
| `TableReference`, `SheetReference` | A table by name, its sheet's name when the table's is shared, and a sheet by name | Frozen |
| `CellRange`, `CellRangeList` | A rectangle of cells, specifying its table when its context needs one, and several | Frozen |
| `MergeRange` | A merged region | Frozen |
| `Selector` | What a caller selects with: groups of three positions and their conditions, the frozen form of the selector text | Frozen |
| `SelectionMatch` | One thing a selector matched: a `SheetReference`, a `TableReference`, a `CellRange` or a `CellReference`, qualified by its sheet and table | Alias |
| `CellReferenceLike`, `CellRangeLike`, `SelectorLike` | A reference, a range or a selector, or its text, wherever a call takes one | Alias |
| `TimeZoneLike` | A `tzinfo`, or a name `zoneinfo.ZoneInfo` knows, wherever a call takes a time zone | Alias |
| `MachineTimeZone` | The zone pybers is running in, a document's time zone unless `pybers.open` specifies another | Value |

A reference is qualified only as far as its context needs, as a path is. `table.cell` takes `B3` alone or a qualifier naming that table. A table keys its cells by `CellAddress`, so iterating a table yields addresses, and anything gathered across tables, a selection included, yields qualified references.

## One handle

Every document starts at one of two calls. `pybers.create(locale)` returns a new `Document` of one sheet holding no table, in the language and region specified, and `pybers.open(path)` returns one read from a file. Every edit goes through the document either returns. Nothing reaches the disk until `Document.save`, which writes a complete package atomically, either over the file it came from or to a new path. A document never read from a file, a created one or one read from its JSON form, has its archives composed on its first save, so it needs a path.

```python
document = pybers.open("budget.numbers")
table = document.sheet("Budget").table("Q3")
table.cell("B3").value = Decimal("1250.00")
table.cell("B4").formulaSet("=SUM(B1:B3)")
document.save()
```

## Addresses

**A reference is a path, and a selector is CSS.** A reference specifies one cell and resolves through the one resolver, qualified only as far as its context needs, as a path does. A selector matches sheets, tables, ranges and cells by pattern and returns references, as a CSS selector does: grouping with commas, wildcards, conditions on what pybers models, positions such as every nth row, and negation. Every way of selecting is one or the other, and one resolver reads both.

A selector has three positions, sheet, table and cells, joined by `::`, and an empty position means any. Written plainly its components fill the positions from the left, and after a leading `::` from the right, as the groups of an IPv6 address do, so a position always specifies the same part and no selector reads two ways:

| Form | Selects |
| ---- | ------- |
| `Budget` | A sheet |
| `Budget::Q3` | A table on it |
| `Budget::Q3::B3`, `Budget::Q3::B2:D9`, `Budget::Q3::B`, `Budget::Q3::3` | A cell, a range, a whole column, a whole row |
| `*::Q3`, `::Q3::B4`, `::B3` | Every table named `Q3`, then cell `B4` of each, then cell `B3` of every table |
| `Q*::*` | Every table of every sheet whose name starts with `Q` |
| `Budget::Q*[kind=number]` | Every number in those tables, a condition applying to the cells of everything selected |
| `Budget::*:not(Notes)::B:nth-row(2n):not(:empty)` | Negation of a name or a condition, and a position by pattern |
| `Budget::*, Notes::Table 1` | Several selectors at once |

- **`document.select`, `sheet.select` and `table.select` read a selector relative to their owner**, so a selector given to a table names its cells alone. Each returns a tuple of `SelectionMatch`: a sheet as a `SheetReference`, a table as a `TableReference`, a range as a `CellRange` naming its sheet and table, and a cell, or each cell a condition keeps, as a `CellReference`. Nothing is created or changed.
- **The typed lookups are one-group selections through the same resolver.** `document.sheet(name)`, `document.table(name)`, `sheet.table(name)` and `table.cell(address)` take a name literally, and given no name, `document.sheet()`, `document.table()` and `sheet.table()` return the only one there is, refusing several by listing them. `document.sheet` and `sheet.table` also take a position, counted from one in the file's own list.
- **A condition selects by what pybers models, never by what a cell holds.** `[kind=duration]`, `[format=currency]`, `[control=slider]` and `[conditional]` each read one field, named once in one table in `pybers.selection.conditions`, and a bare `[kind]` matches any value. `:empty`, `:formula`, `:merged`, `:header` and `:footer` read a cell's state, and `:nth-row(an+b)` and `:nth-column(an+b)` its place, counted from one.
- **A wildcard matches names in the shell's style**, with `*` and `?`, a table's name without regard to case and a sheet's with it. A backslash takes the next character literally, and `pybers.quoteSelectorName` writes any name so.
- **An exact name nothing carries is refused**, listing what the document holds, each name quoted, while a pattern or a condition matching nothing returns nothing. **A malformed selector is refused** naming the part and the column where it sits.
- **Matching is apart from acting.** An action states the selections it accepts. An action on each cell, such as `document.cellSet`, applies to every matched cell it can and reports each one it did not, and why, and one needing one block or one table, such as a merge, refuses any other shape before writing anything, listing what matched.

## Headers and footers

A table's header rows, header columns and footer rows are `table.headers`, set by `table.headersSet(headerRows=1, footerRows=1)`, each from 0 to 5, the most Numbers accepts. Numbers styles headers and footers itself, and a structural edit moves them as Numbers does. A change Numbers would not make is refused: a count past five, headers and footers leaving no row or no column outside them, whether set or reached by inserting or removing a line, and a change moving a cell read from a file into or out of them, since Numbers re-parents that cell's style and pybers does not.

## One call per command

Each command answers to one public call, and the call does the work.

- **A call returns data and prints nothing.** What it returns is a frozen dataclass, or the model itself, which the caller formats however it likes. `pybers.checkDocument` is the pattern.
- **A long call takes `onProgress`**, a callback that hears each step as it starts, so the caller decides how progress looks, if at all.
- **Nothing waits for input.** A call that cannot proceed raises.

## Writing a cell

A value's kind follows its Python type, as the table above lists. A currency amount is a `CurrencyAmount`, a `Decimal` amount with the ISO 4217 code of its currency, `CurrencyAmount(Decimal("1250.00"), "EUR")`, which adds, subtracts and compares only with an amount in the same currency. A number written into a currency cell keeps that cell's currency, as typing into one in Numbers does, and `pybers.currencies` lists the 37 currencies Numbers offers. A currency's symbol and where it sits come from the document's own locale, `document.localeIdentifier` such as `en_IT`, through `document.currencySymbolFind("EUR")` and `document.currencyPattern`, never from a table pybers keeps. An `int` is written as that exact number and a `date` as midnight, and a `float` is refused in favor of `Decimal`. A date is read as a naive `datetime`, the wall-clock time Numbers stores, and an aware one written is converted to the document's time zone, which `pybers.open(path, timeZone=...)` sets and which defaults to the zone pybers is running in.

- **A cell that changes kind takes the Automatic format** for its new kind, as a value typed into a fresh cell does, and loses any control the old value had.
- **A value write never fails because of the cell's format.** A value of the cell's kind keeps its format, and keeps its control while the control can show it; a control that cannot, such as a slider given a number outside its range, is dropped with its format.
- **A cell's kind and format always agree.** A format applied that cannot show the cell's value is refused, naming both, unless the call passes `CellFormatConflict.AUTOMATIC`.
- **Formats apply over a range**, with `table.cellFormatApply(range, format)`, and `document.cellSet(selector, ...)` sets every cell a selector matches, its value, format and style in one call, returning `CellChanges`: each change, and each part skipped and why, such as a cell a formula backs.
- **A write reports each cell whose kind or format it changed.** A preview is the same write left unsaved, as every command's `--preview` is, so no call takes a `preview` argument.
- **A table's structure is readable**: each column's kind and format, and the cells that differ from them.

The reasoning is in `decisions.md`, under writing values and formats.

## A document's language and region

`document.localeIdentifier` is the language and region a document shows its values in, such as `de_DE`, and `document.localeSet("de_DE")` changes it as Numbers' Language & Region does, returning a `LocaleChange`. `pybers.locales` lists the regions offered, and any other is refused with a `LocaleError` naming the closest. The save builds each locale field from a table pybers reads from macOS's own locale data before a release, and marks every formula for recalculation, since a result such as `DOLLAR` follows the region. The reasoning is in `decisions.md`, under a document's language and region.

## The JSON form

`pybers.formatJsonForm(subject)` returns a document, a sheet, a table, a table narrowed to one range, or a cell as JSON text, and a list of them as an array, a `(table, range)` pair being that table narrowed. `pybers.parseJsonForm(text)` reads either back into an equal model. It is the one serializer, so a command's `--format json` and a script's output are the same text, and any other value a call returns, a `Check` or a `CellChange`, is written by the same rules. Every number is a JSON number with its exact digits, read back exactly with `json.loads(text, parse_float=Decimal, parse_int=Decimal)`. The rule each value follows is in `decisions.md`, and `pybers/interchange/schema.json` describes the form.

## Colors

A `Color` specifies its space and always includes an alpha (opacity). pybers does not convert. `pybers.Color.parse(text)` reads its one text form and `str(color)` prints it, as the [README](../README.md#colors) shows for each color system.

## What is stored

pybers reports what a document stores and never calculates. A formula is returned as its formula, with the value Numbers last cached beside it, marked stale once an edit has changed a cell the formula reads. Numbers recalculates it on next opening.

## Errors

Every error is a `PybersError`, carrying a message that specifies the file and the reason. A message opens with what it is about, says what is wrong, then what to do. It says `pybers`, never "this library", calls a limit of pybers "not supported", and cuts any clause the reader does not need. A document pybers cannot read raises `ReadError`, a write it cannot complete `WriteError`, and a feature's own errors live with that feature. A call never prints an error. It returns a failure only when examining one is its purpose, as `checkDocument` does, and raises every other.

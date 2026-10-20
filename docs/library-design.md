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
| `Table` | A grid of cells, with its size and its merges. `cells` is a read-only view, and a cell changes through the table | Owner |
| `TableRows`, `TableRow` | The rows of a table, and one row's cells | View |
| `Cell` | One cell: its value, formula, style and stored description | Owner |
| `CellChange` | What a write did to one cell, or would do in a preview: value and kind before and after, and how far the table grew | Frozen |
| `CellValue` | `Decimal`, `str`, `bool`, `datetime`, `timedelta` or `None`, never `float` | Value |
| `CellFormat` | How a cell shows its value: one dataclass per family, `CellFormatAutomatic` and `CellFormatUnknown` included, belonging to no document | Frozen |
| `Formula` | A formula's tree of nodes, turned into text only on request | Frozen |
| `Style` | A cell's appearance | Frozen |
| `RichText` | Text with styled runs | Frozen |
| `CellAddress` | Where a cell is in any table: a row and a column, counted from one, with no table and no `$` | Frozen |
| `CellOffset` | A signed distance between two addresses, in rows and columns | Frozen |
| `CellReference` | How something points at a cell: an address, `$` per axis, and the table it specifies when its context needs one | Frozen |
| `TableReference`, `SheetReference` | A table by name, its sheet's name when the table's is shared, and a sheet by name | Frozen |
| `CellRange`, `CellRangeList` | A rectangle of cells, specifying its table when its context needs one, and several | Frozen |
| `MergeRange` | A merged region | Frozen |
| `CellReferenceLike`, `CellRangeLike` | A reference or a range, or its text, wherever a call takes one | Alias |

A reference is qualified only as far as its context needs, as a path is. Each owner takes its part and hands the rest down: `document.cell` needs the table named, `sheet.cell` takes a table on that sheet, and `table.cell` takes `B3` alone or a qualifier naming that table. A table keys its cells by `CellAddress`, so iterating a table yields addresses, and anything gathered across tables yields qualified references. A selector reaching several cells across sheets and tables, as under Addresses, becomes a frozen type of its own when it is built.

## One handle

`pybers.open(path)` returns a `Document`, and every edit goes through it. Nothing reaches the disk until `Document.save`, which writes a complete package atomically, either over the file it came from or to a new path.

```python
document = pybers.open("budget.numbers")
table = document.sheet("Budget").table("Q3")
table.cell("B3").value = Decimal("1250.00")
table.cell("B4").formulaSet("=SUM(B1:B3)")
document.save()
```

## Addresses

**A reference is a path, and a selector is CSS.** A reference specifies one cell and resolves through its owners, qualified only as far as its context needs, as a path does. A selector matches a set of cells by pattern and returns their references, as a CSS selector does: grouping with commas, wildcards, conditions on a cell's kind or format, positions such as every nth row, and negation. Every way of selecting cells is one or the other.

One syntax, Numbers' own, parsed by the library for every caller:

| Form | Selects |
| ---- | ------- |
| `Sheet 1::Table 1::B3` | One cell |
| `Table 1::B3` | One cell, when the table name is unique in the document |
| `Table 1::B3:D9`, `Table 1::B:B`, `Table 1::3:3` | A range, a whole column, a whole row |
| `Q*::*` | Every table of every sheet whose name starts with `Q` |
| `Budget::*, Notes::Table 1` | Several selectors at once |

- **An address names, never counts.** A sheet or table in an address is reached by its name, so nobody writing one has to know whether a count starts at 0 or 1.
- **An ambiguous address is refused**, listing the matches.
- **A wildcard matches names in the shell's style**, with `*` and `?`.

## One call per command

Each command answers to one public call, and the call does the work.

- **A call returns data and prints nothing.** What it returns is a frozen dataclass, or the model itself, which the caller formats however it likes. `pybers.checkDocument` is the pattern.
- **A long call takes `onProgress`**, a callback that hears each step as it starts, so the caller decides how progress looks, if at all.
- **Nothing waits for input.** A call that cannot proceed raises.

## Writing a cell

A value's kind follows its Python type, as the table above lists. An `int` is written as that exact number and a `date` as midnight, and a `float` is refused in favor of `Decimal`. A date is read as a naive `datetime`, the wall-clock time Numbers stores, and an aware one written is converted to the document's time zone, which `pybers.open(path, timeZone=...)` sets and which defaults to the zone pybers is running in.

- **A cell that changes kind takes the Automatic format** for its new kind, as a value typed into a fresh cell does, and loses any control the old value had.
- **A value write never fails because of the cell's format.** A value of the cell's kind keeps its format and control.
- **A cell's kind and format always agree.** A format applied that cannot show the cell's value is refused, naming both, unless the call passes `CellFormatConflict.AUTOMATIC`.
- **Formats apply over a range**, with `table.cellFormatApply(range, format)`, and `document.cellSet(reference, ...)` sets one cell's value, format and style in one call, returning the change. `document.cell(reference)` reaches a cell by a reference naming its table.
- **A write reports each cell whose kind or format it changed**, and `preview=True` reports the same without writing.
- **A table's structure is readable**: each column's kind and format, and the cells that differ from them.

The reasoning is in `decisions.md`, under writing values and formats.

## What is stored

pybers reports what a document stores and never calculates. A formula is returned as its formula, with the value Numbers last cached beside it, marked stale once an edit has changed a cell the formula reads. Numbers recalculates it on next opening.

## Errors

Every error is a `PybersError`, carrying a message that specifies the file and the reason. A message opens with what it is about, says what is wrong, then what to do. It says `pybers`, never "this library", calls a limit of pybers "not supported", and cuts any clause the reader does not need. A document pybers cannot read raises `ReadError`, a write it cannot complete `WriteError`, and a feature's own errors live with that feature. A call never prints an error. It returns a failure only when examining one is its purpose, as `checkDocument` does, and raises every other.

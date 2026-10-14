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
| `CellValue` | `Decimal`, `str`, `bool`, `datetime`, `timedelta` or `None`, never `float` | Value |
| `Formula` | A formula's tree of nodes, turned into text only on request | Frozen |
| `Style` | A cell's appearance | Frozen |
| `RichText` | Text with styled runs | Frozen |
| `CellReference` | One cell's address, `B3`, with `$` per axis | Frozen |
| `CellRange`, `CellRangeList` | A rectangle of cells, and several | Frozen |
| `MergeRange` | A merged region | Frozen |
| `CellAddress`, `RangeAddress` | A reference or its text, wherever a call takes one | Alias |

A selector reaching across sheets and tables, as under Addresses, becomes a frozen type of its own when it is built.

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

## What is stored

pybers reports what a document stores and never calculates. A formula is returned as its formula, with the value Numbers last cached beside it, marked stale once an edit has changed a cell the formula reads. Numbers recalculates it on next opening.

## Errors

Every error is a `PybersError`, carrying a message that names the file and the reason. A message opens with what it is about, says what is wrong, then what to do. It says `pybers`, never "this library", calls a limit of pybers "not supported", and cuts any clause the reader does not need. A document pybers cannot read raises `ReadError`, a write it cannot complete `WriteError`, and a feature's own errors live with that feature. A call never prints an error. It returns a failure only when examining one is its purpose, as `checkDocument` does, and raises every other.

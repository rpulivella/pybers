<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo/pybers-lockup-dark.svg">
  <img src="docs/logo/pybers-lockup-light.svg" alt="pybers: a selected spreadsheet cell holding the Python prompt and a cursor, beside the name" width="272">
</picture>

# pybers

Read and write Apple Numbers documents from Python, with the aim that an edit made by script is as reliable as one made in Numbers by hand.

[![health](https://github.com/rpulivella/pybers/actions/workflows/health.yml/badge.svg?branch=develop)](https://github.com/rpulivella/pybers/actions/workflows/health.yml)
[![License](https://img.shields.io/github/license/rpulivella/pybers)](LICENSE)

> **Status, 20 October 2026:** pybers is early and unreleased. The Python library reads and writes real `.numbers` files, the command line has two commands, `pybers check` and `pybers set`, and nothing is on PyPI yet.

## Command line

`pybers check FILE` says whether pybers can read a document and what it is running on, in a form safe to paste into a public bug report, and `--names` adds the document's sheets, tables and unrecognized cells for its owner. `pybers set FILE CELL VALUE` sets one cell, reading the value as a number or as text unless `--as` names the kind, and `--preview` shows the change without writing it:

```bash
pybers set budget.numbers "Summary::Costs::B4" 1250.00 --in-place
```

Both install with the `cli` extra, `pip install -e ".[cli]"`. Next in the [planned work](#planned), a command will export any document as JSON, for inspecting, diffing and scripting a file without opening Numbers ([PYB-142](https://github.com/rpulivella/pybers/issues/142)), and a terminal interface for browsing a document read-only is planned after it ([PYB-171](https://github.com/rpulivella/pybers/issues/171)).

## Python library

pybers needs the Python that `requires-python` in `pyproject.toml` names, and its one runtime dependency is `protobuf`. Until the first release, install it from a clone:

```bash
pip install -e .
```

```python
import pybers
from decimal import Decimal

document = pybers.open("budget.numbers")

for sheet, table, cell in document.cellsIterate():
    print(sheet.name, table.name, cell.address, cell.value, cell.description.kind)

costs = document.sheet("Summary").table("Costs")
print(len(costs.cells), "cells hold something")
costs.cell("B4").value = Decimal("1250.00")
document.cellSet("Summary::Costs::B6", Decimal("300.00"))
costs.cell("B5").formulaText = "=SUM(B1:B4)"
costs.rowAdd(6)

document.save()
```

A table's `cells` maps each address to its cell and is read-only: a cell changes through the table, as `costs.cell("B4")` does above, so no edit can leave a table holding something that is not one of its cells.

Numeric values are `Decimal`, never `float`, because Numbers stores them as decimal128 and a binary float would add rounding error the document never had.

## Capabilities

- Opening a document and saving it back, with everything pybers does not change left exactly as it was
- Reading every cell's value, its kind (number, currency, text, date, duration and more) and its display format
- Writing numbers and text, and formulas as the text Numbers shows
- Adding and deleting rows and columns, with every formula and merge following
- Moving, copying and filling blocks of cells, a fill continuing a series as Numbers does
- Merging and unmerging cells, and creating sheets and tables

### Planned

- A command-line app that exports a document as JSON ([PYB-142](https://github.com/rpulivella/pybers/issues/142))
- A terminal interface for browsing a document read-only ([PYB-171](https://github.com/rpulivella/pybers/issues/171))
- Writing any value type into any cell ([PYB-144](https://github.com/rpulivella/pybers/issues/144)), shown in any format the Data Format menu offers ([PYB-145](https://github.com/rpulivella/pybers/issues/145))
- Cell styling: fills, padding and alignment, borders, and named cell styles ([PYB-126](https://github.com/rpulivella/pybers/issues/126), [PYB-122](https://github.com/rpulivella/pybers/issues/122), [PYB-128](https://github.com/rpulivella/pybers/issues/128))
- Rich text: styled runs inside a cell, named paragraph styles, OpenType features, tracking and leading ([PYB-125](https://github.com/rpulivella/pybers/issues/125), [PYB-119](https://github.com/rpulivella/pybers/issues/119), [PYB-129](https://github.com/rpulivella/pybers/issues/129), [PYB-131](https://github.com/rpulivella/pybers/issues/131))
- Table appearance: banding, gridlines and outlines ([PYB-123](https://github.com/rpulivella/pybers/issues/123))
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

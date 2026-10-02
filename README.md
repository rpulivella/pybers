# pybers

Read and write Apple Numbers documents from Python, with the aim that an edit made by script is as reliable as one made in Numbers by hand.

[![License](https://img.shields.io/github/license/rpulivella/pybers)](LICENSE)

> **Status, 2026-10-01:** pybers is early and unreleased. The Python library reads and writes real `.numbers` files today, the command line is not built, and nothing is on PyPI yet.

## Command line

Planned. A command will print a document as JSON for inspecting, diffing and scripting without opening Numbers ([PYB-142](https://github.com/rpulivella/pybers/issues/142)), and a terminal interface will follow it.

## Python library

pybers needs Python 3.14 or newer, and its one runtime dependency is `protobuf`. Until the first release, install it from a clone:

```bash
pip install -e .
```

```python
import pybers
from decimal import Decimal

document = pybers.open("budget.numbers")

for sheet, table, cell in document.cellsIterate():
    print(sheet.name, table.name, cell.reference, cell.value, cell.description.kind)

costs = document.sheet("Summary").table("Costs")
costs.cell("B4").value = Decimal("1250.00")
costs.cell("B5").formulaText = "=SUM(B1:B4)"
costs.rowAdd(6)

document.save()
```

Numeric values are `Decimal`, never `float`, because Numbers stores them as decimal128 and a binary float would add rounding error the document never had.

## Capabilities

Built:

- Opening a document and saving it back, with everything pybers does not change left exactly as it was.
- Reading every cell's value, its kind (number, currency, text, date, duration and more) and its display format.
- Writing numbers and text, and formulas as the text Numbers shows.
- Adding and deleting rows and columns, with every formula and merge following.
- Moving, copying and filling blocks of cells, a fill continuing a series as Numbers does.
- Merging and unmerging cells, and creating sheets and tables.

Planned:

- Writing a date, a duration or a boolean into any cell ([PYB-144](https://github.com/rpulivella/pybers/issues/144)).
- Choosing the format a cell displays with ([PYB-145](https://github.com/rpulivella/pybers/issues/145)).
- Cell and text styles ([PYB-8](https://github.com/rpulivella/pybers/issues/8), [PYB-125](https://github.com/rpulivella/pybers/issues/125)).

[`CHANGELOG.md`](CHANGELOG.md) lists the rest.

## Verification

Every claim pybers makes about the format is measured against real `.numbers` files that label their own contents, because a misread offset in this format produces a wrong number rather than an error. Every one of those files reads and writes back unchanged, and every golden file in [`tests/golden/`](tests/golden/), each one a change pybers made, was opened and confirmed in Numbers before it became a permanent check. The measurements are written up in [`docs/findings/`](docs/findings/FINDINGS.md).

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers the setup, the four gates every pull request passes, the workflow and the repository layout.

## Credits

pybers stands on [`numbers-parser`](https://github.com/masaccio/numbers-parser) by [masaccio](https://github.com/masaccio), which reverse-engineered Apple's undocumented archive format from nothing. No code from it is used here, and [`NOTICE`](NOTICE) records the debt.

## License

[Apache-2.0](LICENSE).

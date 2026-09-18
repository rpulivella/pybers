# pybers

A round-trip-tested Python library for reading and writing Apple Numbers documents, built in deep respect for Apple Numbers itself. The goal is for editing a `.numbers` file programmatically to be as reliable as editing it by hand.

> **Status: early, and narrow.** A real `.numbers` file opens, its cells read, and > numbers, text, formulas, merges, sheets and tables can be written, so that Numbers > opens the saved file showing the result with nothing else altered. Styles, and > inserting or deleting rows and columns, are not built. See > [What works today](#what-works-today) for the honest line between finished and not.

## Why this exists

`pybers` exists because a real project needed a different foundation: dataclasses instead of the existing object model, a library and CLI/TUI split from the start, and named styles as a first-class concept rather than a retrofit. Those are design preferences, not criticisms, and they are worth a clean build rather than bending someone else's architecture around them.

There is a simpler reason under all of that: I love writing Python. Taking a `.numbers` file apart is satisfying work, and Python is where I wanted to do it.

`pybers` stands on the shoulders of [`numbers-parser`](https://github.com/masaccio/numbers-parser) by [masaccio](https://github.com/masaccio), which reverse-engineered Apple's entirely undocumented `.numbers` archive format, the protobuf schemas, the compression and the formula AST, from nothing. That is a rare piece of software archaeology, and every reader of this format builds on it. No code from it is used here, and the [`NOTICE`](NOTICE) file records the debt permanently.

## What works today

| Layer | State |
| --- | --- |
| `pybers._persistence` | The persistence layer, private. **Reads** a `.numbers` package: zip container, IWA frames, a pure-Python Snappy codec with no C dependency, base-128 varints, length-prefixed protobuf archives, IEEE-754 decimal128, and cell values including numbers, text, dates, booleans, durations and currency. **Writes** one back, replaying an untouched member exactly and re-encoding an edited one. |
| `pybers.addressing`, `pybers.document`, `pybers.formula`, `pybers.table` | The features, each owning its model types and both of its archive halves. `style`, `text`, `geometry` and `drawable` are model-only so far. |
| The binding between them | `pybers.open(path)` returns a `Document` and `document.save()` writes it back. A cell set to a `Decimal` reaches the tile it came from, and a cell's type can change: text over a number, a number over text, or text into a cell the file stored nothing for. |
| Reaching and walking | `document.sheet(...)` and `sheet.table(...)` take a name or a position counted from one, and both refuse a name no sheet or table carries rather than returning whichever came first. `document.cellsIterate()` yields every cell a document stores, in a stated order, with the table and sheet holding it. |
| Formulas | A formula is read and written as a typed AST rather than as text, so `cell.formulaText` renders one and setting it authors one. `table.formulaFill(...)` fills a formula across a range, and moving a reference rewrites its target. |
| Creating | `document.sheetAdd(...)` and `sheet.tableAdd(...)` create a sheet and a table, including the styles and the calculation-engine records Numbers expects. |
| Merging | `table.mergeAdd("A1:B1")` and `table.mergeRemove("A1")`. A merge discards the cells it covers, permanently, because that is what Numbers does. |
| Recalculation | An edit marks the cells it changed, so Numbers recomputes whatever depended on them when it next opens the file. This library never evaluates a formula. |
| `pybers.cli`, `pybers.tui` | Not started. |

```python
import pybers
from decimal import Decimal

document = pybers.open("budget.numbers")

for sheet, table, cell in document.cellsIterate():
    print(sheet.name, table.name, cell.reference, cell.value)

costs = document.sheet("Summary").table("Costs")
costs.cell("B4").value = Decimal("1250.00")
costs.mergeAdd("A1:C1")

document.save()
```

Every document under `tests/fixtures/` and `tests/measurements/` reads and writes back with each of its archives unchanged. Every file this library has written and had confirmed in Numbers lives in `tests/golden/`, each with the date and version of its confirmation, and the reasoning for keeping them is in its README. `/golden-confirm` drives one of those confirmations from a single command.

## The format, and why there are so many fixtures

Real `.numbers` files, each labeling its own contents so that a decode can be verified rather than merely believed, live in two places. `tests/fixtures/` holds the origins, and `tests/measurements/` holds documents made from an origin by one change. Each directory's README catalogs its files. What they established is written up in [`docs/findings/FINDINGS.md`](docs/findings/FINDINGS.md), split by topic. **Read that before designing anything against this format**, because several findings invalidate the obvious approach.

The format's characteristic failure is that a wrong offset yields wrong numbers rather than an error, which is why this project is built on real files rather than on assumptions. Seven findings changed what the library had to be:

- Cell numbers are **decimal128**, never `float`.
- Formulas are a **postfix AST with relative references**, so there is no formula text to parse, and `$` is a per-axis boolean rather than a character.
- **Merges are stored as formulas**, so a structural edit that ignores the merge store corrupts the document.
- Color carries a **color space**, so a bare RGB triple is not a color.
- All text formatting is a **named style plus a variation** layered on it, and there is no unparented text style.
- **Text run indices count UTF-16 code units**, not Python characters. One astral character silently shifts every later run boundary by one.
- **Numbers shares style archives by reference** between objects, so a decoder that hands out the same mutable object turns one edit into a restyle of unrelated shapes. `Style` is a frozen dataclass for exactly this reason, and that contract holds on the read path.

## Installation

Not published to PyPI yet. To work on it:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Requires Python 3.14 or newer. The only runtime dependency is `protobuf`.

## Repository map

| Path | What lives here |
| --- | --- |
| `src/pybers/` | The library, laid out by concern. A directory per feature, `_persistence/` and `_engine.py` beneath them, and `protos/` and `_generated/` for the extracted iWork schemas with their type stubs. A leading underscore means a caller has no business there. |
| `tests/` | The pytest suite, plus `fixtures/` (origins), `measurements/` (one change from an origin) and `golden/` (files pybers wrote, confirmed in Numbers). |
| `docs/` | Settled decisions, and `findings/`, what the real files established about the format. |
| `scripts/` | Repository tooling, including the schema extractor and the writing gate. See `scripts/README.md`. |
| `.claude/` | Project slash-commands used by the agentic workflow. |
| `.github/` | The pull request template, and the two workflows that check a pull request. |
| `workarea/` | Ephemeral scratch. Git-ignored apart from its README. |
| `CLAUDE.md` | Design contract, house style, and the record of every architectural decision with its reasoning. |
| `CONTRIBUTING.md` | Git workflow: commits, branches, releases. |

## The protobuf schemas are extracted, not copied

`src/pybers/protos/` holds 33 `.proto` schemas dumped from a local `Numbers.app`, and `src/pybers/_generated/` holds the modules `protoc` compiles from them. Both are committed, so `pip install pybers` works on a machine without Numbers present.

`tools/protos-extract.py` re-runs the extraction against a newer Numbers when Apple ships one. The technique, that Apple compiles the protobuf descriptors into the binary where they can be dumped, was learned from numbers-parser's build, and the extractor credits it in its docstring.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers the commit format, branch strategy and release tagging. Other details:

- **Four gates run before a pull request**, and all four are expected to be clean:

  ```bash
  .venv/bin/python3 scripts/pr-preflight-check.py
  ```

  One command runs pytest, ruff, mypy and the prose gate, and reports every one rather than stopping at the first. GitHub Actions runs that same command once a pull request leaves draft, so no second copy of the gate list exists to drift, and a second check then reports one verdict as a comment on the pull request. [`CONTRIBUTING.md`](CONTRIBUTING.md) describes that flow.

  The prose gate is the unusual one and worth explaining: it lints **prose**. Documentation, docstrings and comments are checked against the project's writing rules the way ruff checks code, because this repository treats a wrong comment as a defect.
- **Tickets are written `PYB-34` and pull requests `PR #38`**, never a bare number and never a bare `#`. The key is declared once in `pyproject.toml` under `[tool.pybers]`, and `scripts/ticket.py` reads it from there.
- **The house style is camelCase** for functions, variables and parameters, which is the opposite of what most Python tooling assumes. This is deliberate. Modules stay lowercase and classes stay PascalCase.

## License

[Apache-2.0](LICENSE). See [`NOTICE`](NOTICE) for attribution that carries forward into derivative works.

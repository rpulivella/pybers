#!/usr/bin/env python3
"""\
What a golden should show in Numbers, generated from its JSON form on every run.

The golden is written as its JSON form and read back, and every filled cell of every
table of what reads back is expected: its kind, value, formula, format and control.
What the JSON form loses therefore fails the check rather than passing unseen. Numbers
is the independent reader, so a check compares the two. A measurement labels each
value in row 1 with text in row 2, and such a label is shown beside the cell it
describes.

UPDATES
2026-10-24  Generated from the golden's JSON form, its machine form that form
            itself, and every value and control written by its rules, for PYB-259.
2026-10-22  Written for PYB-255.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pybers
from pybers import (
    UNDETERMINED,
    CellControl,
    CellFormat,
    CellKind,
    CurrencyAmount,
)

# A measurement's layout: each value in row 1, the text describing it in row 2.
measuredRow: int = 1
labelRow: int = 2


@dataclass(frozen=True, slots=True)
class ExpectedCell:
    """One filled cell as pybers reads it, and the cell beneath that describes it."""

    cell: str
    kind: CellKind
    value: pybers.CellValue
    formula: str | None
    format: CellFormat | None
    formatChosen: bool
    control: CellControl | None
    currencyMenu: str | None
    label: str | None


@dataclass(frozen=True, slots=True)
class ExpectedTable:
    """One table's size, merges and filled cells, every other cell empty."""

    sheet: str
    table: str
    rows: int
    columns: int
    merges: tuple[str, ...]
    cells: tuple[ExpectedCell, ...]


@dataclass(frozen=True, slots=True)
class ExpectedValues:
    """Everything a golden should show, table by table, and its JSON form."""

    golden: Path
    tables: tuple[ExpectedTable, ...]
    jsonForm: str


def formatMenuCurrency(code: str, document: pybers.Document) -> str:
    """Return a currency as Numbers' Currency menu titles it, `Swiss Franc (CHF)`."""
    shown = document.currencySymbolFind(code) or code
    return f"{pybers.findCurrency(code).name} ({shown})"


def findLabels(table: pybers.Table) -> dict[pybers.CellAddress, pybers.CellAddress]:
    """Return each measured cell's label, when a table is laid out as a measurement.

    A label beneath an empty cell describes nothing, so it is left its own entry. The
    rows below the labels may hold what the measured cells read, but never text, which
    is how a table of text data is told from a measurement.
    """
    filled = {address: cell for address, cell in table.cells.items()
              if cell.value is not None or cell.formula is not None}
    labels = [address for address in filled if address.row == labelRow]
    textBelow = any(address.row > labelRow and isinstance(cell.value, str)
                    for address, cell in filled.items())
    if not labels or textBelow or not all(
        isinstance(filled[label].value, str) and filled[label].formula is None
        for label in labels
    ):
        return {}
    return {measured: label for label in labels
            if (measured := pybers.CellAddress(measuredRow, label.col)) in filled}


def readExpectedCell(
    cell: pybers.Cell, document: pybers.Document, label: pybers.CellAddress | None
) -> ExpectedCell:
    """Return one filled cell as pybers reads it."""
    presentation = cell.presentation
    if presentation.format is UNDETERMINED:
        raise RuntimeError(f"{cell.address} was read with an edit pending")
    value = cell.value
    menu = (formatMenuCurrency(value.currency, document)
            if isinstance(value, CurrencyAmount) else None)
    return ExpectedCell(
        cell=str(cell.address), kind=cell.kind, value=value, formula=cell.formulaText,
        format=presentation.format, formatChosen=presentation.formatChosen,
        control=presentation.control, currencyMenu=menu,
        label=None if label is None else str(label),
    )


def buildExpectedValues(golden: Path) -> ExpectedValues:
    """Return what every table of a golden should show, read through its JSON form."""
    document = pybers.open(golden)
    jsonForm = pybers.formatJsonForm(document)
    readBack = pybers.parseJsonForm(jsonForm)
    assert isinstance(readBack, pybers.Document)
    tables = []
    for sheet in readBack.sheets:
        for table in sheet.tables:
            labels = findLabels(table)
            cells = tuple(
                readExpectedCell(cell, document, labels.get(address))
                for address, cell in sorted(
                    table.cells.items(), key=lambda each: each[0].asRowColumn())
                if cell.value is not None or cell.formula is not None
            )
            tables.append(ExpectedTable(
                sheet=sheet.name, table=table.name, rows=table.rowCount,
                columns=table.colCount,
                merges=tuple(str(merge.extent) for merge in table.mergeRanges),
                cells=cells,
            ))
    return ExpectedValues(golden, tuple(tables), jsonForm)


def readJsonTree(value: object) -> object:
    """Return a value as the JSON form writes it, each number a Decimal."""
    return json.loads(
        pybers.formatJsonForm(value), parse_float=Decimal, parse_int=Decimal
    )


def formatValue(value: pybers.CellValue) -> str:
    """Return a value as the JSON form writes it, a currency amount by its amount."""
    shown = value.amount if isinstance(value, CurrencyAmount) else value
    return pybers.formatJsonForm(shown)


def listControlFields(control: CellControl) -> list[tuple[str, str]]:
    """Return a control's type and settings, by the names its JSON form gives them."""
    tree = readJsonTree(control)
    assert isinstance(tree, dict)
    return [
        (name, ", ".join(map(str, setting)) if isinstance(setting, list)
         else str(setting).lower() if isinstance(setting, bool) else str(setting))
        for name, setting in tree.items()
    ]


def formatFormat(cell: ExpectedCell) -> str:
    """Return a cell's format and whether a person chose it, `currency, chosen`."""
    family = "none" if cell.format is None else cell.format.value
    return f"{family}, {'chosen' if cell.formatChosen else 'automatic'}"


def writeExpectationsJson(expected: ExpectedValues, into: Path) -> Path:
    """Write the machine form of the expectations, which is the golden's JSON form."""
    path = into / "expectations.json"
    path.write_text(expected.jsonForm + "\n")
    return path


def listCellBullets(cell: ExpectedCell) -> list[str]:
    """Return a cell's JSON form flattened, one labeled bullet per leaf."""
    bullets = []
    if cell.value is not None:
        shown = formatValue(cell.value)
        bullets.append(f"- value: `{shown.strip(chr(34))}`")
    if cell.formula is not None:
        bullets.append(f"- formula: `{cell.formula}`")
    bullets.append(f"- kind: {cell.kind.value}")
    bullets.append(f"- format: {formatFormat(cell)}")
    if cell.currencyMenu is not None:
        bullets.append(f"- currency: {cell.currencyMenu}")
    if cell.control is not None:
        for name, setting in listControlFields(cell.control):
            bullets.append(f"- {name}: {setting}")
    return bullets


def writeExpectations(expected: ExpectedValues, into: Path) -> Path:
    """Write what Numbers should show, each measured cell followed by its label."""
    lines = [f"# {expected.golden.name}"]
    for table in expected.tables:
        merged = ", ".join(table.merges) or "nothing"
        lines += ["", f"## {table.sheet} › {table.table}", "",
                  f"{table.rows} rows × {table.columns} columns · merged {merged} · "
                  f"{len(table.cells)} filled, every other cell empty"]
        labels = {cell.label: cell.cell for cell in table.cells if cell.label}
        byName = {cell.cell: cell for cell in table.cells}
        for cell in table.cells:
            if cell.cell in labels:
                continue
            heading = f"### {cell.cell}" + (" · measured" if cell.label else "")
            lines += ["", heading, *listCellBullets(cell)]
            if cell.label is not None:
                label = byName[cell.label]
                lines += ["", f"### {label.cell} · describes {cell.cell}",
                          f"- value: {label.value}", f"- format: {formatFormat(label)}"]
    path = into / "expectations.md"
    path.write_text("\n".join(lines) + "\n")
    return path


__all__ = [
    "ExpectedCell",
    "labelRow",
    "measuredRow",
    "ExpectedTable",
    "ExpectedValues",
    "buildExpectedValues",
    "formatValue",
    "listControlFields",
    "writeExpectations",
    "writeExpectationsJson",
]

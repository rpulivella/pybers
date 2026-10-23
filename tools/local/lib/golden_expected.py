#!/usr/bin/env python3
"""\
What a golden should show in Numbers, generated from the golden on every run.

Every filled cell of every table is read through pybers, as a cell's JSON form would
hold it: its kind, value, formula, format and control. Numbers is the independent
reader, so a check compares the two. A measurement labels each value in row 1 with
text in row 2, and such a label is shown beside the cell it describes.

UPDATES
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
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import assert_never

import pybers
from pybers import (
    UNDETERMINED,
    CellControl,
    CellControlCheckbox,
    CellControlPopUpMenu,
    CellControlSlider,
    CellControlStarRating,
    CellControlStepper,
    CellControlUnknown,
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
    """Everything a golden should show, table by table."""

    golden: Path
    tables: tuple[ExpectedTable, ...]


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
    """Return what every table of a golden should show, read from the golden."""
    document = pybers.open(golden)
    tables = []
    for sheet in document.sheets:
        for table in sheet.tables:
            labels = findLabels(table)
            cells = tuple(
                readExpectedCell(cell, document, labels.get(address))
                for address, cell in sorted(
                    table.cells.items(), key=lambda each: (each[0].row, each[0].col))
                if cell.value is not None or cell.formula is not None
            )
            tables.append(ExpectedTable(
                sheet=sheet.name, table=table.name, rows=table.rowCount,
                columns=table.colCount,
                merges=tuple(str(merge.extent) for merge in table.mergeRanges),
                cells=cells,
            ))
    return ExpectedValues(golden, tuple(tables))


def formatValue(value: pybers.CellValue) -> str:
    """Return a value as a TOML literal, a duration as its seconds."""
    match value:
        case bool():
            return "true" if value else "false"
        case CurrencyAmount():
            return str(value.amount)
        case Decimal():
            return str(value)
        case str():
            return json.dumps(value, ensure_ascii=False)
        case datetime():
            return value.isoformat()
        case timedelta():
            return str(Decimal(str(value.total_seconds())))
        case _:
            return json.dumps(str(value), ensure_ascii=False)


def listControlFields(control: CellControl) -> list[tuple[str, str]]:
    """Return a control's kind and settings, as a cell's JSON form names them."""
    match control:
        case CellControlCheckbox():
            return [("kind", "checkbox")]
        case CellControlStarRating():
            return [("kind", "star rating")]
        case CellControlSlider(minimum, maximum, increment):
            return [("kind", "slider"), ("minimum", str(minimum)),
                    ("maximum", str(maximum)), ("increment", str(increment))]
        case CellControlStepper(minimum, maximum, increment):
            return [("kind", "stepper"), ("minimum", str(minimum)),
                    ("maximum", str(maximum)), ("increment", str(increment))]
        case CellControlPopUpMenu(items, startsWithFirstItem):
            return [("kind", "pop-up menu"), ("items", ", ".join(items)),
                    ("starts with", "first item" if startsWithFirstItem else "blank")]
        case CellControlUnknown(interactionType):
            return [("kind", f"unknown interaction type {interactionType}")]
        case _:
            assert_never(control)


def formatFormat(cell: ExpectedCell) -> str:
    """Return a cell's format and whether a person chose it, `currency, chosen`."""
    family = "none" if cell.format is None else cell.format.value
    return f"{family}, {'chosen' if cell.formatChosen else 'automatic'}"


def writeExpectationsToml(expected: ExpectedValues, into: Path) -> Path:
    """Write the expected values as TOML, the machine form of the Markdown."""
    lines = [f"# What {expected.golden.name} should show, generated from it by",
             "# `buildExpectedValues` in `tools/local/lib/golden_expected.py`."]
    for table in expected.tables:
        merges = ", ".join(json.dumps(merge) for merge in table.merges)
        lines += ["", "[[table]]", f"sheet = {json.dumps(table.sheet)}",
                  f"table = {json.dumps(table.table)}", f"rows = {table.rows}",
                  f"columns = {table.columns}", f"merges = [{merges}]"]
        for cell in table.cells:
            lines += ["", "[[table.cell]]", f"cell = {json.dumps(cell.cell)}",
                      f'kind = "{cell.kind.value}"']
            if cell.value is not None:
                lines.append(f"value = {formatValue(cell.value)}")
            if isinstance(cell.value, CurrencyAmount):
                lines.append(f'currency = "{cell.value.currency}"')
            if cell.formula is not None:
                lines.append(f"formula = {json.dumps(cell.formula)}")
            if cell.format is not None:
                lines.append(f'format = "{cell.format.value}"')
            lines.append(f"formatChosen = {'true' if cell.formatChosen else 'false'}")
            if cell.control is not None:
                fields = ", ".join(f"{json.dumps(name)} = {json.dumps(setting)}"
                                   for name, setting in listControlFields(cell.control))
                lines.append(f"control = {{ {fields} }}")
            if cell.label is not None:
                lines.append(f"label = {json.dumps(cell.label)}")
    path = into / "expectations.toml"
    path.write_text("\n".join(lines) + "\n")
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
            named = "control" if name == "kind" else f"control {name}"
            bullets.append(f"- {named}: {setting}")
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
    "writeExpectationsToml",
]

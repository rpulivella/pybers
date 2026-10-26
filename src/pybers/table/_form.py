#!/usr/bin/env python3
"""\
A table and its cells as the JSON form holds them, and the form built back into both.

The table feature owns which names a cell shows, so `CellForm` holds exactly the
public names of `Cell`, and rebuilding a cell sets the same private state the archive
reader sets. A formula is written as its text, and as its nodes too when the text
would not parse back to them, such as one holding typed whitespace. A formula whose
text suffices carries `WITHHELD` there. The reader rebuilds a cell among the same
table names it was written with, so the cell's own names decide.

Private. The JSON form's half of the table feature, beside `_read` and `_write`.

UPDATES
2026-10-24  Written for PYB-259.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import ClassVar

from pybers.absence import WITHHELD
from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellAddress
from pybers.errors import PybersError
from pybers.formula.nodes import Formula
from pybers.formula.parse import parseFormula
from pybers.interchange._leaves import JsonFormError
from pybers.interchange._tree import jsonFormReadOnly
from pybers.table.cell import Cell, CellValue
from pybers.table.cells import Table
from pybers.table.kinds import (
    CellKind,
    CellPresentation,
    CellStorage,
    kindValueTypes,
)
from pybers.table.merges import MergeRange

# Kinds whose cell holds no value, so a value of None needs no formula to explain it.
valuelessKinds: frozenset[CellKind] = frozenset(
    {CellKind.EMPTY, CellKind.ERROR, CellKind.UNKNOWN}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CellForm:
    """One cell as the JSON form holds it, in the order PYB-260's `pybers show` uses."""

    address: CellAddress
    value: CellValue
    kind: CellKind
    formulaText: str | None
    valueCached: bool | None = field(default=None, metadata={jsonFormReadOnly: True})
    presentation: CellPresentation
    unrecognizedTypeCode: int | None = None
    formula: Formula | WITHHELD | None = WITHHELD

    # The value is read as the type its kind holds, or as null where a formula
    # backs it, since a formula given no value is held uncalculated.
    jsonFormChoices: ClassVar[frozendict[str, tuple[str, Mapping[CellKind, type]]]] = (
        frozendict(value=("kind", kindValueTypes))
    )


@dataclass(frozen=True, slots=True)
class TableForm:
    """One table as the JSON form holds it, its cells in row order."""

    name: str
    identifier: str
    rowCount: int
    colCount: int
    mergeRanges: tuple[MergeRange, ...]
    cells: tuple[CellForm, ...]


def buildTableForm(table: Table, extent: CellRange | None = None) -> TableForm:
    """Return a table's form, holding only the cells within `extent` if one is given."""
    cells = sorted(table.cells.items(), key=lambda each: each[0].asRowColumn())
    return TableForm(
        name=table.name, identifier=table.identifier, rowCount=table.rowCount,
        colCount=table.colCount, mergeRanges=tuple(table.mergeRanges),
        cells=tuple(
            buildCellForm(cell) for address, cell in cells
            if extent is None or extent.covers(address)
        ),
    )


def buildCellForm(cell: Cell) -> CellForm:
    """Return a cell's form, its nodes carried only when its text would lose them."""
    text, stored = cell.formulaText, cell.formula
    formula: Formula | WITHHELD | None = stored
    if stored is not None and text is not None and checkParsesBack(
        text, cell.address, cell.tableNames, stored
    ):
        formula = WITHHELD
    return CellForm(
        address=cell.address, value=cell.value, kind=cell.kind, formulaText=text,
        valueCached=cell.valueCached, presentation=cell.presentation,
        unrecognizedTypeCode=cell.unrecognizedTypeCode, formula=formula,
    )


def checkParsesBack(
    text: str, address: CellAddress, names: Mapping[str, str], formula: Formula
) -> bool:
    """Report whether a formula's text parses back to its nodes, given these names."""
    try:
        return parseFormula(text, address, tables=names) == formula
    except PybersError:
        return False


def buildTable(form: TableForm, path: str) -> Table:
    """Return the table a form describes, its formulas left for `assignFormulas`."""
    table = Table(
        name=form.name, rowCount=form.rowCount, colCount=form.colCount,
        mergeRanges=list(form.mergeRanges), identifier=form.identifier,
    )
    for index, cellForm in enumerate(form.cells):
        addCell(table, cellForm, f"{path}.cells[{index}]")
    return table


def addCell(table: Table, form: CellForm, path: str) -> None:
    """Give a table the cell a form describes, as the archive reader gives one."""
    backed = form.formulaText is not None
    if form.valueCached is not None and form.valueCached is not backed:
        raise JsonFormError(
            f"{path}.valueCached is {str(form.valueCached).lower()}, and the cell "
            f"{'holds' if backed else 'holds no'} formula."
        )
    if form.value is None and not backed and form.kind not in valuelessKinds:
        raise JsonFormError(f"{path} is a {form.kind} cell holding no value.")
    if form.unrecognizedTypeCode is not None and form.kind is not CellKind.UNKNOWN:
        raise JsonFormError(
            f"{path} names an unrecognized type code, and its kind is {form.kind}."
        )
    try:
        cell = table.cell(form.address)
    except PybersError as exc:
        raise JsonFormError(f"{path}: {exc}") from exc
    cell._stored = CellStorage(form.kind, form.presentation, form.unrecognizedTypeCode)
    cell._value = form.value
    cell._storedValue = form.value


def assignFormulas(table: Table, form: TableForm, path: str) -> None:
    """Give each cell its formula, once the table can name every table it reaches.

    Nodes the form carries are used when they render as its text, and text alone
    is parsed against the cell, so a form never holds a formula it does not show.
    """
    for index, cellForm in enumerate(form.cells):
        where = f"{path}.cells[{index}]"
        cell = table.cells[cellForm.address]
        text, formula = cellForm.formulaText, cellForm.formula
        if text is None:
            if isinstance(formula, Formula):
                raise JsonFormError(
                    f"{where} carries formula nodes and no formulaText."
                )
            continue
        if formula is None:
            raise JsonFormError(f"{where} has formulaText and a formula of null.")
        if isinstance(formula, Formula):
            cell.formula = formula
            if cell.formulaText != text:
                raise JsonFormError(
                    f"{where}: its nodes show {cell.formulaText!r}, and its "
                    f"formulaText is {text!r}."
                )
            continue
        try:
            cell.formulaSet(text)
        except PybersError as exc:
            raise JsonFormError(f"{where}.formulaText: {exc}") from exc


__all__ = [
    "CellForm",
    "TableForm",
    "buildCellForm",
    "buildTable",
    "buildTableForm",
    "assignFormulas",
]

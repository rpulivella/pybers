#!/usr/bin/env python3
"""\
What a formula reads, as the calculation engine records it.

A formula's nodes say where its operands sit relative to the cell holding it. The
engine keeps the same fact the other way round, as absolute coordinates hanging off
that cell, so that editing an operand tells Numbers which formulas to recompute.
Deriving one from the other is this module, and nothing here knows an archive.

**A formula whose precedents are not declared is evaluated once and never again.**
Numbers computes it on open, in an order of its own, and a formula reading a cell
computed later caches the error that cell still held. Measured 2026-09-16 for
PYB-86, see findings-02-formulas.md.

UPDATES
2026-09-18  A range of one cell reads as that cell, for PYB-17.
2026-09-16  Written for PYB-86.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/16"

from dataclasses import dataclass

from pybers.addressing.reference import CellReference, originOffset
from pybers.formula.nodes import Formula, FormulaRange, FormulaReference


@dataclass(frozen=True, slots=True)
class CellPrecedent:
    """One cell a formula reads, counted from zero, in the table it names."""

    row: int
    column: int
    tableId: str | None


@dataclass(frozen=True, slots=True)
class RangePrecedent:
    """One bounded rectangle a formula reads, counted from zero."""

    top: int
    left: int
    bottom: int
    right: int
    tableId: str | None


@dataclass(frozen=True, slots=True)
class SpanPrecedent:
    """Whole columns or whole rows a formula reads, counted from zero.

    An axis without bounds is what `SUM(A)` names, and the engine keeps it apart
    from a rectangle because it grows with the table rather than staying put.
    """

    begin: int
    end: int
    columns: bool
    tableId: str | None


@dataclass(frozen=True, slots=True)
class Precedents:
    """Everything one formula reads, grouped as the engine's registers group it."""

    cells: tuple[CellPrecedent, ...] = ()
    ranges: tuple[RangePrecedent, ...] = ()
    spans: tuple[SpanPrecedent, ...] = ()


def resolveFormulaPrecedents(formula: Formula, host: CellReference) -> Precedents:
    """Return what a formula reads, resolved against the cell holding it.

    Duplicates are dropped and order is kept, since a call naming one range twice
    is one dependency to the engine, as `SUMIFS` shows in `20-formula-shapes`.
    """
    cells: dict[CellPrecedent, None] = {}
    ranges: dict[RangePrecedent, None] = {}
    spans: dict[SpanPrecedent, None] = {}
    for node in formula.nodes:
        content = node.content
        if isinstance(content, FormulaReference):
            if content.broken:
                continue
            if content.row is None or content.column is None:
                spans.update(dict.fromkeys(expandReferenceSpans(content, host)))
                continue
            cells[
                CellPrecedent(
                    row=content.row.resolve(host.row) - originOffset,
                    column=content.column.resolve(host.col) - originOffset,
                    tableId=content.tableId,
                )
            ] = None
        elif isinstance(content, FormulaRange):
            extent = content.resolve(host)
            if extent.startRow is None or extent.endRow is None:
                whole = expandRangeSpans(
                    extent.startCol, extent.endCol, True, content.tableId
                )
                spans.update(dict.fromkeys(whole))
            elif extent.startCol is None or extent.endCol is None:
                whole = expandRangeSpans(
                    extent.startRow, extent.endRow, False, content.tableId
                )
                spans.update(dict.fromkeys(whole))
            elif (extent.startRow, extent.startCol) == (extent.endRow, extent.endCol):
                # One cell is a cell edge however it was written, as Numbers
                # registered `SUM(A2:A2)` in `56c-row-deleted`.
                cells[
                    CellPrecedent(
                        row=extent.startRow - originOffset,
                        column=extent.startCol - originOffset,
                        tableId=content.tableId,
                    )
                ] = None
            else:
                ranges[
                    RangePrecedent(
                        top=extent.startRow - originOffset,
                        left=extent.startCol - originOffset,
                        bottom=extent.endRow - originOffset,
                        right=extent.endCol - originOffset,
                        tableId=content.tableId,
                    )
                ] = None
    return Precedents(tuple(cells), tuple(ranges), tuple(spans))


def expandReferenceSpans(
    reference: FormulaReference, host: CellReference
) -> list[SpanPrecedent]:
    """Return the whole column or row one unbounded reference names."""
    if reference.column is not None:
        line = reference.column.resolve(host.col) - originOffset
        return [SpanPrecedent(line, line, True, reference.tableId)]
    if reference.row is not None:
        line = reference.row.resolve(host.row) - originOffset
        return [SpanPrecedent(line, line, False, reference.tableId)]
    return []


def expandRangeSpans(
    begin: int | None, end: int | None, columns: bool, tableId: str | None
) -> list[SpanPrecedent]:
    """Return the whole columns or rows one half-unbounded range names."""
    if begin is None or end is None:
        return []
    return [
        SpanPrecedent(begin - originOffset, end - originOffset, columns, tableId)
    ]


__all__ = [
    "CellPrecedent",
    "Precedents",
    "RangePrecedent",
    "SpanPrecedent",
    "resolveFormulaPrecedents",
]

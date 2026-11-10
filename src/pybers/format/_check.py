#!/usr/bin/env python3
"""\
Whether a cell can take a format or a control, judged before any cell changes.

A format must show the value the cell would hold, and a control must show its value
through a format it uses, as findings-11-formats.md measures. What fits and what pybers
can write yet are told apart, so a caller can fall back to Automatic for the first.

Private. The format feature's checks on a write, which `Document.cellSet` makes.

UPDATES
2026-11-10  Written for PYB-145, from the checks `pybers.table.cell` held.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

from typing import TYPE_CHECKING

from pybers.absence import UNCHANGED, UNDETERMINED
from pybers.addressing.reference import CellReference
from pybers.format._read import findFormatOfType
from pybers.format._write import findAutomaticFormat
from pybers.format.controls import CellControl, controlFormatFamilies
from pybers.format.formats import CellFormat, CellFormatAutomatic, findFormatShown
from pybers.table.cell import isSameValue
from pybers.table.kinds import CellKind, findCellKind, kindFormatFamilies

if TYPE_CHECKING:
    from pybers.table.cell import Cell, CellValue


def findFormatMisfit(
    cell: Cell | None, where: CellReference, cellFormat: CellFormat, value: CellValue
) -> str | None:
    """Return why a format cannot show the value a cell would hold, or None if it can.

    An empty cell takes any format, as Numbers keeps one on a cell it emptied.
    """
    shown = findFormatShown(cellFormat)
    if shown is UNDETERMINED or value is None:
        return None
    unchanged = cell is not None and isSameValue(cell.value, value)
    kind = (
        cell.kind if cell is not None and unchanged
        else findCellKind(value, CellKind.EMPTY, None, False)
    )
    if shown.formatFamily in kindFormatFamilies.get(kind, frozenset()):
        return None
    holds = "holds" if unchanged else "would hold"
    return (
        f"{where} {holds} a {kind} value, which a {shown.formatFamily} format cannot "
        "show."
    )


def findControlRefusal(
    cell: Cell | None,
    where: CellReference,
    control: CellControl,
    cellFormat: CellFormat | UNCHANGED,
    value: CellValue,
) -> str:
    """Return why pybers refuses to give a cell a control, naming any format misfit.

    A control shows its value through a format, which must be one it uses, as
    findings-11-formats.md measures. No control can be written until its own ticket.
    """
    shown: CellFormat | UNDETERMINED | None = (
        cellFormat if cellFormat is not UNCHANGED
        else None if cell is None else cell.presentation.format
    )
    family = None if shown is None else findFormatShown(shown)
    if (family is None or family is UNDETERMINED) and value is not None:
        family = findFormatOfType(findAutomaticFormat(value).format_type)
    uses = controlFormatFamilies.get(control.controlType)
    if uses is not None and family not in (None, UNDETERMINED) and (
        family.formatFamily not in uses
    ):
        return (
            f"{where} shows its value through a {family.formatFamily} format, which a "
            f"{control.controlType} control cannot use. It uses "
            f"{', '.join(sorted(uses))}."
        )
    return f"pybers cannot yet write a {control.controlType} control at {where}."


def findFormatRefusal(
    cell: Cell | None,
    where: CellReference,
    cellFormat: CellFormat,
    value: CellValue,
    control: CellControl | None,
) -> str | None:
    """Return why pybers cannot yet give a cell a format over a value, or None.

    A chosen family is written over the entry Numbers' Automatic picks for the value,
    so only that family can be chosen until its own ticket teaches the writer more.
    """
    if cell is not None and cell.formula is not None:
        return f"{where} is backed by a formula, whose format pybers cannot yet set."
    if control is not None:
        return (
            f"{where} shows its value through a control, and pybers cannot yet set "
            "the format beneath one."
        )
    if value is None:
        return f"{where} holds no value, and pybers cannot yet format an empty cell."
    shown = None if cell is None else cell.presentation.format
    unchanged = cell is not None and isSameValue(cell.value, value)
    if isinstance(cellFormat, CellFormatAutomatic) or (
        unchanged and cellFormat == shown
    ):
        return None
    written = findFormatOfType(findAutomaticFormat(value).format_type)
    if cellFormat == written:
        return None
    return (
        f"pybers cannot yet write a {cellFormat.formatFamily} format, so {where} "
        f"can take {written.formatFamily} or automatic."
    )


__all__ = ["findControlRefusal", "findFormatMisfit", "findFormatRefusal"]

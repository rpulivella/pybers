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
from pybers.format._write import findAutomaticFormat, findFormatEntry
from pybers.format.controls import CellControl, controlFormatFamilies
from pybers.format.formats import (
    CellFormat,
    CellFormatAutomatic,
    CellFormatBoolean,
    CellFormatCurrency,
    CellFormatDateTime,
    CellFormatDuration,
    CellFormatNumber,
    CellFormatShown,
    CellFormatText,
    findFormatShown,
)
from pybers.table.cell import isSameValue
from pybers.table.kinds import CellKind, findCellKind, kindFormatFamilies

if TYPE_CHECKING:
    from pybers.table.cell import Cell, CellValue


# The formats a refusal offers instead, each family pybers can write an entry for.
writableFormats: tuple[CellFormatShown, ...] = (
    CellFormatNumber(), CellFormatCurrency(), CellFormatDateTime(),
    CellFormatDuration(), CellFormatText(),
)


def findFormatMisfit(
    cell: Cell | None, where: CellReference, cellFormat: CellFormat, value: CellValue
) -> str | None:
    """Return why a format cannot show the value a cell would hold, or None if it can.

    An empty cell takes any format, as Numbers keeps one on a cell it emptied, and so
    does a formula, whose format waits in its family's slot for a result it fits.
    """
    shown = findFormatShown(cellFormat)
    formula = cell is not None and cell.formula is not None
    if shown is UNDETERMINED or value is None or formula:
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
    """Return why pybers cannot give a cell a format, or None when it can.

    A format sits in its family's slot over whatever the cell holds, a value, an
    empty cell or a formula awaiting a result, so pybers refuses only a format beneath
    a control, one Numbers keeps no chosen form of, and one it has no entry for yet.
    """
    if control is not None:
        return (
            f"{where} shows its value through a control, and pybers cannot yet set "
            "the format beneath one."
        )
    shown = None if cell is None else cell.presentation.format
    unchanged = cell is not None and isSameValue(cell.value, value)
    if isinstance(cellFormat, CellFormatAutomatic) or (
        unchanged and cellFormat == shown
    ):
        return None
    if cell is not None and cell.formula is not None and cellFormat == CellFormatText():
        return (
            f"{where} is backed by a formula, and Numbers keeps no chosen text format "
            "on one, so it can take automatic."
        )
    if cellFormat == CellFormatBoolean():
        return (
            f"Numbers offers no boolean format to choose, so {where} can take a "
            "checkbox or automatic."
        )
    if findFormatEntry(cellFormat, value) is not None:
        return None
    writable = [
        each.formatFamily.value for each in writableFormats
        if findFormatEntry(each, value) is not None
        and findFormatMisfit(cell, where, each, value) is None
    ]
    return (
        f"pybers cannot yet write a {cellFormat.formatFamily} format, so {where} can "
        f"take {', '.join([*writable, 'automatic'])}."
    )


__all__ = ["findControlRefusal", "findFormatMisfit", "findFormatRefusal"]

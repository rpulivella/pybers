#!/usr/bin/env python3
"""\
Whether a cell can take a format or a control, judged before any cell changes.

A format must show the value the cell would hold, and a control must show its value
through a format it uses, as findings-11-formats.md measures. What fits and what pybers
can write are told apart, so a caller can fall back to Automatic for the first.

Private. The format feature's checks on a write, which `Document.cellSet` makes.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
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
from pybers.errors import composeRefusal, formatChoiceList, nothingWritten
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
    return composeRefusal(
        str(where), f"{holds} a {kind} value, which a {shown.formatFamily} format "
        "cannot show", "Give a format that shows it", nothingWritten,
    )


def findControlRefusal(
    cell: Cell | None,
    where: CellReference,
    control: CellControl,
    cellFormat: CellFormat | UNCHANGED,
    value: CellValue,
) -> str:
    """Return why pybers refuses to give a cell a control, stating any format misfit.

    A control shows its value through a format, which must be one it uses, as
    findings-11-formats.md measures. Writing a control is not supported.
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
        return composeRefusal(
            str(where), f"shows its value through a {family.formatFamily} format, "
            f"which a {control.controlType} control cannot use",
            f"The formats it uses are {formatChoiceList(sorted(uses))}", nothingWritten,
        )
    return composeRefusal(
        str(where), f"would take a {control.controlType} control, and writing one is "
        "not supported", notDone=nothingWritten,
    )


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
    a control, one Numbers keeps no chosen form of, and one it has no entry for.
    """
    if control is not None:
        return composeRefusal(
            str(where), "shows its value through a control, and setting the format "
            "beneath one is not supported", notDone=nothingWritten,
        )
    shown = None if cell is None else cell.presentation.format
    unchanged = cell is not None and isSameValue(cell.value, value)
    if isinstance(cellFormat, CellFormatAutomatic) or (
        unchanged and cellFormat == shown
    ):
        return None
    if cell is not None and cell.formula is not None and cellFormat == CellFormatText():
        return composeRefusal(
            str(where), "is backed by a formula, and Numbers keeps no chosen text "
            "format on one", "Give it automatic", nothingWritten,
        )
    if cellFormat == CellFormatBoolean():
        return composeRefusal(
            str(where), "cannot take a boolean format, since Numbers offers none to "
            "choose", "Give it a checkbox or automatic", nothingWritten,
        )
    if findFormatEntry(cellFormat, value) is not None:
        return None
    writable = [
        each.formatFamily.value for each in writableFormats
        if findFormatEntry(each, value) is not None
        and findFormatMisfit(cell, where, each, value) is None
    ]
    return composeRefusal(
        str(where), f"would take a {cellFormat.formatFamily} format, and writing one "
        "is not supported",
        f"The formats it can take are {formatChoiceList([*writable, 'automatic'])}",
        nothingWritten,
    )


__all__ = ["findControlRefusal", "findFormatMisfit", "findFormatRefusal"]

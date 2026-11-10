#!/usr/bin/env python3
"""\
The format and the control a cell record shows its value with, as the model names them.

Private. Part of the format feature's archive half.

UPDATES
2026-11-09  Written for PYB-145, from the format reading in `pybers.table._read`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/09"

from .._persistence.cells import (
    CellRecord,
    carriesChosenFormat,
    chosenFormatBits,
    chosenFormatOffset,
    controlSlot,
    countedFormatSlots,
    displayedKindSlot,
    findSlotValue,
)
from .controls import CellControl
from .formats import (
    CellFormat,
    CellFormatAutomatic,
    CellFormatBoolean,
    CellFormatCheckbox,
    CellFormatCurrency,
    CellFormatDateTime,
    CellFormatDuration,
    CellFormatFraction,
    CellFormatNumber,
    CellFormatNumberCustom,
    CellFormatNumeralSystem,
    CellFormatPercent,
    CellFormatScientific,
    CellFormatShown,
    CellFormatStarRating,
    CellFormatText,
    CellFormatUnknown,
)

currencyFormatType: int = 257

# The format each measured `format_type` names, every one the documents carry.
formatsByType: frozendict[int, CellFormatShown] = frozendict({
    1: CellFormatBoolean(),
    256: CellFormatNumber(),
    257: CellFormatCurrency(),
    258: CellFormatPercent(),
    259: CellFormatScientific(),
    260: CellFormatText(),
    261: CellFormatDateTime(),
    262: CellFormatFraction(),
    263: CellFormatCheckbox(),
    267: CellFormatStarRating(),
    268: CellFormatDuration(),
    269: CellFormatNumeralSystem(),
    270: CellFormatNumberCustom(),
})


def findFormatOfType(formatType: int | None) -> CellFormatShown:
    """Return the format an entry's type names, unknown for a type not measured."""
    known = None if formatType is None else formatsByType.get(formatType)
    return CellFormatUnknown(formatType) if known is None else known


def findWaitingFormatKey(record: CellRecord) -> int | None:
    """Return the key of the one chosen format a record showing no kind holds, or None.

    A formula with no result shows no kind until Numbers calculates it, so its format
    waits in its family's slot, chosen, as findings-11-formats.md measures.
    """
    chosen = [
        key for bit, slot in zip(chosenFormatBits, countedFormatSlots, strict=True)
        if len(record.raw) > chosenFormatOffset and record.raw[chosenFormatOffset] & bit
        and (key := findSlotValue(record, slot)) is not None
    ]
    return chosen[0] if len(chosen) == 1 else None


def readWaitingFormat(
    record: CellRecord, formatTypes: dict[int, int]
) -> CellFormat | None:
    """Return the format a record showing no kind holds waiting, or None for none."""
    key = findWaitingFormatKey(record)
    return None if key is None else findFormatOfType(formatTypes.get(key))


def readRecordFormat(
    record: CellRecord, formatTypes: dict[int, int]
) -> CellFormat | None:
    """Return the format a record shows its value with, or None when it names none.

    The displayed slot holds a kind, 1 to 6, naming the per-kind slot whose key is
    the format. A kind or key this cannot follow is unknown, never a guess, and a
    format no person chose is Numbers' Automatic, holding the one it chose.
    """
    displayed = findSlotValue(record, displayedKindSlot)
    if displayed is None:
        return readWaitingFormat(record, formatTypes)
    key = (
        findSlotValue(record, countedFormatSlots[displayed - 1])
        if 1 <= displayed <= len(countedFormatSlots) else None
    )
    shown = findFormatOfType(None if key is None else formatTypes.get(key))
    return shown if carriesChosenFormat(record) else CellFormatAutomatic(shown)


def readRecordControl(
    record: CellRecord, controls: dict[int, CellControl]
) -> CellControl | None:
    """Return the control a record names, or None when it names none."""
    key = findSlotValue(record, controlSlot)
    return None if key is None else controls.get(key)


__all__ = [
    "currencyFormatType", "findFormatOfType", "findWaitingFormatKey", "formatsByType",
    "readRecordControl",
    "readRecordFormat",
]

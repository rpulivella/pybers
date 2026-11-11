#!/usr/bin/env python3
"""\
The format entry a cell record names, as the writer builds it.

Private. Part of the format feature's archive half.

UPDATES
2026-11-10  An Automatic duration records the units its value holds, not minutes
            alone, as Numbers does.
2026-11-10  Written for PYB-145, from the format entries in `pybers.table._records`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/10"

import datetime
from typing import TYPE_CHECKING

from .._generated import TSKArchives_pb2 as tsk
from .._persistence.cells import (
    checkboxFormatSlot,
    currencyFormatSlot,
    dateFormatSlot,
    durationFormatSlot,
    numberFormatSlot,
    textFormatSlot,
)
from ..currency import CurrencyAmount
from ._read import currencyFormatType, findFormatOfType
from .formats import CellFormatFamily, CellFormatShown

if TYPE_CHECKING:
    from ..table.cell import CellValue

# Numbers' Automatic format for each kind it gives one, as the documents store it:
# the number in `11-value-types-noformats` and `20-formula-shapes`, and the boolean a
# formula in `69-functions-added-in-15-4` returned. A duration's follows its value.
automaticNumberFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=256, decimal_places=253, negative_style=0,
    show_thousands_separator=False,
)
automaticTextFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=260
)
automaticBooleanFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=1
)
# A date has no Automatic, since Numbers names a pattern for every date it stores, so
# pybers writes ISO 8601 order, the same in every region. Numbers stores `yyyy-MM-dd`
# in `66-series-horizontal-base`; PYB-145 sets any other.
dateOnlyFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=261, date_time_format="yyyy-MM-dd"
)
dateAndTimeFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=261, date_time_format="yyyy-MM-dd HH:mm"
)


# As Numbers' menu writes it, in `88-formula-currency-results` and `12-number-currency`.
def buildCurrencyFormat(code: str) -> tsk.FormatStructArchive:
    """Return the Currency format Numbers gives an amount in one currency."""
    return tsk.FormatStructArchive(
        format_type=currencyFormatType, decimal_places=2, currency_code=code,
        negative_style=0,
        show_thousands_separator=False, use_accounting_style=False,
    )


# Each duration unit's bit and its length, largest first. See findings-11-formats.md.
durationUnits: tuple[tuple[int, datetime.timedelta], ...] = (
    (1, datetime.timedelta(weeks=1)), (2, datetime.timedelta(days=1)),
    (4, datetime.timedelta(hours=1)), (8, datetime.timedelta(minutes=1)),
    (16, datetime.timedelta(seconds=1)), (32, datetime.timedelta(milliseconds=1)),
)
minutesUnit: int = 8


def findDurationUnits(value: datetime.timedelta) -> tuple[int, int]:
    """Return the largest and smallest unit a duration holds an amount of, as bits.

    Numbers' Automatic units record the range it shows, measured in
    `15-number-duration-formats` and `73-values-typed-over-controls`. A duration of
    no length shows in minutes, as Numbers shows zero.
    """
    remaining, held = abs(value), []
    for bit, length in durationUnits:
        count, remaining = divmod(remaining, length)
        if count:
            held.append(bit)
    return (held[0], held[-1]) if held else (minutesUnit, minutesUnit)


def findAutomaticFormat(value: CellValue) -> tsk.FormatStructArchive:
    """Return the format a value takes in a cell whose kind it changed."""
    if isinstance(value, CurrencyAmount):
        return buildCurrencyFormat(value.currency)
    if isinstance(value, str):
        return automaticTextFormat
    if isinstance(value, bool):
        return automaticBooleanFormat
    if isinstance(value, datetime.datetime):
        return dateOnlyFormat if value.time() == datetime.time() else dateAndTimeFormat
    if isinstance(value, datetime.timedelta):
        largest, smallest = findDurationUnits(value)
        return tsk.FormatStructArchive(
            format_type=268, duration_style=1, duration_unit_largest=largest,
            duration_unit_smallest=smallest, use_automatic_duration_units=True,
        )
    return automaticNumberFormat


# The kind slot each family's format sits in, measured in findings-01-values.md.
formatSlots: frozendict[CellFormatFamily, tuple[int, int]] = frozendict({
    CellFormatFamily.NUMBER: numberFormatSlot,
    CellFormatFamily.NUMBER_CUSTOM: numberFormatSlot,
    CellFormatFamily.PERCENT: numberFormatSlot,
    CellFormatFamily.SCIENTIFIC: numberFormatSlot,
    CellFormatFamily.FRACTION: numberFormatSlot,
    CellFormatFamily.NUMERAL_SYSTEM: numberFormatSlot,
    CellFormatFamily.STAR_RATING: numberFormatSlot,
    CellFormatFamily.CURRENCY: currencyFormatSlot,
    CellFormatFamily.DATE_TIME: dateFormatSlot,
    CellFormatFamily.DURATION: durationFormatSlot,
    CellFormatFamily.TEXT: textFormatSlot,
    CellFormatFamily.CHECKBOX: checkboxFormatSlot,
    CellFormatFamily.BOOLEAN: checkboxFormatSlot,
})

# The entry each family takes over no value it could follow: an empty cell, or a
# formula whose result is absent or of another kind. Each is its Automatic entry.
plainFormatEntries: frozendict[CellFormatFamily, tsk.FormatStructArchive] = (
    frozendict({
        CellFormatFamily.NUMBER: automaticNumberFormat,
        CellFormatFamily.DATE_TIME: dateOnlyFormat,
        CellFormatFamily.DURATION: findAutomaticFormat(datetime.timedelta()),
        CellFormatFamily.TEXT: automaticTextFormat,
    })
)


def findFormatEntry(
    cellFormat: CellFormatShown, value: CellValue
) -> tsk.FormatStructArchive | None:
    """Return the entry pybers writes for a format over a value, or None for none.

    A value of the format's own family takes the entry Automatic gives it, so a
    currency names its currency and a duration its units, and any other value takes
    the family's plain entry. The one place pybers decides which formats it can write.
    """
    if value is not None:
        automatic = findAutomaticFormat(value)
        if findFormatOfType(automatic.format_type) == cellFormat:
            return automatic
    return plainFormatEntries.get(cellFormat.formatFamily)


__all__ = [
    "automaticBooleanFormat",
    "automaticNumberFormat",
    "automaticTextFormat",
    "buildCurrencyFormat",
    "dateAndTimeFormat",
    "dateOnlyFormat",
    "findAutomaticFormat",
    "findDurationUnits",
    "findFormatEntry",
    "formatSlots",
]

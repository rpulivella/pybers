#!/usr/bin/env python3
"""\
The format entry a cell record names, as the writer builds it.

Private. Part of the format feature's archive half.

UPDATES
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
from collections.abc import Callable
from typing import TYPE_CHECKING

from .._generated import TSKArchives_pb2 as tsk
from .._persistence.cells import (
    countedFormatSlots,
    decodeRecord,
    displayedKindSlot,
    findSlotValue,
)
from ..currency import CurrencyAmount
from ._read import currencyFormatType, findFormatOfType
from .formats import CellFormat, CellFormatAutomatic

if TYPE_CHECKING:
    from ..table.cell import CellValue

# Numbers' Automatic format for each kind it gives one, as the documents store it:
# the number in `11-value-types-noformats` and `20-formula-shapes`, the duration in
# `11` `D1`, and the boolean a formula in `69-functions-added-in-15-4` returned.
automaticNumberFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=256, decimal_places=253, negative_style=0,
    show_thousands_separator=False,
)
automaticTextFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=260
)
automaticDurationFormat: tsk.FormatStructArchive = tsk.FormatStructArchive(
    format_type=268, duration_style=1, duration_unit_largest=8,
    duration_unit_smallest=8, use_automatic_duration_units=True,
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
        return automaticDurationFormat
    return automaticNumberFormat


def checkAskedFormatShown(
    raw: bytes,
    asked: CellFormat,
    value: CellValue,
    formatOf: Callable[[int], tsk.FormatStructArchive | None],
) -> bool:
    """Report whether a record already names the entry a format asked for needs.

    A chosen family is the one Automatic writes for the value, so a record showing
    any other entry takes Automatic's, and the chosen bit says the rest.
    """
    record = decodeRecord(0, raw)
    displayed = findSlotValue(record, displayedKindSlot)
    key = (
        findSlotValue(record, countedFormatSlots[displayed - 1])
        if displayed is not None and 1 <= displayed <= len(countedFormatSlots)
        else None
    )
    current = None if key is None else formatOf(key)
    if isinstance(asked, CellFormatAutomatic):
        return current == findAutomaticFormat(value)
    return current is not None and findFormatOfType(current.format_type) == asked


__all__ = [
    "automaticBooleanFormat",
    "automaticDurationFormat",
    "automaticNumberFormat",
    "automaticTextFormat",
    "buildCurrencyFormat",
    "checkAskedFormatShown",
    "dateAndTimeFormat",
    "dateOnlyFormat",
    "findAutomaticFormat",
]

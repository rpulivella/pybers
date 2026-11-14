#!/usr/bin/env python3
"""What a cell's record says beyond its value: the kind it stores, and its format.

The kind follows the stored value type, never the Data Format menu, so a date is a
date whatever format shows it, and a percentage is a number. Currency is the one
format with a type of its own, because the currency code is information a number
cannot carry. See findings-01-values.md.

UPDATES
2026-11-12  A record's own cell style, for PYB-265.
2026-11-10  `kindFormatFamilies`, the families each kind of value is shown with, for
            PYB-145.
2026-11-09  A presentation's format is a `CellFormat`, its Automatic wrapping the one
            Numbers chose, replacing `formatChosen`, and the family enum moved to
            the format feature, for PYB-145.
2026-10-24  `kindValueTypes`, the type each kind's value holds, for PYB-259.
2026-10-22  `CellPresentation`, a cell's format and its control, replacing the
            description, whose kind is the cell's own, for PYB-255.
2026-10-22  A `CurrencyAmount` is the currency kind, for PYB-220.
2026-10-20  The boolean family, Numbers' Automatic format for TRUE and FALSE, for
            PYB-144.
2026-10-12  A format the save will choose is UNDETERMINED, not None, for PYB-190.
2026-10-07  An unknown kind keeps the record's own type, for PYB-169.
2026-10-01  Written for PYB-141, replacing `Cell.errored`, its chosen-format flag
            and its rich-text marker.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/01"

import datetime
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pybers.absence import UNDETERMINED
from pybers.currency import CurrencyAmount
from pybers.format.controls import CellControl
from pybers.format.formats import CellFormat, CellFormatFamily
from pybers.style.cells import CellStyle

if TYPE_CHECKING:
    from pybers.table.cell import CellValue


class CellKind(StrEnum):
    """The kind of value a cell's record stores."""

    EMPTY = "empty"
    NUMBER = "number"
    CURRENCY = "currency"
    TEXT = "text"
    RICH_TEXT = "rich-text"
    DATE_TIME = "date-time"
    DURATION = "duration"
    BOOLEAN = "boolean"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CellPresentation:
    """How a cell shows its value: its format and its control.

    `format` is None when the record names none, and UNDETERMINED once an edit
    changed the kind or dropped the control, since the save then chooses it. A
    control is kept only while it can show the cell's value, as the save keeps it.
    """

    format: CellFormat | UNDETERMINED | None
    control: CellControl | None = None


@dataclass(frozen=True, slots=True)
class CellStorage:
    """What a cell's record stores beside its value, as read, copied or saved.

    A failed formula is the `ERROR` kind, and an `UNKNOWN` kind keeps the record's
    own type in `unrecognizedTypeCode`.
    """

    kind: CellKind
    presentation: CellPresentation
    unrecognizedTypeCode: int | None = None
    cellStyle: CellStyle | None = None


emptyStorage: CellStorage = CellStorage(CellKind.EMPTY, CellPresentation(None))


def findCellKind(
    value: CellValue, stored: CellKind, storedValue: CellValue, formulaPending: bool
) -> CellKind:
    """Return the kind a cell's value is stored as, following any edit to it.

    The stored kind holds while the value is the one stored, which is how rich text
    stays rich and an error stays an error. A number written over currency stays
    currency, because the writer keeps the record's type. A formula given a cell
    with no record is saved as type 8, the uncalculated state, so it is an error.
    """
    if formulaPending and value is None:
        return CellKind.ERROR
    if type(value) is type(storedValue) and value == storedValue:
        return stored
    if value is None:
        return CellKind.EMPTY
    if isinstance(value, bool):
        return CellKind.BOOLEAN
    if isinstance(value, CurrencyAmount):
        return CellKind.CURRENCY
    if isinstance(value, Decimal):
        return CellKind.CURRENCY if stored is CellKind.CURRENCY else CellKind.NUMBER
    if isinstance(value, str):
        return CellKind.TEXT
    if isinstance(value, datetime.datetime):
        return CellKind.DATE_TIME
    if isinstance(value, datetime.timedelta):
        return CellKind.DURATION
    return CellKind.UNKNOWN


# The type a value of each kind holds, the inverse of `findCellKind`. Measured across
# every document in the tests on 2026-10-24: an error, an empty and an unknown cell
# hold None, and each other kind one type.
kindValueTypes: frozendict[CellKind, type] = frozendict({
    CellKind.EMPTY: type(None),
    CellKind.NUMBER: Decimal,
    CellKind.CURRENCY: CurrencyAmount,
    CellKind.TEXT: str,
    CellKind.RICH_TEXT: str,
    CellKind.DATE_TIME: datetime.datetime,
    CellKind.DURATION: datetime.timedelta,
    CellKind.BOOLEAN: bool,
    CellKind.ERROR: type(None),
    CellKind.UNKNOWN: type(None),
})


# The format families Numbers shows each kind of value with, measured across the 190
# documents in the tests on 2026-11-10. A custom format reads as unknown until its
# family is decoded, so it is not listed.
kindFormatFamilies: frozendict[CellKind, frozenset[CellFormatFamily]] = frozendict({
    CellKind.NUMBER: frozenset({
        CellFormatFamily.NUMBER, CellFormatFamily.PERCENT, CellFormatFamily.SCIENTIFIC,
        CellFormatFamily.FRACTION, CellFormatFamily.NUMERAL_SYSTEM,
        CellFormatFamily.NUMBER_CUSTOM, CellFormatFamily.STAR_RATING,
    }),
    CellKind.CURRENCY: frozenset({CellFormatFamily.CURRENCY}),
    CellKind.DATE_TIME: frozenset({CellFormatFamily.DATE_TIME}),
    CellKind.DURATION: frozenset({CellFormatFamily.DURATION}),
    CellKind.BOOLEAN: frozenset({CellFormatFamily.BOOLEAN, CellFormatFamily.CHECKBOX}),
    CellKind.TEXT: frozenset({CellFormatFamily.TEXT}),
    CellKind.RICH_TEXT: frozenset({CellFormatFamily.TEXT}),
})


__all__ = [
    "CellKind",
    "CellPresentation",
    "CellStorage",
    "emptyStorage",
    "findCellKind",
    "kindFormatFamilies",
    "kindValueTypes",
]

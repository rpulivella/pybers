#!/usr/bin/env python3
"""What a cell's record says beyond its value: the kind it stores, and its format.

The kind follows the stored value type, never the Data Format menu, so a date is a
date whatever format shows it, and a percentage is a number. Currency is the one
format with a type of its own, because the currency code is information a number
cannot carry. See findings-01-values.md.

UPDATES
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

if TYPE_CHECKING:
    from pybers.table.cells import CellValue


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


class CellFormat(StrEnum):
    """The family of the format a cell displays its value with."""

    NUMBER = "number"
    CURRENCY = "currency"
    PERCENT = "percent"
    SCIENTIFIC = "scientific"
    FRACTION = "fraction"
    NUMERAL_SYSTEM = "numeral-system"
    CUSTOM_NUMBER = "custom-number"
    TEXT = "text"
    DATE_TIME = "date-time"
    DURATION = "duration"
    CHECKBOX = "checkbox"
    STAR_RATING = "star-rating"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CellDescription:
    """A cell's stored kind, its format, and whether a person chose that format.

    `format` is None when the record names none, or once an edit changed the kind,
    since the save then decides it. A failed formula is the `ERROR` kind, and an
    `UNKNOWN` kind keeps the record's own type in `unrecognizedTypeCode`.
    """

    kind: CellKind
    format: CellFormat | None
    formatChosen: bool
    unrecognizedTypeCode: int | None = None


emptyDescription: CellDescription = CellDescription(CellKind.EMPTY, None, False)


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
    if isinstance(value, Decimal):
        return CellKind.CURRENCY if stored is CellKind.CURRENCY else CellKind.NUMBER
    if isinstance(value, str):
        return CellKind.TEXT
    if isinstance(value, datetime.datetime):
        return CellKind.DATE_TIME
    if isinstance(value, datetime.timedelta):
        return CellKind.DURATION
    return CellKind.UNKNOWN


__all__ = [
    "CellDescription",
    "CellFormat",
    "CellKind",
    "emptyDescription",
    "findCellKind",
]

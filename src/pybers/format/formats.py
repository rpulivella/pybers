#!/usr/bin/env python3
"""\
The format a cell shows its value with, a closed family with one member per family.

A cell's record names a format entry, and a person either chose that format or left
Numbers' Automatic to choose it. The two are independent in the file, since a chosen
format can equal the one Automatic picks, so `CellFormatAutomatic` wraps the format
Numbers chose in `shown` rather than standing in for it. See findings-11-formats.md.

UPDATES
2026-11-10  `CellFormatConflict`, what a write does with a format that does not fit.
2026-11-09  Written for PYB-145.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/09"

from abc import ABC
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, final

from pybers._family import FamilyMember, checkFamily
from pybers.absence import UNDETERMINED


class CellFormatFamily(StrEnum):
    """The family of a format, as the Data Format menu groups them."""

    AUTOMATIC = "automatic"
    NUMBER = "number"
    NUMBER_CUSTOM = "number-custom"
    BOOLEAN = "boolean"
    CURRENCY = "currency"
    PERCENT = "percent"
    SCIENTIFIC = "scientific"
    FRACTION = "fraction"
    NUMERAL_SYSTEM = "numeral-system"
    TEXT = "text"
    DATE_TIME = "date-time"
    DURATION = "duration"
    CHECKBOX = "checkbox"
    STAR_RATING = "star-rating"
    UNKNOWN = "unknown"


class CellFormatConflict(StrEnum):
    """What a write does with a format that cannot show the value a cell holds."""

    REFUSE = "refuse"
    AUTOMATIC = "automatic"


class CellFormatBase(FamilyMember, ABC):
    """A format a cell shows its value with, named by its `formatFamily`."""

    __slots__ = ()
    formatFamily: ClassVar[CellFormatFamily]


@final
@dataclass(frozen=True, slots=True)
class CellFormatNumber(CellFormatBase):
    """A number format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.NUMBER


@final
@dataclass(frozen=True, slots=True)
class CellFormatNumberCustom(CellFormatBase):
    """A custom number format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.NUMBER_CUSTOM


@final
@dataclass(frozen=True, slots=True)
class CellFormatBoolean(CellFormatBase):
    """The format Numbers gives TRUE and FALSE, which no menu offers."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.BOOLEAN


@final
@dataclass(frozen=True, slots=True)
class CellFormatCurrency(CellFormatBase):
    """A currency format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.CURRENCY


@final
@dataclass(frozen=True, slots=True)
class CellFormatPercent(CellFormatBase):
    """A percent format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.PERCENT


@final
@dataclass(frozen=True, slots=True)
class CellFormatScientific(CellFormatBase):
    """A scientific format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.SCIENTIFIC


@final
@dataclass(frozen=True, slots=True)
class CellFormatFraction(CellFormatBase):
    """A fraction format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.FRACTION


@final
@dataclass(frozen=True, slots=True)
class CellFormatNumeralSystem(CellFormatBase):
    """A numeral system format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.NUMERAL_SYSTEM


@final
@dataclass(frozen=True, slots=True)
class CellFormatText(CellFormatBase):
    """A text format, which shows every value as text."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.TEXT


@final
@dataclass(frozen=True, slots=True)
class CellFormatDateTime(CellFormatBase):
    """A date and time format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.DATE_TIME


@final
@dataclass(frozen=True, slots=True)
class CellFormatDuration(CellFormatBase):
    """A duration format."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.DURATION


@final
@dataclass(frozen=True, slots=True)
class CellFormatCheckbox(CellFormatBase):
    """A checkbox format, shown through the checkbox control."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.CHECKBOX


@final
@dataclass(frozen=True, slots=True)
class CellFormatStarRating(CellFormatBase):
    """A star rating format, shown through the star rating control."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.STAR_RATING


@final
@dataclass(frozen=True, slots=True)
class CellFormatUnknown(CellFormatBase):
    """A format pybers cannot follow, by its entry's type when the record names one."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.UNKNOWN

    formatType: int | None


type CellFormatShown = (
    CellFormatNumber | CellFormatNumberCustom | CellFormatBoolean | CellFormatCurrency
    | CellFormatPercent | CellFormatScientific | CellFormatFraction
    | CellFormatNumeralSystem | CellFormatText | CellFormatDateTime | CellFormatDuration
    | CellFormatCheckbox | CellFormatStarRating | CellFormatUnknown
)


@final
@dataclass(frozen=True, slots=True)
class CellFormatAutomatic(CellFormatBase):
    """Numbers' Automatic format and the one it chose, UNDETERMINED until saved."""

    formatFamily: ClassVar[CellFormatFamily] = CellFormatFamily.AUTOMATIC

    shown: CellFormatShown | UNDETERMINED = UNDETERMINED


type CellFormat = CellFormatShown | CellFormatAutomatic

checkFamily(CellFormatBase, CellFormat, "formatFamily")


def findFormatShown(cellFormat: CellFormat) -> CellFormatShown | UNDETERMINED:
    """Return the format a cell is shown with, the one Automatic chose included."""
    if isinstance(cellFormat, CellFormatAutomatic):
        return cellFormat.shown
    return cellFormat


__all__ = [
    "CellFormat",
    "CellFormatAutomatic",
    "CellFormatBase",
    "CellFormatBoolean",
    "CellFormatCheckbox",
    "CellFormatConflict",
    "CellFormatCurrency",
    "CellFormatDateTime",
    "CellFormatDuration",
    "CellFormatFamily",
    "CellFormatFraction",
    "CellFormatNumber",
    "CellFormatNumberCustom",
    "CellFormatNumeralSystem",
    "CellFormatPercent",
    "CellFormatScientific",
    "CellFormatShown",
    "CellFormatStarRating",
    "CellFormatText",
    "CellFormatUnknown",
    "findFormatShown",
]

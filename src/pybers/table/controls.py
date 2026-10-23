#!/usr/bin/env python3
"""\
The control a cell presents its value through, beside the format that shows it.

A slider, a stepper and a pop-up menu are controls only, so their value displays through
an ordinary format. A checkbox and a star rating are a format and a control both. See
findings-11-formats.md, "Controls are a format plus a cell spec". Numbers clamps a value
outside a range control, measured in `73-values-typed-over-controls`, while pybers never
clamps, so a control that cannot show a value is dropped by the save.

UPDATES
2026-10-22  Written for PYB-255.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, final

from pybers._family import FamilyMember, checkFamily
from pybers.currency import CurrencyAmount

if TYPE_CHECKING:
    from pybers.table.cell import CellValue

starRatingMaximum: Decimal = Decimal(5)


def findRangeAmount(value: CellValue) -> Decimal | None:
    """Return the number a range control positions, or None for any other value."""
    if isinstance(value, CurrencyAmount):
        return value.amount
    return value if isinstance(value, Decimal) else None


class CellControlBase(FamilyMember, ABC):
    """A control a cell presents its value through."""

    __slots__ = ()

    @abstractmethod
    def showsValue(self, value: CellValue) -> bool:
        """Report whether this control can show a value, so the save keeps it."""


@final
@dataclass(frozen=True, slots=True)
class CellControlCheckbox(CellControlBase):
    """A checkbox, over a true or false value."""

    def showsValue(self, value: CellValue) -> bool:
        """Report that a checkbox shows any value, as a typed value keeps it."""
        return True


@final
@dataclass(frozen=True, slots=True)
class CellControlStarRating(CellControlBase):
    """A star rating, over a number from 0 to 5."""

    def showsValue(self, value: CellValue) -> bool:
        """Report whether a number lies within the stars, or the value is not one."""
        amount = findRangeAmount(value)
        return amount is None or 0 <= amount <= starRatingMaximum


@final
@dataclass(frozen=True, slots=True)
class CellControlSlider(CellControlBase):
    """A slider, from its minimum to its maximum in steps of its increment."""

    minimum: Decimal
    maximum: Decimal
    increment: Decimal

    def showsValue(self, value: CellValue) -> bool:
        """Report whether a number lies within the range, or the value is not one."""
        amount = findRangeAmount(value)
        return amount is None or self.minimum <= amount <= self.maximum


@final
@dataclass(frozen=True, slots=True)
class CellControlStepper(CellControlBase):
    """A stepper, from its minimum to its maximum in steps of its increment."""

    minimum: Decimal
    maximum: Decimal
    increment: Decimal

    def showsValue(self, value: CellValue) -> bool:
        """Report whether a number lies within the range, or the value is not one."""
        amount = findRangeAmount(value)
        return amount is None or self.minimum <= amount <= self.maximum


@final
@dataclass(frozen=True, slots=True)
class CellControlPopUpMenu(CellControlBase):
    """A pop-up menu of text items, which starts with its first item or blank."""

    items: tuple[str, ...]
    startsWithFirstItem: bool

    def showsValue(self, value: CellValue) -> bool:
        """Report whether text is one of the items, or the value is not text."""
        return not isinstance(value, str) or value in self.items


@final
@dataclass(frozen=True, slots=True)
class CellControlUnknown(CellControlBase):
    """A control pybers has not measured, carried through by its interaction type."""

    interactionType: int

    def showsValue(self, value: CellValue) -> bool:
        """Report that an unmeasured control shows any value, so it is never dropped."""
        return True


type CellControl = (
    CellControlCheckbox | CellControlStarRating | CellControlSlider
    | CellControlStepper | CellControlPopUpMenu | CellControlUnknown
)

checkFamily(CellControlBase, CellControl)


__all__ = [
    "CellControl",
    "CellControlBase",
    "CellControlCheckbox",
    "CellControlPopUpMenu",
    "CellControlSlider",
    "CellControlStarRating",
    "CellControlStepper",
    "CellControlUnknown",
]

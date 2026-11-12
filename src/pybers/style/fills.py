#!/usr/bin/env python3
"""\
What paints an area: a `Color`, a gradient, an image, or an explicit absence of fill.

A gradient and an image read and survive a round trip, and are named by their type
alone until PYB-287 models them. `FillNone` is stored, and differs from inheriting a
fill, because a header cell cleared of its gray must say so.

UPDATES
2026-11-12  Written for PYB-265.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/12"

from abc import ABC
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, final

from pybers._family import FamilyMember, checkFamily
from pybers.color.colors import Color


class FillType(StrEnum):
    """What kind of fill a fill other than a `Color` is."""

    GRADIENT = "gradient"
    IMAGE = "image"
    NONE = "none"


class FillBase(FamilyMember, ABC):
    """A fill other than a `Color`, named by its `fillType`."""

    __slots__ = ()
    fillType: ClassVar[FillType]


@final
@dataclass(frozen=True, slots=True)
class FillGradient(FillBase):
    """A gradient fill, carried as stored."""

    fillType: ClassVar[FillType] = FillType.GRADIENT


@final
@dataclass(frozen=True, slots=True)
class FillImage(FillBase):
    """An image fill, carried as stored."""

    fillType: ClassVar[FillType] = FillType.IMAGE


@final
@dataclass(frozen=True, slots=True)
class FillNone(FillBase):
    """No fill, stated rather than inherited."""

    fillType: ClassVar[FillType] = FillType.NONE


type FillOther = FillGradient | FillImage | FillNone
type Fill = Color | FillOther

checkFamily(FillBase, FillOther, "fillType")

__all__ = [
    "Fill", "FillBase", "FillGradient", "FillImage", "FillNone", "FillOther",
    "FillType",
]

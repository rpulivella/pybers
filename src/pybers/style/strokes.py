#!/usr/bin/env python3
"""\
A line: its width in points, its color, its pattern, cap, join and miter limit.

One value serves a cell's border, a table's gridline and outline, and later a shape's
border and a text outline, since Numbers stores each as the same `TSD.StrokeArchive`.
A dash is a list of lengths in multiples of the width, as `43-stroke-dashes` and
`100b-lines` measured. See findings-04-text.md and findings-06-styles.md.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-17  Written for PYB-266.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/17"

import math
from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar, final

from pybers._family import FamilyMember, checkFamily
from pybers.color.colors import (
    Color,
    ColorError,
    findNearestFloat32,
    findShortestDecimal,
)
from pybers.errors import PybersError, composeRefusal

# The six lengths `TSD.StrokePatternArchive` holds, of which `count` are live.
strokeDashSlots: int = 6


class StrokeError(PybersError, ValueError):
    """A stroke Numbers cannot store, stating why."""


def readStrokeNumber(name: str, number: object) -> Decimal:
    """Return a number as the Decimal specifying the float32 a stroke stores."""
    if isinstance(number, bool) or not isinstance(number, int | float | Decimal):
        raise StrokeError(
            composeRefusal(f"The stroke {name} {number!r}", "is not a number")
        )
    if not math.isfinite(number):
        raise StrokeError(
            composeRefusal(f"The stroke {name} {number}", "is not finite")
        )
    try:
        return findShortestDecimal(findNearestFloat32(float(number)))
    except ColorError as exc:
        raise StrokeError(composeRefusal(
            f"The stroke {name} {number}", "is too large for Numbers to store"
        )) from exc


class StrokeCap(StrEnum):
    """How a line ends, named as SVG's `stroke-linecap` names it."""

    BUTT = "butt"
    ROUND = "round"
    SQUARE = "square"


class StrokeJoin(StrEnum):
    """How a line turns a corner, named as SVG's `stroke-linejoin` names it."""

    MITER = "miter"
    ROUND = "round"
    BEVEL = "bevel"


class StrokePatternType(StrEnum):
    """What kind of pattern a stroke draws."""

    SOLID = "solid"
    DASH = "dash"
    EMPTY = "empty"
    BRUSH = "brush"
    FRAME = "frame"
    PATTERNED = "patterned"


class StrokePatternBase(FamilyMember, ABC):
    """How a stroke lays its color along its line, identified by its `patternType`."""

    __slots__ = ()
    patternType: ClassVar[StrokePatternType]


@final
@dataclass(frozen=True, slots=True)
class StrokeSolid(StrokePatternBase):
    """An unbroken line."""

    patternType: ClassVar[StrokePatternType] = StrokePatternType.SOLID


@final
@dataclass(frozen=True, slots=True)
class StrokeDash(StrokePatternBase):
    """Dashes and gaps in turn, each length a multiple of the stroke's width.

    A dot is a dash of 0.001 with a round cap, as Numbers draws one.
    """

    patternType: ClassVar[StrokePatternType] = StrokePatternType.DASH
    lengths: tuple[Decimal, ...]
    phase: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if not 1 <= len(self.lengths) <= strokeDashSlots:
            raise StrokeError(composeRefusal(
                f"A dash of {len(self.lengths)} lengths", "is not supported, since "
                f"Numbers stores from 1 to {strokeDashSlots}",
            ))
        lengths = tuple(
            readStrokeNumber("dash length", each) for each in self.lengths
        )
        if any(each < 0 for each in lengths):
            raise StrokeError(composeRefusal(
                f"The dash lengths {', '.join(map(str, lengths))}",
                "hold a negative length, and a length is 0 or more",
            ))
        object.__setattr__(self, "lengths", lengths)
        object.__setattr__(self, "phase", readStrokeNumber("dash phase", self.phase))


@final
@dataclass(frozen=True, slots=True)
class StrokeEmpty(StrokePatternBase):
    """No line, stated, which hides any other line drawn at the same place."""

    patternType: ClassVar[StrokePatternType] = StrokePatternType.EMPTY


@final
@dataclass(frozen=True, slots=True)
class StrokeBrush(StrokePatternBase):
    """A brush stroke Numbers draws by name, randomized by its seed.

    Its stored pattern is solid, so the brush is checked before the pattern is
    believed. `seed` is None where none is stored, as in every brush measured.
    """

    patternType: ClassVar[StrokePatternType] = StrokePatternType.BRUSH
    name: str
    seed: int | None = None


@final
@dataclass(frozen=True, slots=True)
class StrokeFrame(StrokePatternBase):
    """A picture frame, carried as stored."""

    patternType: ClassVar[StrokePatternType] = StrokePatternType.FRAME


@final
@dataclass(frozen=True, slots=True)
class StrokePatterned(StrokePatternBase):
    """A patterned stroke, carried as stored."""

    patternType: ClassVar[StrokePatternType] = StrokePatternType.PATTERNED


type StrokePattern = (
    StrokeSolid | StrokeDash | StrokeEmpty | StrokeBrush | StrokeFrame
    | StrokePatterned
)

checkFamily(StrokePatternBase, StrokePattern, "patternType")


@dataclass(frozen=True, slots=True)
class Stroke:
    """A line, its width in points and its color never assumed opaque."""

    width: Decimal
    color: Color
    pattern: StrokePattern
    cap: StrokeCap = StrokeCap.BUTT
    join: StrokeJoin = StrokeJoin.MITER
    miterLimit: Decimal = Decimal(4)

    def __post_init__(self) -> None:
        width = readStrokeNumber("width", self.width)
        if width < 0:
            raise StrokeError(composeRefusal(
                f"A stroke width of {width}", "is negative, and a width is 0 or more"
            ))
        if not isinstance(self.color, Color):
            raise StrokeError(composeRefusal(
                f"The stroke color {type(self.color).__name__}", "is not a Color"
            ))
        if not isinstance(self.pattern, StrokePatternBase):
            raise StrokeError(composeRefusal(
                f"The stroke pattern {type(self.pattern).__name__}",
                "is not a StrokePattern",
            ))
        for name, kind in (("cap", StrokeCap), ("join", StrokeJoin)):
            if not isinstance(getattr(self, name), kind):
                choices = ", ".join(each.value for each in kind)
                raise StrokeError(composeRefusal(
                    f"The stroke {name} {getattr(self, name)!r}",
                    f"is not a {kind.__name__}", f"Give one of {choices}",
                ))
        object.__setattr__(self, "width", width)
        object.__setattr__(
            self, "miterLimit", readStrokeNumber("miter limit", self.miterLimit)
        )


# A line style's name, and the pattern, cap and join Numbers stores for it.
type StrokePresets = frozendict[str, tuple[StrokePattern, StrokeCap, StrokeJoin]]

# The cell Border Styles menu's lines, as Numbers 15.4 stores them in `100b-lines`.
cellStrokePresets: StrokePresets = frozendict({
    "solid": (StrokeSolid(), StrokeCap.BUTT, StrokeJoin.MITER),
    "dashed": (
        StrokeDash(lengths=(Decimal(2), Decimal(2))), StrokeCap.BUTT, StrokeJoin.MITER,
    ),
    "dotted": (
        StrokeDash(lengths=(Decimal("0.001"), Decimal(2))), StrokeCap.ROUND,
        StrokeJoin.ROUND,
    ),
})


def formatStrokePattern(stroke: Stroke, presets: StrokePresets) -> str:
    """Return a stroke's line as a preset names it, or as its pattern, cap and join."""
    for name, (pattern, cap, join) in presets.items():
        if (stroke.pattern, stroke.cap, stroke.join) == (pattern, cap, join):
            return name
    match stroke.pattern:
        case StrokeEmpty():
            return "hidden"
        case StrokeDash(lengths=lengths, phase=phase):
            shown = " ".join(map(str, lengths))
            word = f"dash({shown})" if phase == 0 else f"dash({shown} / {phase})"
        case StrokeBrush(name=name):
            word = f"brush({name})"
        case other:
            word = other.patternType.value
    return f"{word} cap({stroke.cap}) join({stroke.join})"


def formatStroke(stroke: Stroke, presets: StrokePresets = cellStrokePresets) -> str:
    """Return a stroke as CSS writes a border, `1pt dashed #000000ff`.

    A hidden stroke draws nothing, so it is `hidden` alone.
    """
    if isinstance(stroke.pattern, StrokeEmpty):
        return "hidden"
    return f"{stroke.width}pt {formatStrokePattern(stroke, presets)} {stroke.color}"


__all__ = [
    "StrokePresets", "cellStrokePresets", "formatStroke", "formatStrokePattern",
    "Stroke", "StrokeBrush", "StrokeCap", "StrokeDash", "StrokeEmpty", "StrokeError",
    "StrokeFrame", "StrokeJoin", "StrokePattern", "StrokePatternBase",
    "StrokePatternType", "StrokePatterned", "StrokeSolid", "readStrokeNumber",
    "strokeDashSlots",
]

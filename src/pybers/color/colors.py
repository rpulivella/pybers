#!/usr/bin/env python3
"""\
A color as Numbers stores it: its color space, its components, alpha and headroom.

Nothing here converts a color. A component is the float32 the file holds, kept as the
shortest Decimal that reads back to it, so `0.1` stays `0.1`, and the text form is CSS
syntax that specifies the same numbers. Numbers stores RGB alone, whichever slider
chose the color, so a stored CMYK or grayscale color reads and survives but pybers
creates none in a document. See findings-06-styles.md and `docs/decisions.md`.

UPDATES
2026-11-06  Written for PYB-264.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/06"

import math
import re
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import cache
from typing import ClassVar

from pybers.errors import PybersError

# The fewest significant digits that always read back to the same float32.
float32Digits: int = 9
hexChannelMaximum: int = 255

numberPattern: str = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
functionPattern: re.Pattern[str] = re.compile(r"([a-z0-9-]+)\((.*)\)", re.DOTALL)
hexPattern: re.Pattern[str] = re.compile(r"#[0-9a-f]+")

carryingForms: str = (
    "#rrggbbaa, color(srgb r g b / a), color(display-p3 r g b / a), "
    "device-cmyk(c m y k / a) or device-gray(w / a)"
)
# Each CSS function or `color()` space specifying what Numbers does not store.
unstoredModels: frozendict[str, str] = frozendict({
    "hsl": "HSL", "hsla": "HSL", "hwb": "HWB", "lab": "Lab", "lch": "LCH",
    "oklab": "OKLab", "oklch": "OKLCH", "xyz": "XYZ", "xyz-d50": "XYZ",
    "xyz-d65": "XYZ",
})
unstoredSpaces: frozenset[str] = frozenset({
    "srgb-linear", "display-p3-linear", "a98-rgb", "prophoto-rgb", "rec2020",
})


# A float loses nothing here, since a component is rounded to a float32 either way.
type ColorNumber = Decimal | float | int


class ColorError(PybersError, ValueError):
    """A color Numbers cannot store, or text that is not one, naming why."""


class ColorSpace(StrEnum):
    """What a color's components are measured in, which also decides how many it has."""

    SRGB = "srgb"
    DISPLAY_P3 = "display-p3"
    DEVICE_CMYK = "device-cmyk"
    DEVICE_GRAY = "device-gray"


componentCounts: frozendict[ColorSpace, int] = frozendict({
    ColorSpace.SRGB: 3, ColorSpace.DISPLAY_P3: 3,
    ColorSpace.DEVICE_CMYK: 4, ColorSpace.DEVICE_GRAY: 1,
})
rgbSpaces: frozendict[str, ColorSpace] = frozendict({
    "srgb": ColorSpace.SRGB, "display-p3": ColorSpace.DISPLAY_P3,
})


def findNearestFloat32(number: float) -> float:
    """Return the float32 nearest a number, as the float that represents it exactly."""
    try:
        packed = struct.pack("<f", number)
    except OverflowError as exc:
        raise ColorError(
            f"{number} is too large for the float32 a color stores."
        ) from exc
    rounded: float = struct.unpack("<f", packed)[0]
    return rounded


def findShortestDecimal(number: float) -> Decimal:
    """Return the shortest Decimal reading back to a float32, `0.1` for 0.1f."""
    for digits in range(1, float32Digits + 1):
        shown = f"{number:.{digits}g}"
        if findNearestFloat32(float(shown)) == number:
            break
    return Decimal(format(Decimal(shown), "f"))


@cache
def findHexChannels() -> frozendict[Decimal, int]:
    """Return each float32 a whole number of 255ths rounds to, and that whole number."""
    return frozendict({
        readChannel("component", whole / hexChannelMaximum): whole
        for whole in range(hexChannelMaximum + 1)
    })


def readChannel(name: str, number: object) -> Decimal:
    """Return one number as the Decimal specifying its float32, or refuse it."""
    if isinstance(number, bool) or not isinstance(number, int | float | Decimal):
        raise ColorError(f"A color's {name} is a number, and this one is {number!r}.")
    if isinstance(number, Decimal) and not number.is_finite():
        raise ColorError(f"A color's {name} is finite, and this one is {number}.")
    if not math.isfinite(number):
        raise ColorError(f"A color's {name} is finite, and this one is {number}.")
    return findShortestDecimal(findNearestFloat32(float(number)))


def parseNumbers(text: str, count: int, form: str) -> tuple[Decimal, ...]:
    """Return the numbers a space-separated list holds, exactly `count` of them."""
    words = text.split()
    plain = all(re.fullmatch(numberPattern, each) for each in words)
    if len(words) != count or not plain:
        raise ColorError(
            f"{form} takes {count} plain {'number' if count == 1 else 'numbers'} "
            f"here, and is given {text.strip()!r}."
        )
    return tuple(Decimal(each) for each in words)


def parseAlphaBody(
    body: str, count: int, form: str
) -> tuple[tuple[Decimal, ...], Decimal]:
    """Return a function's components and alpha, refusing a body omitting the alpha."""
    before, slash, after = body.partition("/")
    if not slash:
        raise ColorError(
            f"Every color states its alpha, and {body.strip()!r} leaves it out. "
            f"Write it as {form}."
        )
    return parseNumbers(before, count, form), parseNumbers(after, 1, form)[0]


def parseHexColor(text: str) -> Color:
    """Return the sRGB color `#rrggbbaa` specifies, refusing every shorter hex form."""
    if hexPattern.fullmatch(text) is None or len(text) != 9:
        if hexPattern.fullmatch(text) is not None and len(text) in (4, 7):
            raise ColorError(
                f"Every color states its alpha, and {text!r} leaves it out. "
                "Write it as #rrggbbaa."
            )
        raise ColorError(f"{text!r} is not a color. Write a hex color as #rrggbbaa.")
    red, green, blue, alpha = (
        int(text[start:start + 2], 16) / hexChannelMaximum for start in (1, 3, 5, 7)
    )
    return Color(ColorSpace.SRGB, (red, green, blue), alpha)


def parseFunctionColor(name: str, body: str, text: str) -> Color:
    """Return the color a CSS function specifies, refusing a model Numbers lacks."""
    match name:
        case "color":
            return parseColorFunction(body)
        case "device-cmyk":
            components, alpha = parseAlphaBody(body, 4, "device-cmyk(c m y k / a)")
            return Color(ColorSpace.DEVICE_CMYK, components, alpha)
        case "device-gray":
            components, alpha = parseAlphaBody(body, 1, "device-gray(w / a)")
            return Color.gray(components[0], alpha)
        case "rgb" | "rgba":
            raise ColorError(
                f"{text!r} is not a form pybers reads. Write an sRGB color as "
                "#rrggbbaa or color(srgb r g b / a)."
            )
    if name in unstoredModels:
        raise composeUnstoredModelRefusal(unstoredModels[name])
    raise ColorError(f"{text!r} is not a color. Write it as {carryingForms}.")


def composeUnstoredModelRefusal(model: str) -> ColorError:
    """Return the refusal of a model Numbers does not store."""
    return ColorError(
        f"Numbers stores no {model} color, and pybers converts no color. Numbers "
        "stores RGB, in sRGB or Display P3."
    )


def parseColorFunction(body: str) -> Color:
    """Return the RGB color `color(space r g b / a)` specifies, its space Numbers'."""
    spaceName, _, rest = body.strip().partition(" ")
    if spaceName in unstoredModels:
        raise composeUnstoredModelRefusal(unstoredModels[spaceName])
    if spaceName in unstoredSpaces:
        raise ColorError(
            f"Numbers stores no color in {spaceName}, and pybers converts no color. "
            "Numbers stores RGB in srgb or display-p3."
        )
    if spaceName not in rgbSpaces:
        raise ColorError(
            f"color() takes srgb or display-p3 as its space, and is given "
            f"{spaceName!r}."
        )
    form = f"color({spaceName} r g b / a)"
    components, alpha = parseAlphaBody(rest, 3, form)
    return Color(rgbSpaces[spaceName], components, alpha)


@dataclass(frozen=True, slots=True, init=False)
class Color:
    """A color in Numbers' own terms, never converted, and unequal across spaces.

    `Color(ColorSpace.SRGB, (1, 0.5, 0), 1)`, sRGB.
    `Color(ColorSpace.DISPLAY_P3, (1, 0.5, 0), 1)`, Display P3.
    `Color(ColorSpace.DEVICE_CMYK, (0, 0, 0, 1), 1)`, CMYK.
    `Color.gray(0.5, 1)`, grayscale, stored as Numbers stores it, three equal sRGB.
    `Color.black` and `Color.white`, the two tokens.
    """

    colorSpace: ColorSpace
    components: tuple[Decimal, ...]
    alpha: Decimal
    headroom: Decimal = Decimal(1)

    black: ClassVar[Color]
    white: ClassVar[Color]

    def __init__(
        self, colorSpace: ColorSpace, components: Sequence[ColorNumber],
        alpha: ColorNumber, headroom: ColorNumber = 1,
    ) -> None:
        if not isinstance(colorSpace, ColorSpace):
            raise ColorError(f"A color's space is a ColorSpace, and is {colorSpace!r}.")
        count = componentCounts[colorSpace]
        if len(components) != count:
            raise ColorError(
                f"A {colorSpace} color holds {count} components, and this one holds "
                f"{len(components)}."
            )
        alpha = readChannel("alpha", alpha)
        if not 0 <= alpha <= 1:
            raise ColorError(
                f"A color's alpha is from 0 to 1, and this one is {alpha}."
            )
        headroom = readChannel("headroom", headroom)
        if headroom <= 0:
            raise ColorError(
                f"A color's headroom is above 0, and this one is {headroom}."
            )
        held = tuple(readChannel("component", each) for each in components)
        if not all(0 <= each <= headroom for each in held):
            shown = ", ".join(map(str, held))
            raise ColorError(
                f"A color's components are from 0 to its headroom of {headroom}, and "
                f"this one holds {shown}."
            )
        object.__setattr__(self, "colorSpace", colorSpace)
        object.__setattr__(self, "components", held)
        object.__setattr__(self, "alpha", alpha)
        object.__setattr__(self, "headroom", headroom)

    @classmethod
    def gray(cls, level: ColorNumber, alpha: ColorNumber) -> Color:
        """Return a gray from one level, as the Gray Scale sliders store it.

        Numbers stores three equal sRGB components, so this is what the color holds.
        """
        return cls(ColorSpace.SRGB, (level, level, level), alpha)

    @classmethod
    def parse(cls, text: str) -> Color:
        """Return the color CSS text specifies, which always states its alpha.

        `#ff8000ff`, sRGB. `color(display-p3 1 0.5 0 / 1)`, Display P3.
        `device-cmyk(0 0 0 1 / 1)`, CMYK. `device-gray(0.5 / 1)`, grayscale, read as
        `Color.gray` reads it, so it prints as `color(srgb 0.5 0.5 0.5 / 1)`.
        `black` and `white`, the two tokens.
        """
        form = text.strip().lower()
        if form == "black":
            return cls.black
        if form == "white":
            return cls.white
        if form.startswith("#"):
            return parseHexColor(form)
        found = functionPattern.fullmatch(form)
        if found is None:
            raise ColorError(
                f"{text!r} is not a color. Write it as {carryingForms}, or name black "
                "or white."
            )
        return parseFunctionColor(found[1], found[2], text)

    def __str__(self) -> str:
        if self.headroom != 1:
            raise ColorError(
                f"This color has a headroom of {self.headroom}, and CSS "
                "has no syntax for one, so it has no text form. Its JSON form carries "
                "it."
            )
        numbers = " ".join(map(str, self.components))
        match self.colorSpace:
            case ColorSpace.DEVICE_CMYK | ColorSpace.DEVICE_GRAY:
                return f"{self.colorSpace}({numbers} / {self.alpha})"
        if self.colorSpace is ColorSpace.SRGB:
            channels = findHexChannels()
            wholes = [channels.get(each) for each in (*self.components, self.alpha)]
            if None not in wholes:
                return "#" + "".join(f"{each:02x}" for each in wholes)
        return f"color({self.colorSpace} {numbers} / {self.alpha})"


# Numbers stores black and white chosen with any slider but CMYK as these.
Color.black = Color.gray(0, 1)
Color.white = Color.gray(1, 1)


__all__ = ["Color", "ColorError", "ColorNumber", "ColorSpace"]

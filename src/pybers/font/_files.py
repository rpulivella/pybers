#!/usr/bin/env python3
"""\
The faces a font file holds, read from its own tables by fontTools on any system.

A collection holds several fonts, and a variable font offers each named instance as a
face of its own, which is how a font menu lists it. A face whose PostScript name
starts with `.` is hidden by macOS and never offered, so it is left out.

Private. The font feature's read half, reached by the catalog's extraction and by
reading a machine's fonts or a font file.

UPDATES
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

import logging
import re
import struct
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont, TTLibError

from pybers.errors import PybersError, composeRefusal, nothingRead
from pybers.font.faces import FontFace, FontSlant, FontSource

# The tag a collection opens with, rather than its suffix, which is not always kept.
collectionTag: bytes = b"ttcf"
# An instance with no PostScript name of its own records this name identifier.
noNameId: int = 0xFFFF
hiddenMarker: str = "."
# Words a face's name slants with, New Peninim's faces being Inclined.
slantWords: tuple[str, ...] = ("italic", "oblique", "inclined")
nonAlphanumeric: re.Pattern[str] = re.compile(r"[^A-Za-z0-9]")
# `OS/2.fsSelection` and `head.macStyle` bits.
italicBit: int = 1 << 0
obliqueBit: int = 1 << 9
macBoldBit: int = 1 << 0
macItalicBit: int = 1 << 1
regularWeight: int = 400
boldWeight: int = 700
# A stored weight below Thin is a legacy scale's, Skia's 5 for Regular.
weightFloor: int = 100
weightCeiling: int = 1000
# The common weight names CSS Fonts 4 maps, longest first so `semibold` beats `bold`.
weightKeywords: tuple[tuple[str, int], ...] = (
    ("extralight", 200), ("ultralight", 200), ("extrabold", 800), ("ultrabold", 800),
    ("semibold", 600), ("demibold", 600), ("hairline", 100), ("thin", 100),
    ("light", 300), ("medium", 500), ("bold", 700), ("heavy", 900), ("black", 900),
)
# The name identifier of a face's PostScript name.
postScriptNameId: int = 6
# What a font file that fontTools cannot parse raises, and nothing broader.
unreadable: tuple[type[Exception], ...] = (
    TTLibError, OSError, struct.error, KeyError, AssertionError, ValueError,
)


# A library prints nothing, so fontTools' warnings reach only a caller's own handlers.
logging.getLogger("fontTools").addHandler(logging.NullHandler())


class FontError(PybersError, ValueError):
    """A font file pybers cannot read, or a face it cannot find."""


def readFontSlant(font: TTFont, styleName: str) -> FontSlant:
    """Return a face's slant from its italic bit or its name, oblique where it says so.

    Apple's fonts set their italic bits unevenly, and this rule agrees with CoreText
    on 674 of the 676 faces macOS offered on 24 November 2026, Zapfino and Brush
    Script setting a bit CoreText ignores. `post.italicAngle` was refused, since
    a script face slopes without being italic.
    """
    words = styleName.lower()
    if "OS/2" in font:
        selection = font["OS/2"].fsSelection
        if selection & obliqueBit or "oblique" in words:
            return FontSlant.OBLIQUE
        italic = bool(selection & italicBit)
    else:
        italic = bool(font["head"].macStyle & macItalicBit)
    if italic or any(each in words for each in slantWords):
        return FontSlant.OBLIQUE if "oblique" in words else FontSlant.ITALIC
    return FontSlant.NORMAL


def readNameWeight(styleName: str) -> int:
    """Return the weight a face's name states by a CSS keyword, regular where none."""
    words = nonAlphanumeric.sub("", styleName).lower()
    return next(
        (weight for keyword, weight in weightKeywords if keyword in words),
        regularWeight,
    )


def readFontWeight(font: TTFont, styleName: str) -> int:
    """Return a face's weight, from its name where the font states none on the scale.

    A legacy face with no `OS/2` states bold in `head.macStyle`, Apple Chancery states
    a weight of 0, and Skia weighs its faces from 0 to 5.
    """
    if "OS/2" not in font:
        return boldWeight if font["head"].macStyle & macBoldBit else regularWeight
    weight = int(font["OS/2"].usWeightClass)
    return weight if weightFloor <= weight <= weightCeiling else readNameWeight(
        styleName
    )


def buildInstanceName(base: FontFace, styleName: str) -> str:
    """Return the PostScript name CoreText gives an instance that states none.

    The default face's name, `_`, then the instance's with spaces as hyphens, as
    CoreText named all 78 such instances on the Mac measured on 24 November 2026,
    `CommitMonoV143-ExtraLight_200-Italic` among them. Adobe Technical Note 5902
    names them otherwise, and CoreText is what Numbers draws through.
    """
    return f"{base.postScriptName}_{styleName.replace(' ', '-')}"


def readInstanceFaces(
    font: TTFont, base: FontFace, source: FontSource, path: Path
) -> list[FontFace]:
    """Return each named instance of a variable font as a face of its own."""
    names = font["name"]
    axes = {axis.axisTag: axis for axis in font["fvar"].axes}
    defaults = {tag: axis.defaultValue for tag, axis in axes.items()}
    # Skia's axis runs from 0.48 to 3.2, a scale older than OpenType's.
    onScale = "wght" in axes and axes["wght"].maxValue >= weightFloor
    faces: list[FontFace] = []
    for instance in font["fvar"].instances:
        styleName = names.getDebugName(instance.subfamilyNameID) or base.name
        coordinates = instance.coordinates
        if instance.postscriptNameID != noNameId:
            postScriptName = names.getDebugName(instance.postscriptNameID)
        elif coordinates == defaults:
            # CoreText offers an instance at the default as the default face itself.
            continue
        else:
            postScriptName = buildInstanceName(base, styleName)
        weight = coordinates.get("wght")
        if weight is None:
            weight = base.weight
        elif not onScale:
            weight = readNameWeight(styleName)
        slant = base.slant
        if coordinates.get("ital", 0) >= 1:
            slant = FontSlant.ITALIC
        elif coordinates.get("slnt", 0) != 0:
            slant = FontSlant.OBLIQUE
        faces.append(FontFace(
            fontFamily=base.fontFamily, name=styleName,
            postScriptName=postScriptName or base.postScriptName,
            weight=round(weight), slant=slant,
            source=source, file=path,
        ))
    return faces


def readFontFaces(font: TTFont, source: FontSource, path: Path) -> list[FontFace]:
    """Return one font's face, and each named instance when it is variable."""
    names = font["name"]
    postScriptName = names.getDebugName(postScriptNameId)
    fontFamily = names.getBestFamilyName()
    styleName = names.getBestSubFamilyName() or ""
    if postScriptName is None or fontFamily is None:
        return []
    base = FontFace(
        fontFamily=fontFamily, name=styleName, postScriptName=postScriptName,
        weight=readFontWeight(font, styleName),
        slant=readFontSlant(font, styleName),
        source=source, file=path,
    )
    if "fvar" not in font:
        return [base]
    return [base, *readInstanceFaces(font, base, source, path)]


def readFileFaces(path: Path, source: FontSource) -> tuple[FontFace, ...]:
    """Return every face a font file offers, each PostScript name once, in file order.

    A file that is not a font, or one fontTools cannot parse, is refused naming it.
    """
    try:
        with path.open("rb") as stream:
            isCollection = stream.read(len(collectionTag)) == collectionTag
        opened = (
            TTCollection(path, lazy=True) if isCollection else TTFont(path, lazy=True)
        )
        found: dict[str, FontFace] = {}
        with opened:
            fonts = opened.fonts if isinstance(opened, TTCollection) else [opened]
            for font in fonts:
                for face in readFontFaces(font, source, path):
                    if not any(
                        each.startswith(hiddenMarker)
                        for each in (face.postScriptName, face.fontFamily)
                    ):
                        found.setdefault(face.postScriptName, face)
    except unreadable as exc:
        raise FontError(composeRefusal(
            str(path), f"is not a font pybers can read: {exc}",
            "Give an .otf, .ttf or .ttc file", nothingRead,
        )) from exc
    return tuple(found.values())


__all__ = ["FontError", "readFileFaces"]

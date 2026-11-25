#!/usr/bin/env python3
"""\
The typefaces pybers knows, and selecting their fonts with a document's selector.

`openTypefaces()` holds the catalog pybers ships and the fonts the machine offers, and
`openTypefaces(path)` one font file's fonts. A font both know reports the catalog, so
`[source=catalog]` selects every font a Mac on the catalog's macOS carries. A
typefaces selector has two positions, typeface and font, read by the one parser and
resolver a document's selector is, every name compared loosely, so `AvenirNext`
selects Avenir Next.

UPDATES
2026-11-24  `openTypefaces` reports its progress, and each font file it cannot read
            is a `PartSkip`, for PYB-319.
2026-11-24  A typeface is the design and a font one weight and slant of it, and a
            refusal says what is wrong in pybers' words alone, for PYB-318.
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

import difflib
import functools
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import overload

from pybers.addressing.text import quoteReferenceText
from pybers.errors import composeRefusal, formatChoiceList, nothingRead
from pybers.selection.resolver import (
    listPresent,
    matchConditions,
    matchName,
    normalizeName,
    placeComponents,
    refuseExactMiss,
)
from pybers.selection.scheme import (
    SelectorAttributeField,
    SelectorNameMatch,
    SelectorScheme,
)
from pybers.selection.selector import SelectorLike, toSelector
from pybers.status import (
    PartSkip,
    ProgressListener,
    composeProgressCount,
    composeProgressStep,
    dropProgress,
)
from pybers.typeface._files import TypefaceError, readFileFonts, unreadableCause
from pybers.typeface._machine import findMachineFontFiles
from pybers.typeface.fonts import TypefaceFont, TypefaceSlant, TypefaceSource

# A font's weight when none is given, and the range CSS `font-weight` takes.
regularWeight: int = 400
weightRange: tuple[int, int] = (1, 1000)
# Where the catalog's files sit on every Mac.
systemFonts: PurePosixPath = PurePosixPath("/System/Library/Fonts")
slantOrder: tuple[TypefaceSlant, ...] = tuple(TypefaceSlant)

typefaceScheme: SelectorScheme[TypefaceFont] = SelectorScheme(
    positions=("typeface", "font"),
    attributes=frozendict(
        weight=SelectorAttributeField(
            lambda font: font.weight, parse=int, ordered=True,
            takes="a whole number from 1 to 1000",
        ),
        slant=SelectorAttributeField(
            lambda font: font.slant.value, tuple(each.value for each in TypefaceSlant)
        ),
        source=SelectorAttributeField(
            lambda font: font.source.value, tuple(each.value for each in TypefaceSource)
        ),
        postscript=SelectorAttributeField(
            lambda font: font.postScriptName, parse=str, text=True
        ),
    ),
    pseudoClasses=frozendict(),
    nameMatch=SelectorNameMatch.LOOSE,
    groupExample="Avenir Next::Demi Bold",
    conditionExamples=("[weight>=600]",),
    exclusionExample="Avenir*:not(Avenir Next Condensed)",
)


@functools.cache
def readCatalogFonts() -> tuple[TypefaceFont, ...]:
    """Return every font macOS installs, from the catalog pybers ships, read once."""
    from pybers._generated.typefaces import fonts

    return tuple(
        TypefaceFont(
            typeface=typeface, name=name, postScriptName=postScriptName,
            weight=weight, slant=TypefaceSlant(slant), source=TypefaceSource.CATALOG,
            file=systemFonts / file,
        )
        for postScriptName, typeface, name, weight, slant, file in fonts
    )


def sortFonts(fonts: Iterable[TypefaceFont]) -> tuple[TypefaceFont, ...]:
    """Return fonts by typeface, then weight, slant and PostScript name."""
    return tuple(sorted(fonts, key=lambda font: (
        font.typeface.casefold(), font.weight, slantOrder.index(font.slant),
        font.postScriptName,
    )))


def findWeightRefusal(weight: object) -> str | None:
    """Return why a weight is not one CSS takes, or None when it is."""
    if isinstance(weight, bool) or not isinstance(weight, int) or not (
        weightRange[0] <= weight <= weightRange[1]
    ):
        return composeRefusal(
            f"The weight {weight!r}", "is not a whole number from 1 to 1000",
            "Give one such as 400 or 700",
        )
    return None


def findSlantRefusal(slant: object) -> str | None:
    """Return why a slant is not a `TypefaceSlant`, or None when it is."""
    if isinstance(slant, TypefaceSlant):
        return None
    choices = formatChoiceList([f"TypefaceSlant.{each.name}" for each in TypefaceSlant])
    return composeRefusal(
        f"The slant {slant!r}", "is not a TypefaceSlant", f"Give one of {choices}"
    )


def matchNoPseudoClass(name: str, argument: str | None) -> bool:
    """Refuse a pseudo-class, since the typefaces' scheme admits none."""
    raise AssertionError(f"The parser admitted a pseudo-class for a font, {name!r}.")


def normalizeTypefaceName(name: str) -> str:
    """Return a typeface's or a font's name as a selector compares it, `avenirnext`."""
    return normalizeName(name, SelectorNameMatch.LOOSE).casefold()


def findClosestName(written: str, names: Iterable[str]) -> str | None:
    """Return the part of a refusal stating the closest name, or None when none is."""
    loose = {normalizeTypefaceName(each): each for each in names}
    wanted = normalizeTypefaceName(written)
    closest = difflib.get_close_matches(wanted, list(loose), n=1)
    return None if not closest else (
        f"The closest is {quoteReferenceText(loose[closest[0]])}"
    )


@dataclass(frozen=True, slots=True)
class Typefaces:
    """The fonts pybers knows, each PostScript name once, and each file it skipped."""

    fonts: tuple[TypefaceFont, ...]
    skipped: tuple[PartSkip, ...] = ()

    def select(self, selector: SelectorLike) -> tuple[TypefaceFont, ...]:
        """Return every font a selector matches, as `document.select` does."""
        found = toSelector(selector, typefaceScheme)
        match = typefaceScheme.nameMatch
        typefaceNames = list(dict.fromkeys(font.typeface for font in self.fonts))
        matches: dict[str, TypefaceFont] = {}
        for group in found.groups:
            placed, _ = placeComponents(group, typefaceScheme.positions, 2, "typeface")
            typefaceComponent, fontComponent = placed
            selected = [
                each for each in typefaceNames
                if matchName(typefaceComponent, each, match)
            ]
            if not selected:
                assert typefaceComponent is not None
                refuseExactMiss(
                    typefaceComponent, "typeface", "the typefaces pybers knows",
                    findClosestName(typefaceComponent.pattern, typefaceNames),
                )
            inTypefaces = [font for font in self.fonts if font.typeface in selected]
            fonts = [
                font for font in inTypefaces
                if matchName(fontComponent, font.name, match)
            ]
            if selected and not fonts:
                within = (
                    quoteReferenceText(selected[0]) if len(selected) == 1
                    else "the typefaces selected"
                )
                refuseExactMiss(
                    fontComponent, "font", within,
                    listPresent("font", [font.name for font in inTypefaces]),
                )
            for font in fonts:
                if matchConditions(
                    group.conditions, typefaceScheme, font, matchNoPseudoClass
                ):
                    matches.setdefault(font.postScriptName, font)
        return tuple(matches.values())

    @overload
    def font(
        self, typeface: str, weight: int = ..., slant: TypefaceSlant = ...
    ) -> TypefaceFont: ...

    @overload
    def font(self, *, postScriptName: str) -> TypefaceFont | None: ...

    def font(
        self, typeface: str | None = None, weight: int = regularWeight,
        slant: TypefaceSlant = TypefaceSlant.NORMAL, *,
        postScriptName: str | None = None,
    ) -> TypefaceFont | None:
        """Return the font a typeface, weight and slant specify, or a name finds.

        A font the typeface lacks is refused, listing those it has, so no bold or italic
        is ever faked. A PostScript name pybers does not know finds None.
        """
        if (typeface is None) == (postScriptName is None):
            given = "neither" if typeface is None else "both"
            raise TypefaceError(composeRefusal(
                "A font", f"is asked for by {given} a typeface "
                f"{'nor' if typeface is None else 'and'} a PostScript name",
                "Give one of them",
            ))
        if postScriptName is not None:
            wanted = normalizeTypefaceName(postScriptName)
            return next((
                each for each in self.fonts
                if normalizeTypefaceName(each.postScriptName) == wanted
            ), None)
        assert typeface is not None
        refusal = findWeightRefusal(weight) or findSlantRefusal(slant)
        if refusal is not None:
            raise TypefaceError(refusal)
        wanted = normalizeTypefaceName(typeface)
        inTypeface = [
            each for each in self.fonts
            if normalizeTypefaceName(each.typeface) == wanted
        ]
        if not inTypeface:
            typefaceNames = dict.fromkeys(each.typeface for each in self.fonts)
            raise TypefaceError(composeRefusal(
                quoteReferenceText(typeface), "is not a typeface pybers knows",
                findClosestName(typeface, typefaceNames),
            ))
        quoted = quoteReferenceText(inTypeface[0].typeface)
        found = [
            each for each in inTypeface if each.weight == weight and each.slant is slant
        ]
        if not found:
            raise TypefaceError(composeRefusal(
                quoted, f"has no font of weight {weight} and {slant} slant",
                f"Its fonts are {formatFontChoices(inTypeface)}",
            ))
        if len(found) > 1:
            names = formatChoiceList([
                f"{quoteReferenceText(each.name)} ({each.postScriptName})"
                for each in found
            ])
            raise TypefaceError(composeRefusal(
                quoted, f"has {len(found)} fonts of weight {weight} and {slant} "
                f"slant, {names}", "Choose one by its PostScript name",
            ))
        return found[0]


def formatFontChoices(fonts: Iterable[TypefaceFont]) -> str:
    """Return fonts as a refusal lists them, `'Bold' (700, normal)`."""
    return formatChoiceList([
        f"{quoteReferenceText(font.name)} ({font.weight}, {font.slant})"
        for font in fonts
    ])


def openTypefaces(
    path: Path | str | None = None, *, onProgress: ProgressListener | None = None
) -> Typefaces:
    """Return the fonts pybers knows, or the fonts of the font file at `path`.

    `onProgress` hears each step, and each machine font file read, counted against
    its total.
    """
    report = onProgress or dropProgress
    if path is not None:
        file = Path(path)
        if not file.is_file():
            raise TypefaceError(composeRefusal(
                str(file), "does not exist", None, nothingRead
            ))
        report(composeProgressStep("reading the font file"))
        return Typefaces(sortFonts(readFileFonts(file, TypefaceSource.FILE)))
    report(composeProgressStep("reading the catalog"))
    fonts = {font.postScriptName: font for font in readCatalogFonts()}
    skipped: list[PartSkip] = []
    report(composeProgressStep("finding the fonts on this machine"))
    files = findMachineFontFiles()
    phrase = "reading the fonts on this machine"
    report(composeProgressCount(phrase, 0, len(files)))
    for completed, file in enumerate(files, 1):
        try:
            for font in readFileFonts(file, TypefaceSource.MACHINE):
                fonts.setdefault(font.postScriptName, font)
        except TypefaceError:
            skipped.append(PartSkip(str(file), unreadableCause))
        report(composeProgressCount(phrase, completed, len(files)))
    return Typefaces(sortFonts(fonts.values()), tuple(skipped))


__all__ = ["Typefaces", "typefaceScheme", "openTypefaces", "readCatalogFonts"]

#!/usr/bin/env python3
"""\
The faces pybers knows, and selecting them as a document's parts are selected.

`openFonts()` holds the catalog pybers ships and the fonts the machine offers, and
`openFonts(path)` one font file's faces. A face both know reports the catalog, so
`[source=catalog]` selects every face a Mac carries. A fonts selector has two
positions, font family and face, read by the one parser and resolver a document's
selector is, every name compared loosely, so `AvenirNext` selects Avenir Next.

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

import difflib
import functools
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pybers.addressing.text import quoteReferenceText
from pybers.errors import composeRefusal, nothingRead
from pybers.font._files import FontError, readFileFaces
from pybers.font._machine import findMachineFontFiles
from pybers.font.faces import FontFace, FontSlant, FontSource
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
from pybers.selection.selector import SelectorComponent, SelectorLike, toSelector

# Where the catalog's files sit on every Mac.
systemFonts: PurePosixPath = PurePosixPath("/System/Library/Fonts")
slantOrder: tuple[FontSlant, ...] = tuple(FontSlant)

fontScheme: SelectorScheme[FontFace] = SelectorScheme(
    positions=("font family", "face"),
    attributes=frozendict(
        weight=SelectorAttributeField(
            lambda face: face.weight, parse=int, ordered=True
        ),
        slant=SelectorAttributeField(
            lambda face: face.slant.value, tuple(each.value for each in FontSlant)
        ),
        source=SelectorAttributeField(
            lambda face: face.source.value, tuple(each.value for each in FontSource)
        ),
        postscript=SelectorAttributeField(
            lambda face: face.postScriptName, parse=str, text=True
        ),
    ),
    pseudoClasses=frozendict(),
    nameMatch=SelectorNameMatch.LOOSE,
    groupExample="Avenir Next::Demi Bold",
    conditionExamples=("[weight>=600]",),
    exclusionExample="Avenir*:not(Avenir Next Condensed)",
)


@functools.cache
def readCatalogFaces() -> tuple[FontFace, ...]:
    """Return every face macOS installs, from the catalog pybers ships, read once."""
    from pybers._generated.fonts import fonts

    return tuple(
        FontFace(
            fontFamily=fontFamily, name=name, postScriptName=postScriptName,
            weight=weight, slant=FontSlant(slant), source=FontSource.CATALOG,
            file=systemFonts / file,
        )
        for postScriptName, fontFamily, name, weight, slant, file in fonts
    )


def sortFaces(faces: Iterable[FontFace]) -> tuple[FontFace, ...]:
    """Return faces by font family, then weight, slant and PostScript name."""
    return tuple(sorted(faces, key=lambda face: (
        face.fontFamily.casefold(), face.weight, slantOrder.index(face.slant),
        face.postScriptName,
    )))


def matchNoPseudoClass(name: str, argument: str | None) -> bool:
    """Refuse a pseudo-class, which the fonts' scheme admits none of."""
    raise AssertionError(f"The parser admitted a pseudo-class for a font, {name!r}.")


def findClosestName(component: SelectorComponent, names: Iterable[str]) -> str:
    """Return the part of a refusal stating the closest name, compared loosely."""
    loose = {
        normalizeName(each, SelectorNameMatch.LOOSE).casefold(): each for each in names
    }
    wanted = normalizeName(component.pattern, SelectorNameMatch.LOOSE).casefold()
    closest = difflib.get_close_matches(wanted, list(loose), n=1)
    if not closest:
        return "None is close, and `pybers show fonts` lists every one"
    return f"The closest is {quoteReferenceText(loose[closest[0]])}"


@dataclass(frozen=True, slots=True)
class Fonts:
    """The faces pybers knows, each PostScript name once, and the files it could not
    read, each as the reason it gives.
    """

    faces: tuple[FontFace, ...]
    unreadable: tuple[str, ...] = ()

    def select(self, selector: SelectorLike) -> tuple[FontFace, ...]:
        """Return every face a selector matches, as `document.select` does."""
        found = toSelector(selector, fontScheme)
        match = fontScheme.nameMatch
        families = list(dict.fromkeys(face.fontFamily for face in self.faces))
        matches: dict[str, FontFace] = {}
        for group in found.groups:
            placed, _ = placeComponents(group, fontScheme.positions, 2, "font")
            familyComponent, faceComponent = placed
            selected = [
                each for each in families if matchName(familyComponent, each, match)
            ]
            if not selected:
                assert familyComponent is not None
                refuseExactMiss(
                    familyComponent, "font family", "the fonts pybers knows",
                    findClosestName(familyComponent, families),
                )
            inFamilies = [face for face in self.faces if face.fontFamily in selected]
            faces = [
                face for face in inFamilies
                if matchName(faceComponent, face.name, match)
            ]
            if selected and not faces:
                within = (
                    quoteReferenceText(selected[0]) if len(selected) == 1
                    else "the font families selected"
                )
                refuseExactMiss(
                    faceComponent, "face", within,
                    listPresent("face", [face.name for face in inFamilies]),
                )
            for face in faces:
                if matchConditions(
                    group.conditions, fontScheme, face, matchNoPseudoClass
                ):
                    matches.setdefault(face.postScriptName, face)
        return tuple(matches.values())


def openFonts(path: Path | str | None = None) -> Fonts:
    """Return the faces pybers knows, or the faces of the font file at `path`."""
    if path is not None:
        file = Path(path)
        if not file.is_file():
            raise FontError(composeRefusal(
                str(file), "does not exist", None, nothingRead
            ))
        return Fonts(sortFaces(readFileFaces(file, FontSource.FILE)))
    faces = {face.postScriptName: face for face in readCatalogFaces()}
    unreadable: list[str] = []
    for file in findMachineFontFiles():
        try:
            read = readFileFaces(file, FontSource.MACHINE)
        except FontError as exc:
            unreadable.append(str(exc))
            continue
        for face in read:
            faces.setdefault(face.postScriptName, face)
    return Fonts(sortFaces(faces.values()), tuple(unreadable))


__all__ = ["Fonts", "fontScheme", "openFonts", "readCatalogFaces"]

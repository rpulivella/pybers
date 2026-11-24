#!/usr/bin/env python3
"""\
Selecting faces with the selector a document is selected with.

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

import platform
from pathlib import Path, PurePosixPath

import pytest
from fontbuilders import buildFont, saveFont

import pybers
from pybers import FontFace, Fonts, FontSlant, FontSource
from pybers.document.sheets import SelectionError
from pybers.selection.selector import Selector, SelectorError


def buildFace(
    family: str, name: str, postScriptName: str, weight: int = 400,
    slant: FontSlant = FontSlant.NORMAL, source: FontSource = FontSource.CATALOG,
) -> FontFace:
    """Return a face as a catalog or a machine reports one."""
    return FontFace(
        family, name, postScriptName, weight, slant, source,
        PurePosixPath(f"/Fonts/{postScriptName}.otf"),
    )


fonts = Fonts((
    buildFace("Avenir Next", "Regular", "AvenirNext-Regular"),
    buildFace("Avenir Next", "Italic", "AvenirNext-Italic", slant=FontSlant.ITALIC),
    buildFace("Avenir Next", "Demi Bold", "AvenirNext-DemiBold", 600),
    buildFace("Avenir Next", "Demi Bold Italic", "AvenirNext-DemiBoldItalic", 600,
              FontSlant.ITALIC),
    buildFace("Avenir Next Condensed", "Bold", "AvenirNextCondensed-Bold", 700),
    buildFace("Brand Sans", "Black", "BrandSans-Black", 900,
              source=FontSource.MACHINE),
))


def selectNames(selector: str) -> list[str]:
    return [face.postScriptName for face in fonts.select(selector)]


def testFontFamilySelectsEveryFaceInOrder() -> None:
    assert selectNames("Avenir Next") == [
        "AvenirNext-Regular", "AvenirNext-Italic", "AvenirNext-DemiBold",
        "AvenirNext-DemiBoldItalic",
    ]


@pytest.mark.parametrize("written", ["AvenirNext", "avenir-next", "AVENIR  NEXT"])
def testFontFamilyMatchesIgnoringCaseSpacesAndHyphens(written: str) -> None:
    assert len(selectNames(written)) == 4


def testFacePositionTakesWildcards() -> None:
    assert selectNames("Avenir Next::*demi*") == [
        "AvenirNext-DemiBold", "AvenirNext-DemiBoldItalic",
    ]


def testNegationRemovesAFontFamily() -> None:
    assert selectNames("Avenir*:not(Avenir Next)") == ["AvenirNextCondensed-Bold"]


def testWeightCompares() -> None:
    assert selectNames("*[weight>=700]") == [
        "AvenirNextCondensed-Bold", "BrandSans-Black",
    ]


def testConditionsCombine() -> None:
    assert selectNames("Avenir Next[weight>=600][slant=italic]") == [
        "AvenirNext-DemiBoldItalic",
    ]


def testSourceSelectsWhereAFaceWasFound() -> None:
    assert selectNames("*[source=machine]") == ["BrandSans-Black"]


def testPostScriptNameMatchesLooselyUnlessFlaggedExact() -> None:
    assert selectNames("*[postscript=avenirnext demibold]") == ["AvenirNext-DemiBold"]
    assert selectNames('*[postscript="avenirnext-demibold" s]') == []
    assert selectNames('*[postscript="AvenirNext-DemiBold" s]') == [
        "AvenirNext-DemiBold",
    ]


def testGroupsSelectEachFaceOnce() -> None:
    assert selectNames("Brand Sans, *[weight=900], Brand*") == ["BrandSans-Black"]


def testMisspelledFontFamilyIsRefusedNamingTheClosest() -> None:
    with pytest.raises(SelectionError, match="The closest is 'Avenir Next'"):
        fonts.select("Avenir Nxt")


def testMissingFaceIsRefusedListingTheFamilysFaces() -> None:
    with pytest.raises(
        SelectionError, match="'Semibold' selects no face in 'Avenir Next'. The faces "
        "are 'Regular', 'Italic', 'Demi Bold' and 'Demi Bold Italic'",
    ):
        fonts.select("Avenir Next::Semibold")


def testPatternMatchingNothingSelectsNothing() -> None:
    assert selectNames("Garamond*") == []


@pytest.mark.parametrize(("selector", "message"), [
    ("*[slant>=italic]", "compares `[slant]` with `>=`, and it takes only `=`"),
    ("*[weight=heavy]", "gives `[weight]` `heavy`, which is not one of its values"),
    ('*[slant="italic" s]', "gives `[slant]` the `s` flag, which only a name takes"),
    ("*[kind=number]", "'[kind]' is not a selector condition"),
    ("a::b::c", "begins a third position, and a selector holds only font family "
     "and face"),
])
def testMalformedFontsSelectorIsRefused(selector: str, message: str) -> None:
    with pytest.raises(SelectorError, match=message.replace("[", r"\[")):
        fonts.select(selector)


def testDocumentSelectorIsRefusedByFonts() -> None:
    with pytest.raises(SelectorError, match="was parsed to select sheet, table"):
        fonts.select(Selector.parse("Q3"))


def testFontFileOffersItsOwnFaces(tmp_path: Path) -> None:
    path = saveFont(buildFont("Brand Sans", "Bold", "BrandSans-Bold", 700),
                    tmp_path / "brand.ttf")
    found = pybers.openFonts(path)
    assert [(each.postScriptName, each.source) for each in found.faces] == [
        ("BrandSans-Bold", FontSource.FILE),
    ]


def testMissingFontFileIsRefused(tmp_path: Path) -> None:
    with pytest.raises(pybers.FontError, match="absent.otf does not exist"):
        pybers.openFonts(tmp_path / "absent.otf")


@pytest.mark.skipif(not platform.mac_ver()[0], reason="the catalog is a Mac's")
def testFaceBothKnowReportsTheCatalog() -> None:
    found = pybers.openFonts().select('*[postscript="Helvetica-Bold" s]')
    assert [each.source for each in found] == [FontSource.CATALOG]


def testFamilyWeightAndSlantFindOneFace() -> None:
    face = fonts.face("avenir-next", weight=600, slant=FontSlant.ITALIC)
    assert face.postScriptName == "AvenirNext-DemiBoldItalic"


def testFaceDefaultsToRegularUpright() -> None:
    assert fonts.face("Avenir Next").postScriptName == "AvenirNext-Regular"


def testWeightTheFamilyLacksIsRefusedListingItsFaces() -> None:
    with pytest.raises(pybers.FontError, match=(
        r"'Avenir Next' has no face of weight 700 and normal slant. Its faces are "
        r"'Regular' \(400, normal\), 'Italic' \(400, italic\)"
    )):
        fonts.face("Avenir Next", weight=700)


def testSeveralFacesOfOneDesignAreRefusedNamingEach() -> None:
    twins = Fonts((
        buildFace("Jenson", "Regular", "Jenson-Regular"),
        buildFace("Jenson", "Caption", "Jenson-Caption"),
    ))
    with pytest.raises(pybers.FontError, match=(
        r"has 2 faces of weight 400 and normal slant, 'Regular' \(Jenson-Regular\) "
        r"and 'Caption' \(Jenson-Caption\). Choose one by its PostScript name"
    )):
        twins.face("Jenson")


def testUnknownFamilyIsRefusedNamingTheClosest() -> None:
    with pytest.raises(pybers.FontError, match="The closest is 'Avenir Next'"):
        fonts.face("Avenir Nxt")


@pytest.mark.parametrize("weight", [0, 1001, True, "600"])
def testWeightOffTheCssScaleIsRefused(weight: object) -> None:
    with pytest.raises(pybers.FontError, match="is not a whole number from 1 to 1000"):
        fonts.face("Avenir Next", weight=weight)  # type: ignore[call-overload]


def testSlantThatIsNotAFontSlantIsRefused() -> None:
    with pytest.raises(pybers.FontError, match="'italic' is not a FontSlant"):
        fonts.face("Avenir Next", slant="italic")  # type: ignore[call-overload]


def testPostScriptNameFindsTheFaceLoosely() -> None:
    face = fonts.face(postScriptName="avenirnext demibold")
    assert face is not None and face.postScriptName == "AvenirNext-DemiBold"


def testPostScriptNameNobodyKnowsFindsNone() -> None:
    assert fonts.face(postScriptName="BrandSerif-Semibold") is None


@pytest.mark.parametrize("arguments", [{}, {"fontFamily": "Avenir Next",
                                          "postScriptName": "AvenirNext-Regular"}])
def testFaceTakesAFamilyOrANameNeverBothOrNeither(arguments: dict[str, str]) -> None:
    with pytest.raises(pybers.FontError, match="Give one of them"):
        fonts.face(**arguments)  # type: ignore[call-overload]

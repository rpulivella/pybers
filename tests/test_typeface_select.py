#!/usr/bin/env python3
"""\
Selecting fonts with the selector a document is selected with.

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
from pybers import TypefaceFont, Typefaces, TypefaceSlant, TypefaceSource
from pybers.document.sheets import SelectionError
from pybers.selection.selector import Selector, SelectorError


def buildCatalogFont(
    family: str, name: str, postScriptName: str, weight: int = 400,
    slant: TypefaceSlant = TypefaceSlant.NORMAL,
    source: TypefaceSource = TypefaceSource.CATALOG,
) -> TypefaceFont:
    """Return a font as a catalog or a machine reports one."""
    return TypefaceFont(
        family, name, postScriptName, weight, slant, source,
        PurePosixPath(f"/Fonts/{postScriptName}.otf"),
    )


typefaces = Typefaces((
    buildCatalogFont("Avenir Next", "Regular", "AvenirNext-Regular"),
    buildCatalogFont(
        "Avenir Next", "Italic", "AvenirNext-Italic", slant=TypefaceSlant.ITALIC
    ),
    buildCatalogFont("Avenir Next", "Demi Bold", "AvenirNext-DemiBold", 600),
    buildCatalogFont(
        "Avenir Next", "Demi Bold Italic", "AvenirNext-DemiBoldItalic", 600,
        TypefaceSlant.ITALIC,
    ),
    buildCatalogFont("Avenir Next Condensed", "Bold", "AvenirNextCondensed-Bold", 700),
    buildCatalogFont("Brand Sans", "Black", "BrandSans-Black", 900,
              source=TypefaceSource.MACHINE),
))


def selectNames(selector: str) -> list[str]:
    return [font.postScriptName for font in typefaces.select(selector)]


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


def testMisspelledTypefaceIsRefusedNamingTheClosest() -> None:
    with pytest.raises(SelectionError, match="The closest is 'Avenir Next'"):
        typefaces.select("Avenir Nxt")


def testMissingFaceIsRefusedListingTheFamilysFaces() -> None:
    with pytest.raises(
        SelectionError, match="'Semibold' selects no font in 'Avenir Next'. The fonts "
        "are 'Regular', 'Italic', 'Demi Bold' and 'Demi Bold Italic'",
    ):
        typefaces.select("Avenir Next::Semibold")


def testPatternMatchingNothingSelectsNothing() -> None:
    assert selectNames("Garamond*") == []


@pytest.mark.parametrize(("selector", "message"), [
    ("*[slant>=italic]", "compares `[slant]` with `>=`, and it takes only `=`"),
    ("*[weight=heavy]", "gives `[weight]` `heavy`, which is not one of its values. "
     "Give `[weight]` a whole number from 1 to 1000"),
    ('*[slant="italic" s]', "gives `[slant]` the `s` flag, which only a name takes"),
    ("*[kind=number]", "'[kind]' is not a selector condition"),
    ("a::b::c", "begins a third position, and a selector holds only typeface "
     "and font"),
])
def testMalformedFontsSelectorIsRefused(selector: str, message: str) -> None:
    with pytest.raises(SelectorError, match=message.replace("[", r"\[")):
        typefaces.select(selector)


def testDocumentSelectorIsRefusedByTypefaces() -> None:
    with pytest.raises(SelectorError, match="was parsed to select sheet, table"):
        typefaces.select(Selector.parse("Q3"))


def testFontFileOffersItsOwnFaces(tmp_path: Path) -> None:
    path = saveFont(buildFont("Brand Sans", "Bold", "BrandSans-Bold", 700),
                    tmp_path / "brand.ttf")
    found = pybers.openTypefaces(path)
    assert [(each.postScriptName, each.source) for each in found.fonts] == [
        ("BrandSans-Bold", TypefaceSource.FILE),
    ]


def testMissingFontFileIsRefused(tmp_path: Path) -> None:
    with pytest.raises(pybers.TypefaceError, match="absent.otf does not exist"):
        pybers.openTypefaces(tmp_path / "absent.otf")


@pytest.mark.skipif(not platform.mac_ver()[0], reason="the catalog is a Mac's")
def testFaceBothKnowReportsTheCatalog() -> None:
    found = pybers.openTypefaces().select('*[postscript="Helvetica-Bold" s]')
    assert [each.source for each in found] == [TypefaceSource.CATALOG]


def testFamilyWeightAndSlantFindOneFace() -> None:
    font = typefaces.font("avenir-next", weight=600, slant=TypefaceSlant.ITALIC)
    assert font.postScriptName == "AvenirNext-DemiBoldItalic"


def testFaceDefaultsToRegularUpright() -> None:
    assert typefaces.font("Avenir Next").postScriptName == "AvenirNext-Regular"


def testWeightTheFamilyLacksIsRefusedListingItsFaces() -> None:
    with pytest.raises(pybers.TypefaceError, match=(
        r"'Avenir Next' has no font of weight 700 and normal slant. Its fonts are "
        r"'Regular' \(400, normal\), 'Italic' \(400, italic\)"
    )):
        typefaces.font("Avenir Next", weight=700)


def testSeveralFacesOfOneDesignAreRefusedNamingEach() -> None:
    twins = Typefaces((
        buildCatalogFont("Jenson", "Regular", "Jenson-Regular"),
        buildCatalogFont("Jenson", "Caption", "Jenson-Caption"),
    ))
    with pytest.raises(pybers.TypefaceError, match=(
        r"has 2 fonts of weight 400 and normal slant, 'Regular' \(Jenson-Regular\) "
        r"and 'Caption' \(Jenson-Caption\). Choose one by its PostScript name"
    )):
        twins.font("Jenson")


def testUnknownTypefaceIsRefusedNamingTheClosest() -> None:
    with pytest.raises(pybers.TypefaceError, match="The closest is 'Avenir Next'"):
        typefaces.font("Avenir Nxt")


@pytest.mark.parametrize("weight", [0, 1001, True, "600"])
def testWeightOffTheCssScaleIsRefused(weight: object) -> None:
    with pytest.raises(
        pybers.TypefaceError, match="is not a whole number from 1 to 1000"
    ):
        typefaces.font("Avenir Next", weight=weight)  # type: ignore[call-overload]


def testSlantThatIsNotAFontSlantIsRefused() -> None:
    with pytest.raises(pybers.TypefaceError, match="'italic' is not a TypefaceSlant"):
        typefaces.font("Avenir Next", slant="italic")  # type: ignore[call-overload]


def testPostScriptNameFindsTheFaceLoosely() -> None:
    font = typefaces.font(postScriptName="avenirnext demibold")
    assert font is not None and font.postScriptName == "AvenirNext-DemiBold"


def testPostScriptNameNobodyKnowsFindsNone() -> None:
    assert typefaces.font(postScriptName="BrandSerif-Semibold") is None


@pytest.mark.parametrize(("arguments", "given"), [
    ({}, "neither a typeface nor"),
    ({"typeface": "Avenir Next", "postScriptName": "AvenirNext-Regular"},
     "both a typeface and"),
])
def testFaceAskedForByNeitherOrBothSaysWhich(
    arguments: dict[str, str], given: str
) -> None:
    with pytest.raises(pybers.TypefaceError, match=(
        f"A font is asked for by {given} a PostScript name. Give one of them"
    )):
        typefaces.font(**arguments)  # type: ignore[call-overload]


@pytest.mark.parametrize("call", [
    lambda: typefaces.font("Zzqx Qqq"), lambda: typefaces.select("Zzqx Qqq"),
], ids=["font", "select"])
def testTypefaceNothingIsCloseToIsRefusedWithNoFix(call: object) -> None:
    with pytest.raises(pybers.PybersError) as refused:
        call()  # type: ignore[operator]
    assert str(refused.value).endswith("pybers knows.")


def testUnreadableMachineFontIsRecordedAndEveryOtherFaceKept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = saveFont(buildFont("Brand Sans", "Bold", "BrandSans-Bold", 700),
                    tmp_path / "brand.ttf")
    broken = tmp_path / "broken.otf"
    broken.write_text("not a font")
    monkeypatch.setattr(
        "pybers.typeface.typefaces.findMachineFontFiles", lambda: (broken, good)
    )
    found = pybers.openTypefaces()
    assert [each.postScriptName for each in found.select("Brand Sans")] == [
        "BrandSans-Bold",
    ]
    assert found.skipped == (
        pybers.PartSkip(str(broken), "is not a font file pybers can read"),
    )

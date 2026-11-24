#!/usr/bin/env python3
"""\
The fonts a font file offers, as the one font reader reads them.

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

from pathlib import Path

import pytest
from fontbuilders import (
    buildFont,
    italicSelection,
    obliqueSelection,
    saveCollection,
    saveFont,
)

from pybers.typeface._files import TypefaceError, readFileFonts
from pybers.typeface.fonts import TypefaceFont, TypefaceSlant, TypefaceSource

source = TypefaceSource.FILE


def testStaticFaceReadsItsNamesWeightAndSlant(tmp_path: Path) -> None:
    path = saveFont(
        buildFont("Brand Sans", "Semibold Italic", "BrandSans-SemiboldItalic", 600,
                  italicSelection),
        tmp_path / "brand.ttf",
    )
    assert readFileFonts(path, source) == (TypefaceFont(
        typeface="Brand Sans", name="Semibold Italic",
        postScriptName="BrandSans-SemiboldItalic", weight=600,
        slant=TypefaceSlant.ITALIC, source=source, file=path,
    ),)


def testCollectionOffersEachFaceInFileOrder(tmp_path: Path) -> None:
    path = saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Sans", "Bold", "BrandSans-Bold", 700),
    ], tmp_path / "brand.ttc")
    assert [font.postScriptName for font in readFileFonts(path, source)] == [
        "BrandSans-Regular", "BrandSans-Bold",
    ]


def testVariableFontOffersEachNamedInstance(tmp_path: Path) -> None:
    font = buildFont(
        "Brand Sans", "Regular", "BrandSans-Regular",
        axes=[("wght", 100, 400, 900, "Weight")],
        instances=[
            {"location": {"wght": 650}, "stylename": "Semibold",
             "postscriptfontname": "BrandSans-Semibold"},
            {"location": {"wght": 900}, "stylename": "Extra Black"},
            {"location": {"wght": 400}, "stylename": "Regular"},
        ],
    )
    fonts = readFileFonts(saveFont(font, tmp_path / "brand.ttf"), source)
    assert [(font.postScriptName, font.weight) for font in fonts] == [
        ("BrandSans-Regular", 400), ("BrandSans-Semibold", 650),
        ("BrandSans-Regular_Extra-Black", 900),
    ]


def testInstanceOnALegacyAxisTakesItsWeightFromItsName(
    tmp_path: Path,
) -> None:
    font = buildFont(
        "Old Sans", "Regular", "OldSans-Regular", 400,
        axes=[("wght", 0.5, 1, 3.2, "Weight")],
        instances=[{"location": {"wght": 3.2}, "stylename": "Black",
                    "postscriptfontname": "OldSans-Black"}],
    )
    fonts = readFileFonts(saveFont(font, tmp_path / "old.ttf"), source)
    assert fonts[-1].weight == 900


def testWeightBelowThinIsReadFromTheName(tmp_path: Path) -> None:
    path = saveFont(buildFont("Old Sans", "Light", "OldSans-Light", 0),
                    tmp_path / "old.ttf")
    assert readFileFonts(path, source)[0].weight == 300


@pytest.mark.parametrize(("style", "selection", "slant"), [
    ("Regular", 0, TypefaceSlant.NORMAL),
    ("Italic", italicSelection, TypefaceSlant.ITALIC),
    ("Oblique", obliqueSelection, TypefaceSlant.OBLIQUE),
    ("Light Oblique", italicSelection, TypefaceSlant.OBLIQUE),
    ("Ultra Light Italic", 0, TypefaceSlant.ITALIC),
    ("Inclined", 0, TypefaceSlant.ITALIC),
])
def testSlantIsReadFromTheBitsOrTheName(
    tmp_path: Path, style: str, selection: int, slant: TypefaceSlant
) -> None:
    path = saveFont(buildFont("Brand Sans", style, "BrandSans-X", 400, selection),
                    tmp_path / "brand.ttf")
    assert readFileFonts(path, source)[0].slant is slant


def testLegacyFaceWithNoOs2ReadsHeadMacStyle(tmp_path: Path) -> None:
    font = buildFont("Old Mono", "Bold Oblique", "OldMono-BoldOblique")
    del font["OS/2"]
    font["head"].macStyle = 0b11
    font = readFileFonts(saveFont(font, tmp_path / "old.ttf"), source)[0]
    assert (font.weight, font.slant) == (700, TypefaceSlant.OBLIQUE)


@pytest.mark.parametrize(("family", "postScriptName"), [
    (".Hidden Sans", "HiddenSans-Regular"), ("Hidden Sans", ".HiddenSans-Regular"),
])
def testHiddenFaceIsLeftOut(
    tmp_path: Path, family: str, postScriptName: str
) -> None:
    path = saveFont(buildFont(family, "Regular", postScriptName), tmp_path / "h.ttf")
    assert readFileFonts(path, source) == ()


def testFontFileItCannotReadIsRefusedInPybersWordsAlone(tmp_path: Path) -> None:
    path = tmp_path / "notes.ttf"
    path.write_text("not a font")
    with pytest.raises(TypefaceError) as refused:
        readFileFonts(path, source)
    assert str(refused.value) == (
        f"{path} is not a font file pybers can read. Nothing was read."
    )
    assert refused.value.__cause__ is not None


def testFileWithoutAFontsSuffixIsToldWhichToGive(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("not a font")
    with pytest.raises(TypefaceError, match="Give an .otf, .ttf or .ttc file"):
        readFileFonts(path, source)

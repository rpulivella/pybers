#!/usr/bin/env python3
"""\
The faces a font file offers, as the one font reader reads them.

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

from pybers.font._files import FontError, readFileFaces
from pybers.font.faces import FontFace, FontSlant, FontSource

source = FontSource.FILE


def testStaticFaceReadsItsNamesWeightAndSlant(tmp_path: Path) -> None:
    path = saveFont(
        buildFont("Brand Sans", "Semibold Italic", "BrandSans-SemiboldItalic", 600,
                  italicSelection),
        tmp_path / "brand.ttf",
    )
    assert readFileFaces(path, source) == (FontFace(
        fontFamily="Brand Sans", name="Semibold Italic",
        postScriptName="BrandSans-SemiboldItalic", weight=600,
        slant=FontSlant.ITALIC, source=source, file=path,
    ),)


def testCollectionOffersEachFaceInFileOrder(tmp_path: Path) -> None:
    path = saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Sans", "Bold", "BrandSans-Bold", 700),
    ], tmp_path / "brand.ttc")
    assert [face.postScriptName for face in readFileFaces(path, source)] == [
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
    faces = readFileFaces(saveFont(font, tmp_path / "brand.ttf"), source)
    assert [(face.postScriptName, face.weight) for face in faces] == [
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
    faces = readFileFaces(saveFont(font, tmp_path / "old.ttf"), source)
    assert faces[-1].weight == 900


def testWeightBelowThinIsReadFromTheName(tmp_path: Path) -> None:
    path = saveFont(buildFont("Old Sans", "Light", "OldSans-Light", 0),
                    tmp_path / "old.ttf")
    assert readFileFaces(path, source)[0].weight == 300


@pytest.mark.parametrize(("style", "selection", "slant"), [
    ("Regular", 0, FontSlant.NORMAL),
    ("Italic", italicSelection, FontSlant.ITALIC),
    ("Oblique", obliqueSelection, FontSlant.OBLIQUE),
    ("Light Oblique", italicSelection, FontSlant.OBLIQUE),
    ("Ultra Light Italic", 0, FontSlant.ITALIC),
    ("Inclined", 0, FontSlant.ITALIC),
])
def testSlantIsReadFromTheBitsOrTheName(
    tmp_path: Path, style: str, selection: int, slant: FontSlant
) -> None:
    path = saveFont(buildFont("Brand Sans", style, "BrandSans-X", 400, selection),
                    tmp_path / "brand.ttf")
    assert readFileFaces(path, source)[0].slant is slant


def testLegacyFaceWithNoOs2ReadsHeadMacStyle(tmp_path: Path) -> None:
    font = buildFont("Old Mono", "Bold Oblique", "OldMono-BoldOblique")
    del font["OS/2"]
    font["head"].macStyle = 0b11
    face = readFileFaces(saveFont(font, tmp_path / "old.ttf"), source)[0]
    assert (face.weight, face.slant) == (700, FontSlant.OBLIQUE)


@pytest.mark.parametrize(("family", "postScriptName"), [
    (".Hidden Sans", "HiddenSans-Regular"), ("Hidden Sans", ".HiddenSans-Regular"),
])
def testHiddenFaceIsLeftOut(
    tmp_path: Path, family: str, postScriptName: str
) -> None:
    path = saveFont(buildFont(family, "Regular", postScriptName), tmp_path / "h.ttf")
    assert readFileFaces(path, source) == ()


def testFileThatIsNotAFontIsRefusedNamingIt(tmp_path: Path) -> None:
    path = tmp_path / "notes.ttf"
    path.write_text("not a font")
    with pytest.raises(FontError, match="notes.ttf is not a font pybers can read"):
        readFileFaces(path, source)

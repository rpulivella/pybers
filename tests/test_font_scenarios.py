#!/usr/bin/env python3
"""\
The few lines each consumer writes to find a face before naming it in a style.

Both read the catalog pybers ships and a brand's own font file, so each runs alike on
any system.

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

from click.testing import CliRunner
from fontbuilders import buildFont, italicSelection, saveCollection

import pybers
from conftest import findDocumentPath
from pybers.cli._app import app


def saveBrandFont(folder: Path) -> Path:
    """Return a brand's font file, a regular and a semibold italic."""
    return saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Sans", "Semibold Italic", "BrandSans-SemiboldItalic", 600,
                  italicSelection),
    ], folder / "BrandSans.ttc")


def testAScriptAuthorFindsTheFacesAStyleWillName(tmp_path: Path) -> None:
    fonts = pybers.openFonts()
    heading = fonts.face("Avenir Next", weight=600)
    italics = fonts.select("AvenirNext[slant=italic][weight>=600]")

    brand = pybers.openFonts(saveBrandFont(tmp_path))
    emphasis = brand.face("brand sans", weight=600, slant=pybers.FontSlant.ITALIC)

    assert heading.postScriptName == "AvenirNext-DemiBold"
    assert [each.postScriptName for each in italics] == [
        "AvenirNext-DemiBoldItalic", "AvenirNext-BoldItalic", "AvenirNext-HeavyItalic",
    ]
    assert emphasis.postScriptName == "BrandSans-SemiboldItalic"
    assert brand.face(postScriptName="BrandSans-SemiboldItalic") == emphasis


def testACommandFindsAFaceAndChecksADocumentsFaces(tmp_path: Path) -> None:
    runner = CliRunner()
    brandPath = saveBrandFont(tmp_path)

    shown = runner.invoke(app, ["show", "fonts", "avenir next::demi bold"]).stdout
    brand = runner.invoke(app, ["show", str(brandPath), "*[slant=italic]"]).stdout
    checked = runner.invoke(
        app, ["check", str(findDocumentPath("52-table-reset-styled"))]
    ).stdout

    assert "Face: AvenirNext-DemiBold" in shown
    assert "Face: BrandSans-SemiboldItalic" in brand
    assert "AvenirNext-Regular: catalog" in checked

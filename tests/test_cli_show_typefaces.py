#!/usr/bin/env python3
"""\
`pybers show typefaces` and `pybers show FONTFILE`: fonts, one per line, or as JSON.

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
from click.testing import CliRunner, Result
from fontbuilders import buildFont, saveCollection

import pybers
from conftest import firaSansDirectory
from pybers.cli._app import app

runner: CliRunner = CliRunner()


def runShowCommand(*arguments: str | Path) -> Result:
    """Return what `pybers show` does with these arguments."""
    return runner.invoke(app, ["show", *(str(each) for each in arguments)])


@pytest.fixture
def brandPath(tmp_path: Path) -> Path:
    """Return a collection of two fonts, a regular and a long-named bold italic."""
    return saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Sans", "Extra Bold Italic", "BrandSans-ExtraBoldItalicDisplay",
                  800, 1),
    ], tmp_path / "brand.ttc")


def testFontFileShowsItsTypefaceAndEachFaceOnOneLine(brandPath: Path) -> None:
    result = runShowCommand(brandPath)
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Typeface: Brand Sans  2 fonts",
        "  Font: BrandSans-Regular   Name: Regular   Weight: 400   Slant: normal   "
        "Source: file",
        "  Font: BrandSans-ExtraBoldItalicDisplay   Name: Extra Bold Italic   "
        "Weight: 800   Slant: italic   Source: file",
    ]


def testFamiliesAreSeparatedByABlankLine(tmp_path: Path) -> None:
    path = saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Serif", "Regular", "BrandSerif-Regular"),
    ], tmp_path / "brand.ttc")
    lines = runShowCommand(path).stdout.splitlines()
    assert [line for line in lines if not line.startswith("  ")] == [
        "Typeface: Brand Sans  1 font", "", "Typeface: Brand Serif  1 font",
    ]


def testFolderOfFontFilesShowsEveryFont() -> None:
    result = runShowCommand(firaSansDirectory, "Fira Sans::*Bold*")
    assert result.exit_code == 0
    assert result.stdout.splitlines()[0] == "Typeface: Fira Sans  4 fonts"


def testSelectorNarrowsAFontFile(brandPath: Path) -> None:
    result = runShowCommand(brandPath, "*[weight>=800]")
    fonts = [line for line in result.stdout.splitlines() if "Font:" in line]
    assert len(fonts) == 1 and "Weight: 800" in fonts[0]


def testJsonReadsBackAsTheFacesShown(brandPath: Path) -> None:
    result = runShowCommand(brandPath, "--output-format", "json")
    assert pybers.parseJsonForm(result.stdout) == pybers.openTypefaces(brandPath)


def testTypefacesShowsTheCatalogOnAnySystem() -> None:
    result = runShowCommand("typefaces", '*[postscript="HelveticaNeue-Bold" s]')
    assert result.exit_code == 0
    assert "HelveticaNeue-Bold" in result.stdout and "catalog" in result.stdout


def testMisspelledTypefaceIsRefusedNamingTheClosest() -> None:
    result = runShowCommand("typefaces", "Helvetica Nue")
    assert result.exit_code == 1
    assert "The closest is 'Helvetica Neue'" in result.stderr


def testFileNamedTypefacesIsReachedAsADocument(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "typefaces").write_text("not a document")
    monkeypatch.chdir(tmp_path)
    result = runShowCommand("./typefaces")
    assert result.exit_code == 1 and result.stdout == ""


def testUnreadableMachineFontPrintsSkippedOnStderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.otf"
    broken.write_text("not a font")
    monkeypatch.setattr(
        "pybers.typeface.typefaces.findMachineFontFiles", lambda: (broken,)
    )
    result = runShowCommand("typefaces", "Helvetica::Bold")
    assert result.exit_code == 0
    assert "Font: Helvetica-Bold" in result.stdout
    assert result.stderr.startswith("Skipped: ") and "broken.otf" in result.stderr

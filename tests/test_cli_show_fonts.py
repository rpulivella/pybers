#!/usr/bin/env python3
"""\
`pybers show fonts` and `pybers show FONTFILE`: faces, one per line, or their JSON form.

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
from pybers.cli._app import app

runner: CliRunner = CliRunner()


def runShowCommand(*arguments: str | Path) -> Result:
    """Return what `pybers show` does with these arguments."""
    return runner.invoke(app, ["show", *(str(each) for each in arguments)])


@pytest.fixture
def brandPath(tmp_path: Path) -> Path:
    """Return a collection of two faces, a regular and a long-named bold italic."""
    return saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Sans", "Extra Bold Italic", "BrandSans-ExtraBoldItalicDisplay",
                  800, 1),
    ], tmp_path / "brand.ttc")


def testFontFileShowsItsFamilyAndEachFaceOnOneLine(brandPath: Path) -> None:
    result = runShowCommand(brandPath)
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Font family: Brand Sans  2 faces",
        "  Face: BrandSans-Regular   Name: Regular   Weight: 400   Slant: normal   "
        "Source: file",
        "  Face: BrandSans-ExtraBoldItalicDisplay   Name: Extra Bold Italic   "
        "Weight: 800   Slant: italic   Source: file",
    ]


def testFamiliesAreSeparatedByABlankLine(tmp_path: Path) -> None:
    path = saveCollection([
        buildFont("Brand Sans", "Regular", "BrandSans-Regular"),
        buildFont("Brand Serif", "Regular", "BrandSerif-Regular"),
    ], tmp_path / "brand.ttc")
    lines = runShowCommand(path).stdout.splitlines()
    assert [line for line in lines if not line.startswith("  ")] == [
        "Font family: Brand Sans  1 face", "", "Font family: Brand Serif  1 face",
    ]


def testSelectorNarrowsAFontFile(brandPath: Path) -> None:
    result = runShowCommand(brandPath, "*[weight>=800]")
    faces = [line for line in result.stdout.splitlines() if "Face:" in line]
    assert len(faces) == 1 and "Weight: 800" in faces[0]


def testJsonReadsBackAsTheFacesShown(brandPath: Path) -> None:
    result = runShowCommand(brandPath, "--output-format", "json")
    assert pybers.parseJsonForm(result.stdout) == pybers.openFonts(brandPath)


def testFontsShowsTheCatalogOnAnySystem() -> None:
    result = runShowCommand("fonts", '*[postscript="HelveticaNeue-Bold" s]')
    assert result.exit_code == 0
    assert "HelveticaNeue-Bold" in result.stdout and "catalog" in result.stdout


def testMisspelledFontFamilyIsRefusedNamingTheClosest() -> None:
    result = runShowCommand("fonts", "Helvetica Nue")
    assert result.exit_code == 1
    assert "The closest is 'Helvetica Neue'" in result.stderr


def testFileNamedFontsIsReachedAsADocument(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "fonts").write_text("not a document")
    monkeypatch.chdir(tmp_path)
    result = runShowCommand("./fonts")
    assert result.exit_code == 1 and result.stdout == ""


def testUnreadableMachineFontPrintsSkippedOnStderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.otf"
    broken.write_text("not a font")
    monkeypatch.setattr("pybers.font.fonts.findMachineFontFiles", lambda: (broken,))
    result = runShowCommand("fonts", "Helvetica::Bold")
    assert result.exit_code == 0
    assert "Face: Helvetica-Bold" in result.stdout
    assert result.stderr.startswith("Skipped: ") and "broken.otf" in result.stderr

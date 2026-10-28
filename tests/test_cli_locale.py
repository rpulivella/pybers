#!/usr/bin/env python3
"""\
`pybers locale`, run the way a person or an agent at a command line runs it.

Each test changes a copy of `95-region-base`, a document under `en_US`, and the
measurements derived from it record what Numbers writes for each region.

UPDATES
2026-10-28  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/28"

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import pybers
from conftest import copyDocument
from pybers.cli._app import app

runner: CliRunner = CliRunner()


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a write never touches the measurement."""
    return copyDocument("95-region-base", tmp_path)


def runLocaleCommand(*arguments: str | Path) -> Result:
    """Return what `pybers locale` does with these arguments."""
    return runner.invoke(app, ["locale", *(str(each) for each in arguments)])


def testACommandChangesADocumentsRegionInPlace(working: Path) -> None:
    result = runLocaleCommand(working, "de_DE", "--in-place")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["Before: en_US", "After: de_DE"]
    assert f"Written: {working}" in result.stderr
    assert pybers.open(working).localeIdentifier == "de_DE"


def testARegionIsWrittenToANewDocumentLeavingTheOriginal(
    working: Path, tmp_path: Path
) -> None:
    output = tmp_path / "german.numbers"
    assert runLocaleCommand(working, "de_DE", "-o", output).exit_code == 0
    assert pybers.open(output).localeIdentifier == "de_DE"
    assert pybers.open(working).localeIdentifier == "en_US"


def testAPreviewWritesNothing(working: Path) -> None:
    before = working.read_bytes()
    result = runLocaleCommand(working, "de_DE", "--preview")
    assert result.exit_code == 0
    assert "Nothing written: a preview." in result.stderr
    assert working.read_bytes() == before


def testTheRegionADocumentHoldsWritesNothing(working: Path) -> None:
    before = working.read_bytes()
    result = runLocaleCommand(working, "en_US", "--in-place")
    assert result.exit_code == 0
    assert "Nothing written: the document already uses that region." in result.stderr
    assert working.read_bytes() == before


def testARegionPybersDoesNotOfferIsRefused(working: Path) -> None:
    result = runLocaleCommand(working, "de_XX", "--in-place")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith(
        "pybers locale: No region pybers offers is named 'de_XX'. The closest of the "
    )
    assert pybers.open(working).localeIdentifier == "en_US"


def testAChangeNamesWhereItIsWritten(working: Path) -> None:
    result = runLocaleCommand(working, "de_DE")
    assert result.exit_code == 2
    assert "--in-place" in result.stderr


def testWithNoRegionTheCommandListsEveryRegionOffered(working: Path) -> None:
    result = runLocaleCommand(working)
    lines = result.stdout.splitlines()
    assert result.exit_code == 0
    assert lines[:2] == [
        "Locale: en_US", f"Regions offered: {len(pybers.locales)} regions",
    ]
    assert any(line.endswith("de: " + ", ".join(
        each for each in pybers.locales if each.startswith("de_")
    )) for line in lines)


def testTheListingAsJsonNamesTheRegionAndEveryOneOffered(working: Path) -> None:
    result = runLocaleCommand(working, "--format", "json")
    assert json.loads(result.stdout) == {
        "localeIdentifier": "en_US", "locales": list(pybers.locales),
    }


def testAChangeAsJsonIsTheLibrarysChange(working: Path) -> None:
    result = runLocaleCommand(working, "de_DE", "--preview", "--format", "json")
    assert result.stdout == pybers.formatJsonForm(
        pybers.LocaleChange("en_US", "de_DE")
    ) + "\n"

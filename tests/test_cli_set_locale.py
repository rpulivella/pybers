#!/usr/bin/env python3
"""\
`pybers set --locale`, run the way a person or an agent at a command line runs it.

Each test changes a copy of `95-region-base`, a document under `en_US`, and the
measurements derived from it record what Numbers writes for each region.

UPDATES
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-19  `set --locale` in place of the `locale` command, for PYB-301.
2026-11-03  The region prints as `show` prints it, read or changed, and the
            regions offered are no longer listed, for PYB-223.
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
from click.testing import CliRunner, Result

import pybers
from conftest import copyDocument, readPlainText
from pybers.cli._app import app

runner: CliRunner = CliRunner()


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a write never touches the measurement."""
    return copyDocument("95-region-base", tmp_path)


def runLocaleCommand(document: Path, identifier: str, *arguments: str | Path) -> Result:
    """Return what `pybers set --locale` does with these arguments."""
    return runner.invoke(
        app, [
            "set", str(document), "--locale", identifier,
            *(str(each) for each in arguments),
        ],
    )


def testACommandChangesTheDocumentItNames(working: Path) -> None:
    result = runLocaleCommand(working, "de_DE")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["Locale: de_DE"]
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
    assert "Nothing written: previewing only" in result.stderr
    assert working.read_bytes() == before


def testTheRegionADocumentHoldsWritesNothing(working: Path) -> None:
    before = working.read_bytes()
    result = runLocaleCommand(working, "en_US")
    assert result.exit_code == 0
    assert "Nothing written: already en_US" in result.stderr
    assert working.read_bytes() == before


def testARegionPybersDoesNotOfferIsRefused(working: Path) -> None:
    result = runLocaleCommand(working, "de_XX")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith(
        "pybers set: 'de_XX' is not a region pybers offers. The closest is de_LU."
    )
    assert pybers.open(working).localeIdentifier == "en_US"


def testANewFileThatExistsIsRefusedLeavingIt(working: Path, tmp_path: Path) -> None:
    existing = copyDocument("00-baseline", tmp_path)
    before = existing.read_bytes()
    result = runLocaleCommand(working, "de_DE", "-o", existing)
    assert result.exit_code == 2
    assert "specifies a file that exists, and -o writes only a new one" in (
        readPlainText(result.stderr)
    )
    assert existing.read_bytes() == before


def testTheRegionPrintsAsShowPrintsIt(working: Path) -> None:
    result = runLocaleCommand(working, "en_US")
    shown = runner.invoke(app, ["show", str(working)]).stdout.splitlines()
    assert result.stdout.splitlines() == [shown[0]]


def testJsonIsTheRegionUnderItsJsonFormKey(working: Path) -> None:
    result = runLocaleCommand(
        working, "de_DE", "--preview", "--output-format", "json"
    )
    assert json.loads(result.stdout) == {"localeIdentifier": "de_DE"}


@pytest.mark.parametrize("arguments", [("Sheet 1",), ("Sheet 1::Table 1::A1", "1")])
def testALocaleGivenWithASelectorIsRefusedWritingNothing(
    working: Path, arguments: tuple[str, ...]
) -> None:
    before = working.read_bytes()
    result = runner.invoke(
        app, ["set", str(working), *arguments, "--locale", "de_DE"]
    )
    assert result.exit_code == 2
    assert "--locale sets the whole document" in readPlainText(result.stderr)
    assert working.read_bytes() == before


def testSetGivenNeitherASelectorNorALocaleIsRefused(working: Path) -> None:
    result = runner.invoke(app, ["set", str(working)])
    assert result.exit_code == 2
    assert "SELECTOR is missing. Give a SELECTOR, or --locale." in readPlainText(
        result.stderr
    )

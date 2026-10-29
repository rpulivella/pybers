#!/usr/bin/env python3
"""\
`pybers set`, run the way a person or an agent at a command line runs it.

Each test edits a copy of `20-formula-shapes`, whose `Table 2` is ten rows by five
columns and named on one sheet only, while `Table 1` is named on two.

UPDATES
2026-10-28  A write changes FILE itself unless `-o` names a new one, for
            PYB-272.
2026-10-27  Each listed table name quoted, for PYB-260.
2026-10-24  A number read back as the JSON number it is printed as, and a duration
            as ISO 8601, for PYB-259.
2026-10-20  A date, a duration and a boolean, inferred or named, and the zone an
            aware date is written in, for PYB-144.
2026-10-20  Written for PYB-217.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

import datetime
import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import pybers
from conftest import copyDocument, readPlainText
from pybers.cli._app import app

runner: CliRunner = CliRunner()


@pytest.fixture
def working(tmp_path: Path) -> Path:
    """Return a copy of the document, so a write never touches the fixture."""
    return copyDocument("20-formula-shapes", tmp_path)


def runSetCommand(*arguments: str) -> Result:
    """Return what `pybers set` does with these arguments."""
    return runner.invoke(app, ["set", *arguments])


def readCell(path: Path, reference: str) -> pybers.Cell:
    """Return one cell of a document as a fresh read finds it."""
    return pybers.open(path).cell(reference)


def testANumberIsWrittenInPlaceAndReported(working: Path) -> None:
    result = runSetCommand(str(working), "Table 2::B2", "42")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Cell: Sheet 1::Table 2::B2", "Before: none (empty)", "After: 42 (number)",
    ]
    assert f"Written: {working}" in result.stderr
    assert readCell(working, "Table 2::B2").value == Decimal(42)


def testTextIsWrittenToANewDocumentLeavingTheOriginal(
    working: Path, tmp_path: Path
) -> None:
    output = tmp_path / "out.numbers"
    result = runSetCommand(str(working), "Table 2::B2", "hello", "-o", str(output))
    assert result.exit_code == 0
    assert readCell(output, "Table 2::B2").value == "hello"
    assert readCell(working, "Table 2::B2").value is None


def testAsTextKeepsANumberAsText(working: Path) -> None:
    runSetCommand(str(working), "Table 2::B2", "042", "--as", "text")
    cell = readCell(working, "Table 2::B2")
    assert (cell.value, cell.kind) == ("042", pybers.CellKind.TEXT)


def testTextThatIsNotTheKindNamedIsRefused(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(
        str(working), "Table 2::B2", "abc", "--as", "number"
    )
    assert result.exit_code == 1
    assert "pybers set: 'abc' is not a number." in result.stderr
    assert working.read_bytes() == before


def testAPreviewReportsTheChangeAndWritesNothing(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(str(working), "Table 2::B2", "42", "--preview")
    assert result.exit_code == 0
    assert "After: 42 (number)" in result.stdout
    assert "Nothing written: a preview." in result.stderr
    assert working.read_bytes() == before


def testAChangeThatAltersNothingWritesNothingAndSaysSo(working: Path) -> None:
    runSetCommand(str(working), "Table 2::B2", "42")
    before = working.read_bytes()
    result = runSetCommand(str(working), "Table 2::B2", "42")
    assert result.exit_code == 0
    assert "Nothing written: the cell already holds that." in result.stderr
    assert working.read_bytes() == before


def testAPreviewAndANewFileTogetherAreRefused(working: Path) -> None:
    result = runSetCommand(
        str(working), "Table 2::B2", "1", "--preview", "-o", "elsewhere.numbers"
    )
    assert result.exit_code == 2
    assert "Give -o or --preview, not both." in readPlainText(result.stderr)


def testAnOutputThatExistsIsRefused(working: Path, tmp_path: Path) -> None:
    existing = copyDocument("00-baseline", tmp_path)
    before = existing.read_bytes()
    result = runSetCommand(str(working), "Table 2::B2", "1", "-o", str(existing))
    assert result.exit_code == 2
    assert existing.read_bytes() == before


def testACellOutsideItsTableIsRefusedNamingTheSize(working: Path) -> None:
    result = runSetCommand(str(working), "Table 2::G12", "x")
    assert result.exit_code == 1
    assert "10 rows by 5 columns" in result.stderr


def testExtendGrowsTheTableToHoldTheCell(working: Path) -> None:
    result = runSetCommand(str(working), "Table 2::G12", "x", "--extend")
    assert result.exit_code == 0
    assert "Grown: 2 rows, 2 columns" in result.stdout
    assert readCell(working, "Table 2::G12").value == "x"


def testAnAmbiguousTableIsRefusedListingTheMatches(working: Path) -> None:
    result = runSetCommand(str(working), "Table 1::B2", "1")
    assert result.exit_code == 1
    assert "'Sheet 1::Table 1', 'Sheet 2::Table 1'" in result.stderr


def testJsonReportsTheChangeAsTheLibraryReturnsIt(working: Path) -> None:
    result = runSetCommand(
        str(working), "Table 2::B2", "1.50", "--preview", "--format", "json"
    )
    assert json.loads(result.stdout, parse_float=Decimal) == {
        "reference": "Sheet 1::Table 2::B2",
        "valueBefore": None,
        "valueAfter": Decimal("1.50"),
        "kindBefore": "empty",
        "kindAfter": "number",
        "rowsAdded": 0,
        "colsAdded": 0,
    }


@pytest.mark.parametrize(("text", "value", "shown"), [
    ("2026-10-20 09:30", datetime.datetime(2026, 10, 20, 9, 30), "2026-10-20 09:30:00"),
    ("2026-10-20", datetime.datetime(2026, 10, 20), "2026-10-20 00:00:00"),
    ("1h 30m", datetime.timedelta(minutes=90), "1h 30m"),
    ("90m", datetime.timedelta(minutes=90), "1h 30m"),
    ("TRUE", True, "TRUE"),
    ("false", False, "FALSE"),
])
def testADateADurationAndABooleanAreInferred(
    working: Path, text: str, value: object, shown: str
) -> None:
    result = runSetCommand(str(working), "Table 2::B2", text)
    assert result.exit_code == 0
    assert result.stdout.splitlines()[-1].startswith(f"After: {shown} (")
    assert readCell(working, "Table 2::B2").value == value


@pytest.mark.parametrize(("text", "kind", "value"), [
    ("1:30", "duration", datetime.timedelta(minutes=90)),
    ("20261020", "date", datetime.datetime(2026, 10, 20)),
    ("TRUE", "text", "TRUE"),
    ("2026-10-20", "text", "2026-10-20"),
    ("True", "boolean", True),
])
def testAsOverridesTheInference(
    working: Path, text: str, kind: str, value: object
) -> None:
    runSetCommand(str(working), "Table 2::B2", text, "--as", kind)
    assert readCell(working, "Table 2::B2").value == value


def testAClockIsTextUnlessADurationIsNamed(working: Path) -> None:
    runSetCommand(str(working), "Table 2::B2", "1:30")
    assert readCell(working, "Table 2::B2").value == "1:30"


def testTimeZoneWritesAnOffsetDateAsThatZonesWallClock(working: Path) -> None:
    result = runSetCommand(
        str(working), "Table 2::B2", "2026-10-20T16:00Z",
        "--time-zone", "America/Los_Angeles",
    )
    assert result.exit_code == 0
    assert "After: 2026-10-20 09:00:00 (date-time)" in result.stdout
    assert readCell(working, "Table 2::B2").value == datetime.datetime(2026, 10, 20, 9)


def testAZoneNoOneKnowsIsRefusedAndNothingWritten(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(
        str(working), "Table 2::B2", "2026-10-20T16:00Z",
        "--time-zone", "Mars/Olympus",
    )
    assert result.exit_code == 1
    assert "'Mars/Olympus' specifies no time zone" in result.stderr
    assert working.read_bytes() == before


def testWhatJsonPrintsIsTextSetWritesBackUnchanged(working: Path) -> None:
    result = runSetCommand(
        str(working), "Table 2::B2", "2d 4h 0.5s", "--preview", "--format", "json"
    )
    printed = json.loads(result.stdout)["valueAfter"]
    assert printed == "P2DT4H0.5S"
    runSetCommand(str(working), "Table 2::B2", printed)
    assert readCell(working, "Table 2::B2").value == datetime.timedelta(
        days=2, hours=4, milliseconds=500
    )

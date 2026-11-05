#!/usr/bin/env python3
"""\
`pybers set`, run the way a person or an agent at a command line runs it.

Each test edits a copy of `20-formula-shapes`, whose `Table 2` is ten rows by five
columns and named on one sheet only, while `Table 1` is named on two.

UPDATES
2026-11-03  Every cell a selector matches is written and printed as `show` prints
            it, and a cell it cannot write skipped on stderr, for PYB-223.
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
from conftest import copyDocument, listShownFields, readPlainText
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
    """Return the cell `Table 2::B2` names, as a fresh read finds it."""
    table, _, address = reference.rpartition("::")
    return pybers.open(path).table(table).cell(address)


def testANumberIsWrittenInPlaceAndReported(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 2::B2", "42")
    assert result.exit_code == 0
    assert listShownFields(result.stdout)[:3] == [
        ("Cell", "Sheet 1::Table 2::B2"), ("Value", "42"), ("Kind", "number"),
    ]
    assert f"Written: {working}" in result.stderr
    assert readCell(working, "Table 2::B2").value == Decimal(42)


def testTextIsWrittenToANewDocumentLeavingTheOriginal(
    working: Path, tmp_path: Path
) -> None:
    output = tmp_path / "out.numbers"
    result = runSetCommand(str(working), "::Table 2::B2", "hello", "-o", str(output))
    assert result.exit_code == 0
    assert readCell(output, "Table 2::B2").value == "hello"
    assert readCell(working, "Table 2::B2").value is None


def testAsTextKeepsANumberAsText(working: Path) -> None:
    runSetCommand(str(working), "::Table 2::B2", "042", "--as", "text")
    cell = readCell(working, "Table 2::B2")
    assert (cell.value, cell.kind) == ("042", pybers.CellKind.TEXT)


def testTextThatIsNotTheKindNamedIsRefused(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(
        str(working), "::Table 2::B2", "abc", "--as", "number"
    )
    assert result.exit_code == 1
    assert "pybers set: 'abc' is not a number." in result.stderr
    assert working.read_bytes() == before


def testAPreviewReportsTheChangeAndWritesNothing(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(str(working), "::Table 2::B2", "42", "--preview")
    assert result.exit_code == 0
    assert ("Value", "42") in listShownFields(result.stdout)
    assert "Nothing written: a preview." in result.stderr
    assert working.read_bytes() == before


def testAChangeThatAltersNothingWritesNothingAndSaysSo(working: Path) -> None:
    runSetCommand(str(working), "::Table 2::B2", "42")
    before = working.read_bytes()
    result = runSetCommand(str(working), "::Table 2::B2", "42")
    assert result.exit_code == 0
    assert "Nothing written: no cell it matched changes." in result.stderr
    assert working.read_bytes() == before


def testAPreviewAndANewFileTogetherAreRefused(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 2::B2", "1", "--preview", "-o", "elsewhere.numbers"
    )
    assert result.exit_code == 2
    assert "Give -o or --preview, not both." in readPlainText(result.stderr)


def testAnOutputThatExistsIsRefused(working: Path, tmp_path: Path) -> None:
    existing = copyDocument("00-baseline", tmp_path)
    before = existing.read_bytes()
    result = runSetCommand(str(working), "::Table 2::B2", "1", "-o", str(existing))
    assert result.exit_code == 2
    assert existing.read_bytes() == before


def testACellOutsideItsTableIsRefusedNamingTheSize(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 2::G12", "x")
    assert result.exit_code == 1
    assert "10 rows by 5 columns" in result.stderr


def testExtendGrowsTheTableToHoldTheCell(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 2::G12", "x", "--extend")
    assert result.exit_code == 0
    assert listShownFields(result.stdout)[:2] == [
        ("Cell", "Sheet 1::Table 2::G12"), ("Value", "x")
    ]
    assert readCell(working, "Table 2::G12").value == "x"


def testEveryCellMatchedIsWrittenAndPrintedAsShowPrintsIt(working: Path) -> None:
    result = runSetCommand(str(working), "::Table 1::B2", "1")
    assert result.exit_code == 0
    cells = [line for line in result.stdout.splitlines() if line.startswith("Cell: ")]
    assert cells == [
        "Cell: Sheet 1::Table 1::B2", "Cell: Sheet 2::Table 1::B2",
    ]
    shown = runner.invoke(app, ["show", str(working), "::Table 1::B2"])
    assert result.stdout == shown.stdout


def testACellItCannotWriteIsSkippedOnStderrSayingWhy(working: Path) -> None:
    result = runSetCommand(str(working), "Sheet 1::Table 1::A10:A11", "1")
    assert result.exit_code == 0
    assert "Cell: Sheet 1::Table 1::A10" in result.stdout
    assert "Skipped" not in result.stdout
    assert (
        "Skipped: Sheet 1::Table 1::A11 is backed by a formula, which a value would "
        "discard." in result.stderr.splitlines()
    )


def testJsonIsTheFormOfEachCellWrittenAndReadsBack(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 2::B2", "1.50", "--preview", "--format", "json"
    )
    form = json.loads(result.stdout, parse_float=Decimal)
    assert form[0]["table"]["cells"][0]["value"] == Decimal("1.50")
    (cell,) = pybers.parseJsonForm(result.stdout)
    assert isinstance(cell, pybers.Cell) and cell.value == Decimal("1.50")


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
    result = runSetCommand(str(working), "::Table 2::B2", text)
    assert result.exit_code == 0
    assert ("Value", shown) in listShownFields(result.stdout)
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
    runSetCommand(str(working), "::Table 2::B2", text, "--as", kind)
    assert readCell(working, "Table 2::B2").value == value


def testAClockIsTextUnlessADurationIsNamed(working: Path) -> None:
    runSetCommand(str(working), "::Table 2::B2", "1:30")
    assert readCell(working, "Table 2::B2").value == "1:30"


def testTimeZoneWritesAnOffsetDateAsThatZonesWallClock(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 2::B2", "2026-10-20T16:00Z",
        "--time-zone", "America/Los_Angeles",
    )
    assert result.exit_code == 0
    assert ("Value", "2026-10-20 09:00:00") in listShownFields(result.stdout)
    assert readCell(working, "Table 2::B2").value == datetime.datetime(2026, 10, 20, 9)


def testAZoneNoOneKnowsIsRefusedAndNothingWritten(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(
        str(working), "::Table 2::B2", "2026-10-20T16:00Z",
        "--time-zone", "Mars/Olympus",
    )
    assert result.exit_code == 1
    assert "'Mars/Olympus' specifies no time zone" in result.stderr
    assert working.read_bytes() == before


def testWhatJsonPrintsIsTextSetWritesBackUnchanged(working: Path) -> None:
    result = runSetCommand(
        str(working), "::Table 2::B2", "2d 4h 0.5s", "--preview", "--format", "json"
    )
    printed = json.loads(result.stdout)[0]["table"]["cells"][0]["value"]
    assert printed == "P2DT4H0.5S"
    runSetCommand(str(working), "::Table 2::B2", printed)
    assert readCell(working, "Table 2::B2").value == datetime.timedelta(
        days=2, hours=4, milliseconds=500
    )


def testGrowingATableTakesOneCellAndIsRefusedBeforeWriting(working: Path) -> None:
    before = working.read_bytes()
    result = runSetCommand(str(working), "::Table 1::Z99", "1", "--extend")
    assert result.exit_code == 1
    assert result.stderr.splitlines() == [
        "pybers set: `::Table 1::Z99` matches 2 tables, and growing a table to hold a "
        "cell grows one: `Sheet 1::Table 1`, `Sheet 2::Table 1`.",
    ]
    assert working.read_bytes() == before


def testTheHelpShowsAConditionInItsExampleSelector() -> None:
    result = runner.invoke(app, ["set", "--help"], terminal_width=200)
    assert "[kind=number]" in result.stdout

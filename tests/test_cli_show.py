#!/usr/bin/env python3
"""\
`pybers show`, run the way a person or an agent at a command line runs it.

`20-formula-shapes` holds `Table 1` on each of its two sheets and `Table 2` on the
first alone, and its `A11` holds `=SUM(A1:A10)`. `81-control-formats` holds a cell
for each control, a slider in `A1` and a pop-up menu in `I1`.

UPDATES
2026-10-28  A document's outline opens with its locale, for PYB-272.
2026-10-27  Written for PYB-260.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

import hashlib
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import pybers
from conftest import copyDocument, findDocumentPath, renderPlain
from pybers.cli._app import app
from pybers.cli.show import formatCell, formatControl, formatFormat, formatSheet

runner: CliRunner = CliRunner()

shapesPath: Path = findDocumentPath("20-formula-shapes")
controlsPath: Path = findDocumentPath("81-control-formats")


def runShowCommand(*arguments: str | Path) -> Result:
    """Return what `pybers show` does with these arguments."""
    return runner.invoke(app, ["show", *(str(each) for each in arguments)])


def findLines(result: Result, label: str) -> list[str]:
    """Return every line of a result opening with a label."""
    return [line for line in result.stdout.splitlines()
            if line.startswith(f"{label}: ")]


def readFingerprint(path: Path) -> tuple[tuple[str, str, int], ...]:
    """Return every file of a document with its digest and modification time."""
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    return tuple(
        (str(each), hashlib.sha256(each.read_bytes()).hexdigest(),
         each.stat().st_mtime_ns)
        for each in files if each.is_file()
    )


def testADocumentShowsEachSheetWithItsTablesAndSizes() -> None:
    result = runShowCommand(shapesPath)
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Locale: en_US",
        "Sheets:",
        "Sheet 1",
        "├ Table 1: 12 rows, 8 columns",
        "└ Table 2: 10 rows, 5 columns",
        "Sheet 2",
        "└ Table 1: 10 rows, 5 columns",
    ]


def testACellShowsOneLabeledLinePerFact() -> None:
    result = runShowCommand(shapesPath, "Sheet 1::Table 1::A11")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Cell: Sheet 1::Table 1::A11",
        "Value: 55",
        "Kind: number",
        "Formula text: =SUM(A1:A10)",
        "Value cached: yes",
        "Format: number",
        "Format chosen: no",
        "Control: none",
        "Unrecognized type code: none",
    ]


def testACellsLinesFollowTheNamesAndOrderOfItsJsonForm() -> None:
    form = json.loads(pybers.formatJsonForm(
        pybers.open(shapesPath).cell("Sheet 1::Table 1::A11")
    ))["table"]["cells"][0]
    keys = [key for key in form if key not in ("address", "formula")]
    index = keys.index("presentation")
    keys[index:index + 1] = list(form["presentation"])
    expected = [re.sub(r"(?<!^)(?=[A-Z])", " ", key).capitalize() for key in keys]
    lines = runShowCommand(shapesPath, "Sheet 1::Table 1::A11").stdout.splitlines()
    assert [line.split(": ")[0] for line in lines[1:]] == expected


@pytest.mark.parametrize(("address", "control"), [
    ("A1", "slider (minimum 0, maximum 200, increment 5)"),
    ("I1", "pop-up-menu (items ['Item 1', 'Item 2', 'Item 3'], "
           "starts with first item no)"),
    ("J1", "star-rating"),
])
def testAControlShowsEverySettingItHolds(address: str, control: str) -> None:
    result = runShowCommand(controlsPath, f"Table 1::{address}")
    assert findLines(result, "Control") == [f"Control: {control}"]


def testAControlsSettingsAreNamedAndOrderedAsItsJsonForm() -> None:
    control = pybers.open(controlsPath).cell("Table 1::I1").presentation.control
    family, *keys = json.loads(pybers.formatJsonForm(control))
    line = findLines(runShowCommand(controlsPath, "Table 1::I1"), "Control")[0]
    assert family == "controlType"
    found = [line.index(f"{re.sub(r'(?<!^)(?=[A-Z])', ' ', key).lower()} ")
             for key in keys]
    assert found == sorted(found)


formatStems: tuple[str, ...] = (
    "11-value-types-noformats", "12-number-currency", "13-number-percent",
    "14-number-date", "15-number-duration-formats",
    "16-number-scientific-numeralsystems", "17-number-custom",
    "54-format-star-rating", "81-control-formats",
)


def listPresentations() -> list[tuple[str, object, str]]:
    """Return each format and control the format documents hold, with its line."""
    found = []
    for stem in formatStems:
        for _, _, cell in pybers.open(findDocumentPath(stem)).cellsIterate():
            shown = cell.presentation
            found.append((stem, shown.format, formatFormat(shown.format)))
            found.append((stem, shown.control, formatControl(shown.control)))
    return found


def testEveryFormatAndControlShowsEachSettingOfItsJsonForm() -> None:
    for stem, subject, line in listPresentations():
        tree = json.loads(pybers.formatJsonForm(subject))
        if not isinstance(tree, dict):
            assert line == ("none" if tree is None else str(tree)), stem
            continue
        family, *settings = tree.values()
        assert line.startswith(str(family)), (stem, line)
        found = [line.index(f"{re.sub(r'(?<!^)(?=[A-Z])', ' ', key).lower()} ")
                 for key in list(tree)[1:]]
        assert found == sorted(found) and len(found) == len(settings), (stem, line)


def testATableShowsItsSizeMergesAndEachCell() -> None:
    result = runShowCommand(shapesPath, "Table 2")
    assert result.stdout.splitlines()[:5] == [
        "Table: Sheet 1::Table 2",
        "Size: 10 rows, 5 columns",
        "Merges: none",
        "Cells: 1 cell",
        "",
    ]
    assert findLines(result, "Cell") == ["Cell: Sheet 1::Table 2::A1"]


def testATableListsEachOfItsMerges() -> None:
    result = runShowCommand(findDocumentPath("22-merge-2x2"), "Table 1")
    assert findLines(result, "Merges") == [
        "Merges: A1:B1, C1:D1, E1:F1, G1:H1, I1:J1",
    ]


def testASheetHoldingNoTablesSaysSo() -> None:
    printed = renderPlain(formatSheet(pybers.Sheet(name="Empty")))
    assert printed.splitlines() == ["Sheet: Empty", "Tables: none"]


def testAFormatASaveHasNotChosenReadsUnknown() -> None:
    cell = pybers.open(shapesPath).cell("Sheet 1::Table 1::A1")
    cell.value = "text"
    assert cell.presentation.format is pybers.UNDETERMINED
    assert "Format: unknown" in renderPlain(formatCell(cell)).splitlines()


def testASheetShowsEachOfItsTables() -> None:
    result = runShowCommand(shapesPath, "Sheet 1")
    assert result.stdout.splitlines()[:2] == ["Sheet: Sheet 1", "Tables: 2 tables"]
    assert findLines(result, "Table") == [
        "Table: Sheet 1::Table 1", "Table: Sheet 1::Table 2",
    ]


def testARangeShowsOnlyTheCellsWithinIt() -> None:
    result = runShowCommand(shapesPath, "Sheet 1::Table 1::A1:C3")
    assert result.stdout.splitlines()[:2] == [
        "Range: Sheet 1::Table 1::A1:C3", "Cells: 3 cells",
    ]
    assert findLines(result, "Cell") == [
        "Cell: Sheet 1::Table 1::A1",
        "Cell: Sheet 1::Table 1::A2",
        "Cell: Sheet 1::Table 1::A3",
    ]


def testARangeHoldingNothingSaysSo() -> None:
    result = runShowCommand(shapesPath, "Table 2::B2:C4")
    assert result.stdout.splitlines() == [
        "Range: Sheet 1::Table 2::B2:C4", "Cells: none",
    ]


@pytest.mark.parametrize("selector", [
    None, "Sheet 1", "Table 2", "Sheet 1::Table 1::A1:C3", "Sheet 1::Table 1::A11",
])
def testJsonIsTheFormTheLibraryWritesForWhatIsSelected(selector: str | None) -> None:
    document = pybers.open(shapesPath)
    part = document if selector is None else document.partSelect(selector)
    expected = (
        pybers.formatJsonForm(document.sheet("Sheet 1").table("Table 1"), part)
        if isinstance(part, pybers.CellRange) else pybers.formatJsonForm(part)
    )
    arguments = [shapesPath] if selector is None else [shapesPath, selector]
    result = runShowCommand(*arguments, "--format", "json")
    assert result.exit_code == 0
    assert result.stdout == expected + "\n"


def testASelectorNamingNothingIsRefusedWithWhatTheDocumentHolds() -> None:
    result = runShowCommand(shapesPath, "Ledger")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        "pybers show: No sheet or table in this document is named 'Ledger'. The "
        "sheets are 'Sheet 1', 'Sheet 2'. The tables are 'Sheet 1::Table 1', "
        "'Sheet 1::Table 2', 'Sheet 2::Table 1'.",
    ]


def testACellOutsideItsTableIsRefusedWithTheTablesSize() -> None:
    result = runShowCommand(shapesPath, "Table 2::F1")
    assert result.exit_code == 1
    assert result.stderr.splitlines() == [
        "pybers show: F1 is outside 'Table 2', which is 10 rows by 5 columns.",
    ]


def testAMissingDocumentIsRefused(tmp_path: Path) -> None:
    missing = tmp_path / "missing.numbers"
    result = runShowCommand(missing)
    assert result.exit_code == 1
    assert result.stderr.splitlines() == [f"pybers show: {missing} does not exist."]


@pytest.mark.parametrize("selector", [
    "Sheet 1", "Table 2", "Table 2::B2:C4", "Table 2::B3", "Ledger",
])
def testShowNeverWritesTheDocument(tmp_path: Path, selector: str) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    before = readFingerprint(working)
    runShowCommand(working, selector)
    runShowCommand(working, selector, "--format", "json")
    assert readFingerprint(working) == before
    assert sorted(tmp_path.iterdir()) == [working]

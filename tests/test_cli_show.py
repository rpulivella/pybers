#!/usr/bin/env python3
"""\
`pybers show`, run the way a person or an agent at a command line runs it.

`20-formula-shapes` holds `Table 1` on each of its two sheets and `Table 2` on the
first alone, and its `A11` holds `=SUM(A1:A10)`. `81-control-formats` holds a cell
for each control, a slider in `A1` and a pop-up menu in `I1`.

UPDATES
2026-11-03  A selector read by its positions, each match printed as it prints
            alone, a document in full, and a table's headers, for PYB-223.
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
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import pybers
from conftest import copyDocument, findDocumentPath, listShownFields, renderPlain
from pybers.cli._app import app
from pybers.cli.show import (
    formatCell,
    formatControl,
    formatFormat,
    formatSheet,
    formatTable,
)

runner: CliRunner = CliRunner()

shapesPath: Path = findDocumentPath("20-formula-shapes")
controlsPath: Path = findDocumentPath("81-control-formats")


def runShowCommand(*arguments: str | Path) -> Result:
    """Return what `pybers show` does with these arguments."""
    return runner.invoke(app, ["show", *(str(each) for each in arguments)])


def findLines(result: Result, label: str) -> list[str]:
    """Return every field of a result under a label, as `Label: value`."""
    return [f"{each}: {value}" for each, value in listShownFields(result.stdout)
            if each == label]


def readFingerprint(path: Path) -> tuple[tuple[str, str, int], ...]:
    """Return every file of a document with its digest and modification time."""
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    return tuple(
        (str(each), hashlib.sha256(each.read_bytes()).hexdigest(),
         each.stat().st_mtime_ns)
        for each in files if each.is_file()
    )


def testADocumentShowsItsLocaleThenEachSheetInFull() -> None:
    result = runShowCommand(shapesPath)
    assert result.exit_code == 0
    assert result.stdout.splitlines()[:5] == [
        "Locale: en_US", "", "Sheet: Sheet 1  2 tables", "",
        "  Table: Sheet 1::Table 1  12 rows × 8 columns  26 cells",
    ]
    assert findLines(result, "Sheet") == [
        "Sheet: Sheet 1  2 tables", "Sheet: Sheet 2  1 table",
    ]
    assert len(findLines(result, "Cell")) == sum(
        len(table.cells) for sheet in pybers.open(shapesPath).sheets
        for table in sheet.tables
    )


def testACellFoldsItsFieldsOntoLinesUnderIt() -> None:
    result = runShowCommand(shapesPath, "Sheet 1::Table 1::A11")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Cell: Sheet 1::Table 1::A11",
        "  Value: 55   Kind: number   Formula text: =SUM(A1:A10)   Value cached: yes",
        "  Format: number (automatic)   Control: none",
        "  Unrecognized type code: none",
    ]


def testACellsFieldsFollowTheNamesAndOrderOfItsJsonForm() -> None:
    form = json.loads(pybers.formatJsonForm(
        pybers.open(shapesPath).sheet("Sheet 1").table("Table 1").cell("A11")
    ))["table"]["cells"][0]
    keys = [key for key in form if key not in ("address", "formula")]
    index = keys.index("presentation")
    keys[index:index + 1] = list(form["presentation"])
    expected = [re.sub(r"(?<!^)(?=[A-Z])", " ", key).capitalize() for key in keys]
    fields = listShownFields(runShowCommand(shapesPath, "Sheet 1::Table 1::A11").stdout)
    assert [label for label, _ in fields[1:]] == expected


@pytest.mark.parametrize(("address", "control"), [
    ("A1", "slider (minimum 0, maximum 200, increment 5)"),
    ("I1", "pop-up-menu (items ['Item 1', 'Item 2', 'Item 3'], "
           "starts with first item no)"),
    ("J1", "star-rating"),
])
def testAControlShowsEverySettingItHolds(address: str, control: str) -> None:
    result = runShowCommand(controlsPath, f"::Table 1::{address}")
    assert findLines(result, "Control") == [f"Control: {control}"]


def testAControlsSettingsAreNamedAndOrderedAsItsJsonForm() -> None:
    control = pybers.open(controlsPath).table("Table 1").cell("I1").presentation.control
    family, *keys = json.loads(pybers.formatJsonForm(control))
    line = findLines(runShowCommand(controlsPath, "::Table 1::I1"), "Control")[0]
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


def listPresentations() -> list[pybers.CellPresentation]:
    """Return how each cell of the format documents shows its value."""
    return [cell.presentation for stem in formatStems
            for _, _, cell in pybers.open(findDocumentPath(stem)).cellsIterate()]


def testEveryFormatShowsAsTheTextFormItReadsBackFrom() -> None:
    for presentation in listPresentations():
        shown = presentation.format
        line = formatFormat(shown)
        if shown is None:
            assert line == "none"
        elif isinstance(shown, pybers.CellFormatUnknown):
            assert line.startswith("unknown; format-type: ")
        else:
            assert pybers.parseCellFormat(line) == shown, line


def testEveryControlShowsEachSettingOfItsJsonForm() -> None:
    for presentation in listPresentations():
        subject, line = presentation.control, formatControl(presentation.control)
        tree = json.loads(pybers.formatJsonForm(subject))
        if not isinstance(tree, dict):
            assert line == ("none" if tree is None else str(tree)), line
            continue
        family, *settings = tree.values()
        assert line.startswith(str(family)), line
        found = [line.index(f"{re.sub(r'(?<!^)(?=[A-Z])', ' ', key).lower()} ")
                 for key in list(tree)[1:]]
        assert found == sorted(found) and len(found) == len(settings), line


def testATableShowsItsSizeAndCellCountOnOneLineThenEachCell() -> None:
    result = runShowCommand(shapesPath, "*::Table 2")
    assert result.stdout.splitlines()[:3] == [
        "Table: Sheet 1::Table 2  10 rows × 5 columns  1 cell",
        "",
        "  Cell: Sheet 1::Table 2::A1",
    ]


def testATablesBandsShowWhenItHasThem() -> None:
    table = pybers.create("en_US").sheet().tableAdd("Headers", 4, 3)
    table.headersSet(headerRows=1, footerRows=2)
    assert renderPlain(formatTable(table)).splitlines() == [
        "Table: Sheet 1::Headers  4 rows × 3 columns  1 header row, 2 footer rows",
    ]


def testATableListsEachOfItsMerges() -> None:
    result = runShowCommand(findDocumentPath("22-merge-2x2"), "*::Table 1")
    assert result.stdout.splitlines()[0] == (
        "Table: Sheet 1::Table 1  2 rows × 13 columns  "
        "merges A1:B1, C1:D1, E1:F1, G1:H1, I1:J1  18 cells"
    )


def testASheetHoldingNoTablesShowsItsNameAlone() -> None:
    printed = renderPlain(formatSheet(pybers.Sheet(name="Empty")))
    assert printed.splitlines() == ["Sheet: Empty"]


def testAFormatASaveHasNotChosenReadsUnknown() -> None:
    cell = pybers.open(shapesPath).sheet("Sheet 1").table("Table 1").cell("A1")
    cell.value = "text"
    assert cell.presentation.format == pybers.CellFormatAutomatic()
    shown = listShownFields(renderPlain(formatCell(cell)))
    assert ("Format", "unknown (automatic)") in shown


def testASheetShowsEachOfItsTablesIndentedUnderIt() -> None:
    result = runShowCommand(shapesPath, "Sheet 1")
    assert result.stdout.splitlines()[:3] == [
        "Sheet: Sheet 1  2 tables", "",
        "  Table: Sheet 1::Table 1  12 rows × 8 columns  26 cells",
    ]
    assert [line.split("  ")[1] for line in result.stdout.splitlines()
            if line.startswith("  Table: ")] == [
        "Table: Sheet 1::Table 1", "Table: Sheet 1::Table 2",
    ]


def testARangeShowsOnlyTheCellsWithinIt() -> None:
    result = runShowCommand(shapesPath, "Sheet 1::Table 1::A1:C3")
    assert result.stdout.splitlines()[0] == "Range: Sheet 1::Table 1::A1:C3  3 cells"
    assert findLines(result, "Cell") == [
        "Cell: Sheet 1::Table 1::A1",
        "Cell: Sheet 1::Table 1::A2",
        "Cell: Sheet 1::Table 1::A3",
    ]


def testARangeHoldingNothingShowsItsNameAlone() -> None:
    result = runShowCommand(shapesPath, "::Table 2::B2:C4")
    assert result.stdout.splitlines() == ["Range: Sheet 1::Table 2::B2:C4"]


@pytest.mark.parametrize(("selector", "part"), [
    (None, lambda document: document),
    ("Sheet 1", lambda document: [document.sheet("Sheet 1")]),
    ("*::Table 2", lambda document: [document.table("Table 2")]),
    ("Sheet 1::Table 1::A11", lambda document: [
        document.sheet("Sheet 1").table("Table 1").cell("A11")
    ]),
    ("Sheet 1::Table 1::A1:C3, Sheet 2", lambda document: [
        (document.sheet("Sheet 1").table("Table 1"), pybers.CellRange.parse("A1:C3")),
        document.sheet("Sheet 2"),
    ]),
    ("Q*", lambda document: []),
])
def testJsonIsTheFormTheLibraryWritesForWhatIsSelected(
    selector: str | None, part: Callable[[pybers.Document], object]
) -> None:
    expected = pybers.formatJsonForm(part(pybers.open(shapesPath)))
    arguments = [shapesPath] if selector is None else [shapesPath, selector]
    result = runShowCommand(*arguments, "--format", "json")
    assert result.exit_code == 0
    assert result.stdout == expected + "\n"


def testJsonOfSeveralPartsReadsBackAsEachPart() -> None:
    result = runShowCommand(shapesPath, "::A1, Sheet 2", "--format", "json")
    parts = pybers.parseJsonForm(result.stdout)
    assert isinstance(parts, list)
    assert [type(each).__name__ for each in parts] == ["Cell", "Cell", "Cell", "Sheet"]


def testSeveralMatchesEachPrintAsTheyPrintAlone() -> None:
    together = runShowCommand(shapesPath, "*::Table 2, ::A11").stdout
    alone = [runShowCommand(shapesPath, each).stdout
             for each in ("*::Table 2", "::A11")]
    assert together == "\n".join(alone)


def testAPatternMatchingNothingPrintsNothing() -> None:
    result = runShowCommand(shapesPath, "Q*")
    assert result.exit_code == 0
    assert result.stdout == ""


def testASelectorNamingNothingIsRefusedWithWhatTheDocumentHolds() -> None:
    result = runShowCommand(shapesPath, "Ledger")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        "pybers show: No sheet in this document is named 'Ledger'. The sheets are "
        "'Sheet 1', 'Sheet 2'.",
    ]


def testAMalformedSelectorIsRefusedAtTheColumnItGoesWrong() -> None:
    result = runShowCommand(shapesPath, "Sheet 1::Table 1[kind=nmber]")
    assert result.exit_code == 1
    assert result.stderr.startswith(
        "pybers show: `Sheet 1::Table 1[kind=nmber]`, column 17: `nmber` is no "
        "value of `[kind]`. It takes empty, number,"
    )


def testACellOutsideItsTableIsRefusedWithTheTablesSize() -> None:
    result = runShowCommand(shapesPath, "::Table 2::F1")
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
    "Sheet 1", "*::Table 2", "::Table 2::B2:C4", "::Table 2::B3", "Ledger", "::A1",
])
def testShowNeverWritesTheDocument(tmp_path: Path, selector: str) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    before = readFingerprint(working)
    runShowCommand(working, selector)
    runShowCommand(working, selector, "--format", "json")
    assert readFingerprint(working) == before
    assert sorted(tmp_path.iterdir()) == [working]


def testTheHelpShowsAConditionInItsExampleSelector() -> None:
    result = runner.invoke(app, ["show", "--help"], terminal_width=200)
    assert "[kind=number]" in result.stdout

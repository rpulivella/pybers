#!/usr/bin/env python3
"""\
`pybers check`, run the way a person reporting a bug runs it.

UPDATES
2026-10-07  Written for PYB-169.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

import io
import os
import runpy
import sys
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from rich.console import Console
from rich.text import Text
from typer.testing import CliRunner

import pybers
from conftest import findDocumentPath
from pybers._persistence import readPackage, writePackage
from pybers.cli import main
from pybers.cli._app import HelpSection, app
from pybers.cli._console import theme
from pybers.cli.check import formatCheck

baselinePath: Path = findDocumentPath("00-baseline")
recordsPath: Path = findDocumentPath("22e-merge-imported")
runner: CliRunner = CliRunner()

reportLabels: tuple[str, ...] = (
    "pybers: ",
    "Python: ",
    "protobuf: ",
    "OS: ",
    "Saved with: ",
    "Readable: ",
    "Untested archive types: ",
    "Unrecognized cell types: ",
)


def listDocumentWords(path: Path) -> set[str]:
    """Return every sheet name, table name and text value a document holds."""
    document = pybers.open(path)
    words = {sheet.name for sheet in document.sheets}
    for sheet in document.sheets:
        for table in sheet.tables:
            words.add(table.name)
            words.update(
                cell.value for cell in table.cells.values()
                if isinstance(cell.value, str)
            )
    return words


def testCheckReportsEveryFactForADocumentPybersOpens() -> None:
    result = runner.invoke(app, ["check", str(baselinePath)])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert [line.split(": ")[0] + ": " for line in lines] == list(reportLabels)
    assert "Readable: yes" in lines
    assert "Saved with: Numbers 15.3.1 (build 7050.1.1-2)" in lines


@pytest.mark.parametrize(
    "stem", ["57-structure-refusals-base", "42-table-titles-captions"]
)
def testCheckOutputHoldsNothingFromTheDocument(stem: str) -> None:
    path = findDocumentPath(stem)
    result = runner.invoke(app, ["check", str(path)])
    assert result.exit_code == 0
    # Two- and three-letter cell text such as "lo" occurs inside ordinary words.
    words = {word for word in listDocumentWords(path) if len(word.strip()) > 3}
    assert words
    assert not [word for word in words if word in result.output]
    assert stem not in result.output


def testCheckExitsNonzeroWhenPybersCannotOpenTheDocument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = pybers.CheckFailure("ReadError", "Expected one archive.", ("x.py:1",))
    found = replace(pybers.checkDocument(baselinePath), failure=failure)
    monkeypatch.setattr(pybers, "checkDocument", lambda *_, **__: found)
    result = runner.invoke(app, ["check", str(baselinePath)])
    assert result.exit_code == 1
    assert "Readable: no, ReadError: Expected one archive." in result.stdout
    assert "  at x.py:1" in result.stdout


def findAbsentPath(tmp_path: Path) -> Path:
    """Return a path nothing exists at."""
    return tmp_path / "absent.numbers"


def findDirectoryPath(tmp_path: Path) -> Path:
    """Return a directory rather than a file."""
    return tmp_path


def writeTextFile(tmp_path: Path) -> Path:
    """Write a plain text file named as a document."""
    path = tmp_path / "notes.numbers"
    path.write_text("notes")
    return path


def writeZipWithoutDocument(tmp_path: Path) -> Path:
    """Write a zip holding no IWA member, as an exported spreadsheet would be."""
    path = tmp_path / "sheet.numbers"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return path


@pytest.mark.parametrize(
    ("prepare", "reason"),
    [
        (findAbsentPath, "does not exist"),
        (findDirectoryPath, "is a directory"),
        (writeTextFile, "not a zip archive"),
        (writeZipWithoutDocument, "holds no Index/*.iwa member"),
    ],
)
def testCheckRefusesAFileItCannotCheckByNameAndReason(
    tmp_path: Path, prepare: Callable[[Path], Path], reason: str
) -> None:
    path = prepare(tmp_path)
    result = runner.invoke(app, ["check", str(path)])
    assert result.exit_code == 1
    assert str(path) in result.stderr
    assert reason in result.stderr
    assert "Traceback" not in result.output
    assert isinstance(result.exception, SystemExit)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def testCheckRefusesAnUnreadableFileByNameAndReason(tmp_path: Path) -> None:
    locked = tmp_path / "locked.numbers"
    locked.write_bytes(baselinePath.read_bytes())
    locked.chmod(0)
    try:
        result = runner.invoke(app, ["check", str(locked)])
    finally:
        locked.chmod(0o600)
    assert result.exit_code == 1
    assert f"{locked} could not be read: Permission denied." in result.stderr


def testPythonDashMPybersRunsTheSameCommand(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["pybers", "check", str(baselinePath)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_module("pybers", run_name="__main__")
    assert exited.value.code == 0
    assert "Readable: yes" in capsys.readouterr().out


def testTheCommandWithoutTyperSaysWhichExtraInstallsIt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "typer", None)
    monkeypatch.delitem(sys.modules, "pybers.cli._app")
    monkeypatch.delitem(sys.modules, "pybers.cli.check")
    with pytest.raises(SystemExit) as exited:
        main()
    assert "pip install 'pybers[cli]'" in str(exited.value.code)


def testHelpListsCheck() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout


def testNamesListTheDocumentsSheetsAndTables() -> None:
    result = runner.invoke(app, ["check", "--names", str(recordsPath)])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert "Sheet1" in lines
    assert "└ Table 1: 10 rows, 7 columns" in lines


@pytest.mark.parametrize(
    ("arguments", "environment"),
    [(["--debug"], {}), ([], {"PYBERS_DEBUG": "1"})],
    ids=["option", "environment"],
)
def testDebugRaisesAPybersErrorWithItsTraceback(
    tmp_path: Path, arguments: list[str], environment: dict[str, str]
) -> None:
    result = runner.invoke(
        app, [*arguments, "check", str(tmp_path / "absent.numbers")], env=environment
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, pybers.PybersError)


def testDebugRaisesTheFailureAReportDescribes(tmp_path: Path) -> None:
    package = readPackage(baselinePath)
    for iwaFile in package.iwaFiles:
        iwaFile.archives[:] = [
            archive for archive in iwaFile.archives if archive.identifier != 1
        ]
        iwaFile.modified = True
    broken = tmp_path / "broken.numbers"
    writePackage(package, broken)
    result = runner.invoke(app, ["--debug", "check", str(broken)])
    assert "Readable: no" in result.stdout
    assert isinstance(result.exception, pybers.ReadError)


@pytest.mark.parametrize("arguments", [["--help"], ["check", "--help"], ["chek"]])
def testHelpAndUsageErrorsDrawNoBorders(arguments: list[str]) -> None:
    output = runner.invoke(app, arguments).output
    assert output.strip()
    assert not set(output) & set("╭╮╰╯│─━┃┏┓┗┛")


def renderPlain(renderable: object) -> str:
    """Return what a renderable prints on a terminal without color."""
    buffer = io.StringIO()
    Console(file=buffer, width=100, no_color=True, theme=theme).print(renderable)
    return buffer.getvalue()


def testANameInBracketsPrintsAsWritten() -> None:
    found = pybers.checkDocument(baselinePath)
    table = pybers.CheckTable("[draft]", 1, 1)
    names = pybers.CheckNames((pybers.CheckSheet("[bold]Q3", (table,)),), ())
    printed = renderPlain(formatCheck(replace(found, names=names)))
    assert "\n[bold]Q3\n" in printed
    assert "└ [draft]: 1 rows, 1 columns" in printed


def testUnrecognizedCellsHangUnderTheirSheetAndTable() -> None:
    found = pybers.checkDocument(baselinePath)
    cells = (
        pybers.CheckCell("Sheet1", "Table 1", "B7", 4),
        pybers.CheckCell("Sheet1", "Table 1", "C9", 4),
    )
    names = pybers.CheckNames((), cells)
    printed = renderPlain(formatCheck(replace(found, names=names)))
    assert printed.endswith(
        "Unrecognized cells:\nSheet1\n└ Table 1\n  ├ B7: cell type 4\n"
        "  └ C9: cell type 4\n"
    )


@pytest.mark.parametrize(
    "section",
    [
        HelpSection("body", title="Options", border_style="dim"),
        HelpSection(renderable="body", title=Text("Options"), subtitle="x"),
        HelpSection("body"),
    ],
    ids=["as-typer-calls-it", "keywords-and-text-title", "no-title"],
)
def testAHelpSectionRendersHoweverTyperCallsIt(section: HelpSection) -> None:
    buffer = io.StringIO()
    Console(width=40, file=buffer).print(section)
    assert "body" in buffer.getvalue()

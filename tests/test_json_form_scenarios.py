#!/usr/bin/env python3
"""\
The JSON form as each consumer meets it: a script author's few lines, and a command's.

UPDATES
2026-10-24  Written for PYB-259.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

import json
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

import pybers
from conftest import copyDocument, findDocumentPath
from pybers.cli._app import app

runner: CliRunner = CliRunner()


def testAScriptReadsATablesNumbersExactlyFromItsJsonForm() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    table = document.sheet("Sheet 1").table("Table 1")
    form = json.loads(pybers.formatJsonForm(table),
                      parse_float=Decimal, parse_int=Decimal)
    sums = [cell for cell in form["table"]["cells"] if cell["formulaText"]]
    assert sums[0]["value"] == table.cell(sums[0]["address"]).value
    assert pybers.parseJsonForm(pybers.formatJsonForm(table)) == table


def testAScriptSavesAWholeDocumentAsJsonAndReadsItBack(tmp_path: Path) -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    saved = tmp_path / "document.json"
    saved.write_text(pybers.formatJsonForm(document))
    assert pybers.parseJsonForm(saved.read_text()) == document


def testACommandsJsonIsTheLibrarysJsonForm(tmp_path: Path) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    result = runner.invoke(app, [
        "set", str(working), "Table 2::B2", "1234567890123456789012345678901234",
        "--preview", "--format", "json",
    ])
    printed = json.loads(result.stdout, parse_float=Decimal, parse_int=Decimal)
    assert printed["valueAfter"] == Decimal("1234567890123456789012345678901234")
    change = pybers.open(working).cellSet(
        "Table 2::B2", Decimal("1234567890123456789012345678901234"), preview=True
    )
    assert result.stdout.rstrip("\n") == pybers.formatJsonForm(change)

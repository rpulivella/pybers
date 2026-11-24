#!/usr/bin/env python3
"""\
Rows of the same fields as a grid: a header, padded columns never cut, numbers right.

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

import io

from rich.console import Console

from conftest import renderPlain
from pybers.cli._report import GridColumn, formatGrid

columns = (
    GridColumn("Name"), GridColumn("Weight", numeric=True), GridColumn("Slant", "code")
)


def testGridPadsEachColumnToItsLongestValueAndAlignsNumbersRight() -> None:
    shown = formatGrid(columns, [("Regular", "400", "normal"), ("Bold", "700", "x")])
    assert renderPlain(shown).splitlines() == [
        "Name     Weight  Slant",
        "Regular     400  normal",
        "Bold        700  x",
    ]


def testGridNeverCutsAValueWiderThanTheTerminal() -> None:
    longest = "AvenirNextCondensed-UltraLightItalic" * 4
    buffer = io.StringIO()
    # Soft-wrapping, as `pybers.cli._console.console` prints a command's result.
    Console(file=buffer, width=40, soft_wrap=True).print(
        formatGrid(columns, [(longest, "275", "italic")])
    )
    assert f"{longest}     275  italic" in buffer.getvalue()


def testGridStylesTheHeaderAsLabelsAndEachColumnByItsRole() -> None:
    header, row = formatGrid(columns, [("Bold", "700", "normal")]).renderables
    assert {span.style for span in header.spans} == {"label"}
    assert [span.style for span in row.spans] == ["value", "value", "code"]


def testGroupedColumnShowsAValueOnceForTheRowsSharingIt() -> None:
    grouped = (GridColumn("Family", grouped=True), GridColumn("Name"))
    rows = [("Avenir", "Regular"), ("Avenir", "Bold"), ("Skia", "Bold")]
    assert renderPlain(formatGrid(grouped, rows)).splitlines() == [
        "Family  Name",
        "Avenir  Regular",
        "        Bold",
        "Skia    Bold",
    ]


def testGridOfNoRowsIsItsHeader() -> None:
    assert renderPlain(formatGrid(columns, [])).splitlines() == [
        "Name  Weight  Slant",
    ]

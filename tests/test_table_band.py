#!/usr/bin/env python3
"""\
A table's banded rows, read as Numbers stores them and set as its checkbox sets them.

`102-bands-base` holds a table of two header rows, two header columns, five body rows
and a footer row, its columns holding no fill, a stated No Fill, a color, a color
then No Fill and a gradient, and `102b-bands-on` the same with Alternating Row Color
turned on. Which fill each cell displays is read from the preview Numbers saved.
`103c-bands-translucent` holds a band recolored by hand to `#ff3b30` at half opacity,
and `104b-bands-merged-on` merges across banded and unbanded rows.

UPDATES
2026-11-18  Written for PYB-267.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/18"

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import CliRunner

import pybers
from conftest import copyDocument, findDocumentPath, readOverrides
from pybers import Color, TableBand
from pybers.cli._app import app
from pybers.style.fills import Fill, FillGradient, FillImage, FillNone
from pybers.table.tablestyle import TableStyleError, bandGray
from pybers.table.tablestyletext import formatTableStyle, parseTableStyle

yellow = Color.parse("#ffd60aff")
red = Color.parse("#ff3b30ff")
translucentRed = Color(red.colorSpace, red.components, Decimal("0.5"))


def readBand(stem: str, table: str) -> TableBand:
    """Return the band one table of a test document draws."""
    return pybers.open(findDocumentPath(stem)).table(table).tableStyle.bandedRows


@pytest.mark.parametrize(("stem", "table", "band"), [
    ("102-bands-base", "Sheet 1::Table 1", TableBand(False, bandGray)),
    ("102b-bands-on", "Sheet 1::Table 1", TableBand(True, bandGray)),
    ("102b-bands-on", "No headers::Table 1", TableBand(True, bandGray)),
    ("70-retirement-template-15-4", "Data", TableBand(True, Color.parse("#f0ebe2ff"))),
    ("70-retirement-template-15-4", "Life Plans", TableBand(
        False, Color.parse("#f0ebe2ff"),
    )),
])
def testABandReadsAsEachDocumentStatesIt(
    stem: str, table: str, band: TableBand
) -> None:
    assert readBand(stem, table) == band


def testATranslucentBandReadsWithItsAlpha() -> None:
    band = readBand("103c-bands-translucent", "Table 1")
    assert band == TableBand(True, translucentRed)


def testRecoloringABandWritesWhatNumbersWrote(tmp_path: Path) -> None:
    path = copyDocument("103b-bands-one-header-on", tmp_path)
    document = pybers.open(path)
    document.table().tableStyleSet(bandedRows=TableBand(True, translucentRed))
    document.save()
    made = findDocumentPath("103c-bands-translucent")
    assert readOverrides(path, "Table 1") == readOverrides(made, "Table 1")


def testACreatedTableStartsUnbandedWithTheBlankThemesGray() -> None:
    table = pybers.create("en_US").sheet().tableAdd("Bands", rows=4, cols=2)
    assert table.tableStyle.bandedRows == TableBand(False, bandGray)


def testTurningBandingOnStatesOnlyThatAsNumbersDoes(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Bands", rows=4, cols=2)
    table.tableStyleSet(bandedRows=TableBand(True, bandGray))
    document.save(tmp_path / "on.numbers")
    assert readOverrides(tmp_path / "on.numbers", "Bands") == ["banded_rows"]


def testABandKeepsItsColorThroughASaveAndWhenTurnedOff(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Bands", rows=4, cols=2)
    table.tableStyleSet(bandedRows=TableBand(True, yellow))
    table.tableStyleSet(bandedRows=TableBand(False, yellow))
    document.save(tmp_path / "off.numbers")
    reread = pybers.open(tmp_path / "off.numbers").table("Bands")
    assert reread.tableStyle.bandedRows == TableBand(False, yellow)


def testSettingTheBandATableHoldsReportsNoChange() -> None:
    table = pybers.open(findDocumentPath("102b-bands-on")).table("Sheet 1::Table 1")
    assert not table.tableStyleSet(bandedRows=TableBand(True, bandGray)).changed


@pytest.mark.parametrize(("fill", "named"), [
    (FillGradient(), "A gradient band"), (FillImage(), "An image band"),
    (FillNone(), "A band with no fill"),
])
def testABandOtherThanAColorIsRefusedNamingItsType(fill: Fill, named: str) -> None:
    table = pybers.create("en_US").sheet().tableAdd("Bands", rows=4, cols=2)
    with pytest.raises(TableStyleError, match=f"{named} is not one Numbers draws"):
        table.tableStyleSet(bandedRows=TableBand(True, fill))
    assert table.tableStyle.bandedRows == TableBand(False, bandGray)


def testABandThatIsNoBandIsRefused() -> None:
    table = pybers.create("en_US").sheet().tableAdd("Bands", rows=4, cols=2)
    with pytest.raises(TableStyleError, match="is not a TableBand"):
        table.tableStyleSet(bandedRows=True)


@pytest.mark.parametrize(("text", "band"), [
    ("banded-rows: #ffd60aff", TableBand(True, yellow)),
    ("banded-rows: none", TableBand(False, bandGray)),
    ("banded-rows: hidden #ffd60aff", TableBand(False, yellow)),
    ("banded-rows-background: #ffd60aff", TableBand(False, yellow)),
])
def testABandReadsFromItsDeclaration(text: str, band: TableBand) -> None:
    base = pybers.create("en_US").sheet().tableAdd("Bands", rows=4, cols=2).tableStyle
    assert parseTableStyle(text, base).bandedRows == band


@pytest.mark.parametrize("band", [
    TableBand(True, yellow), TableBand(False, yellow), TableBand(True, FillGradient()),
])
def testABandPrintsAsADeclarationThatReadsBack(band: TableBand) -> None:
    base = pybers.create("en_US").sheet().tableAdd("Bands", rows=4, cols=2).tableStyle
    banded = replace(base, bandedRows=band)
    declaration = formatTableStyle(banded)[-1]
    assert parseTableStyle(declaration, banded).bandedRows == band


@pytest.mark.parametrize(("address", "fill"), [
    ("C3", FillNone()),
    ("C4", bandGray),
    ("C8", FillNone()),
    ("D4", "own color"),
    ("E4", bandGray),
    ("F4", FillGradient()),
    ("B4", FillNone()),
    ("A4", "header column gray"),
    ("C1", "header row gray"),
])
def testACellShowsTheFillNumbersDrewForIt(address: str, fill: Fill | str) -> None:
    table = pybers.open(findDocumentPath("102b-bands-on")).table("Sheet 1::Table 1")
    shown = table.cellFillComputed(address)
    if fill == "own color":
        cell = table.cell(address)
        assert cell.cellStyle is not None and shown == cell.cellStyle.background
    elif isinstance(fill, str):
        assert isinstance(shown, Color) and shown != bandGray
    else:
        assert shown == fill


@pytest.mark.parametrize(("address", "banded"), [
    ("B2", False), ("B3", False), ("C3", True), ("C4", True),
    ("D4", False), ("D5", False), ("D6", False), ("E5", True), ("F5", True),
])
def testAMergeShowsItsAnchorsBandAcrossEveryRow(address: str, banded: bool) -> None:
    table = pybers.open(findDocumentPath("104b-bands-merged-on")).table()
    assert table.cellFillComputed(address) == (bandGray if banded else FillNone())


def testTheBandCountsFromTheFirstBodyRow() -> None:
    table = pybers.open(findDocumentPath("103b-bands-one-header-on")).table()
    shown = [table.cellFillComputed(f"B{row}") for row in range(2, 7)]
    assert shown == [FillNone(), bandGray, FillNone(), bandGray, FillNone()]


def testAScriptAuthorBandsAReportsRows(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    table = document.sheet().tableAdd("Report", rows=8, cols=3)
    table.tableStyleSet(bandedRows=pybers.TableBand(True, red))
    document.save(tmp_path / "report.numbers")

    reread = pybers.open(tmp_path / "report.numbers").table("Report")
    assert reread.cellFillComputed("A2") == red
    assert reread.tableStyle.bandedRows.visible


def testACommandBandsATableAndShowsIt(tmp_path: Path) -> None:
    path = str(copyDocument("102-bands-base", tmp_path))
    runner = CliRunner()

    runner.invoke(app, ["set", path, "Sheet 1::Table 1",
                        "--table-style", "banded-rows: #ffd60aff"])
    shown = runner.invoke(app, ["show", path, "Sheet 1::Table 1"]).stdout

    assert "banded-rows: #ffd60aff" in shown


@pytest.mark.parametrize(("declaration", "named"), [
    ("banded-rows: gradient", "A gradient band"),
    ("banded-rows: hidden image", "An image band"),
    ("banded-rows-background: none", "A band with no fill"),
])
def testACommandRefusesABandNumbersCannotDraw(
    declaration: str, named: str, tmp_path: Path
) -> None:
    path = copyDocument("102-bands-base", tmp_path)
    result = CliRunner().invoke(app, [
        "set", str(path), "Sheet 1::Table 1", "--table-style", declaration,
    ])
    assert result.stderr == (
        f"pybers set: {named} is not one Numbers draws, since it bands rows with a "
        "color alone. Give the band a color.\n"
    )


def testACommandSettingTheBandATableHoldsWritesNothing(tmp_path: Path) -> None:
    path = copyDocument("102b-bands-on", tmp_path)
    before = path.read_bytes()
    result = CliRunner().invoke(app, [
        "set", str(path), "Sheet 1::Table 1", "--table-style",
        "banded-rows: color(srgb 0.9601849 0.9601849 0.9601849 / 1)",
    ])
    assert "Nothing written: already set" in result.stderr
    assert path.read_bytes() == before

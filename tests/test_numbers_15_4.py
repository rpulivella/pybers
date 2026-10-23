#!/usr/bin/env python3
"""\
Numbers 15.4: its added functions, and the stylesheet slot it added.

UPDATES
2026-10-22  The golden's writes and comparison moved to the golden builders, for
            PYB-255.
2026-10-13  Written for PYB-139.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/13"

import shutil
from decimal import Decimal
from pathlib import Path

from golden.builders import addedFunctionFormulas

import pybers
from conftest import findDocumentPath
from pybers._generated import TSSArchives_pb2 as tss
from pybers._persistence import NumbersPackage, readPackage, writePackage
from pybers._persistence.types import archiveTypeIds

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"
goldenName: str = "20-functions-added-in-15-4-by-pybers.numbers"
measurementStem: str = "69-functions-added-in-15-4"

def testTheAddedFunctionsGoldenHoldsEveryCall() -> None:
    table = pybers.open(goldenDirectory / goldenName).sheet("Sheet 1").table("Table 2")
    assert {
        address: table.cell(address).formulaText for address, _ in addedFunctionFormulas
    } == dict(addedFunctionFormulas)


# What Numbers 15.4 calculated for each call when it saved the golden.
calculatedByNumbers: dict[str, Decimal | bool] = {
    "B1": Decimal("0.785398163397448"), "B2": Decimal("0.549306144334055"),
    "B3": Decimal("0.642092615934331"), "B4": Decimal("1.31303528549933"),
    "B5": Decimal("1.18839510577812"), "B6": Decimal("0.850918128239322"),
    "B7": Decimal("1.85081571768093"), "B8": Decimal("0.648054273663885"),
    "B9": True, "C1": Decimal("20"), "C2": Decimal("24"),
    "C3": Decimal("0.398942280401433"), "C4": Decimal("0.549306144334055"),
    "C5": Decimal("0.462117157260010"), "C6": Decimal("9"), "C7": Decimal("285"),
    "C8": Decimal("1"), "C9": Decimal("1"),
}


def openMeasuredTable() -> pybers.Table:
    """Return the table Numbers 15.4 calculated and saved."""
    document = pybers.open(findDocumentPath(measurementStem))
    return document.sheet("Sheet 1").table("Table 2")


def testNumbersOwnSaveReadsEveryAddedFunctionByName() -> None:
    table = openMeasuredTable()
    assert {
        address: table.cell(address).formulaText for address, _ in addedFunctionFormulas
    } == dict(addedFunctionFormulas)


def testNumbersOwnSaveHoldsTheValueEachAddedFunctionCalculated() -> None:
    table = openMeasuredTable()
    assert {
        address: table.cell(address).value for address, _ in addedFunctionFormulas
    } == calculatedByNumbers


def readStylesheet(package: NumbersPackage) -> tuple[int, tss.StylesheetArchive]:
    """Return the document stylesheet's archive identifier and its parsed body."""
    for iwaFile in package.iwaFiles:
        for archive in iwaFile.archives:
            for message in archive.messages:
                if message.typeId == archiveTypeIds[tss.StylesheetArchive]:
                    stylesheet = tss.StylesheetArchive()
                    stylesheet.ParseFromString(message.data)
                    return archive.identifier, stylesheet
    raise AssertionError("the package holds no stylesheet")


def fillStyleSlotFor15Point4(path: Path) -> bytes:
    """Fill the 15.4 slot with the 10.1 slot's styles, as no Numbers save yet has."""
    package = readPackage(path)
    identifier, stylesheet = readStylesheet(package)
    stylesheet.styles_for_15_4.CopyFrom(stylesheet.styles_for_10_1)
    for iwaFile in package.iwaFiles:
        if any(archive.identifier == identifier for archive in iwaFile.archives):
            iwaFile.messageReplace(identifier, 0, stylesheet.SerializeToString())
    writePackage(package, path)
    return stylesheet.styles_for_15_4.SerializeToString()


def testTheStyleSlotNumbers15Point4AddedSurvivesAPybersSave(tmp_path: Path) -> None:
    working = Path(
        shutil.copy(findDocumentPath("00-baseline"), tmp_path / "00.numbers")
    )
    filled = fillStyleSlotFor15Point4(working)
    document = pybers.open(working)
    document.sheets[0].tables[0].cell("A1").value = Decimal("7")
    document.save()
    _, stylesheet = readStylesheet(readPackage(working))
    assert stylesheet.HasField("styles_for_15_4")
    assert stylesheet.styles_for_15_4.SerializeToString() == filled

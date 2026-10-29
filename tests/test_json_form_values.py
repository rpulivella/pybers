#!/usr/bin/env python3
"""\
The rule each value follows in the JSON form, and what reading one refuses.

UPDATES
2026-10-28  Version 2, whose document names its locale, for PYB-272.
2026-10-27  A range narrowing a table may name it, and not another, for
            PYB-260.
2026-10-24  Written for PYB-259, taking the value rules `test_cli_formats` held.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

import ast
import datetime
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import pybers
from conftest import allDocuments, findDocumentPath
from pybers.interchange._jsontext import writeJsonText
from pybers.interchange._tree import JsonFormDefinitionError

cliDirectory: Path = Path(pybers.__file__).parent / "cli"

# decimal128's extremes, a full 34-digit coefficient, and the signs and scales a
# binary float would lose.
exactNumbers: tuple[str, ...] = (
    "9.999999999999999999999999999999999E+6144",
    "-9.999999999999999999999999999999999E+6144",
    "1E-6176", "-1E-6176", "0E-6176", "0E+6111", "-0",
    "1234567890123456789012345678901234", "0.10", "1.50", "-1234.5000",
)


def readTree(text: str) -> Any:
    """Return JSON text as a tree of Decimal numbers, as the user docs read it."""
    return json.loads(text, parse_float=Decimal, parse_int=Decimal)


def buildTable(*values: object) -> pybers.Table:
    """Return a table holding one value per row of its first column."""
    table = pybers.Table(name="Values", rowCount=len(values), colCount=1)
    for row, value in enumerate(values, start=1):
        table.cell(pybers.CellAddress(row, 1)).value = value
    return table


def readValues(table: pybers.Table) -> list[Any]:
    """Return each cell's value as the JSON form writes it, its numbers Decimal."""
    tree = readTree(pybers.formatJsonForm(table))
    return [cell["value"] for cell in tree["table"]["cells"]]


def editCell(text: str, **changes: Any) -> str:
    """Return a cell's JSON form with some of its cell's keys changed or removed."""
    tree = readTree(text)
    cell = tree["table"]["cells"][0]
    for key, value in changes.items():
        if value is None and key.startswith("drop_"):
            cell.pop(key.removeprefix("drop_"))
        else:
            cell[key] = value
    return writeJsonText(tree)


def writeFormulaCell() -> str:
    """Return the JSON form of a cell holding a formula and its cached value."""
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    return pybers.formatJsonForm(document.sheet("Sheet 1").table("Table 1").cell("A11"))


@pytest.mark.parametrize("number", exactNumbers)
def testANumberReadsBackWithItsDigitsSignAndExponent(number: str) -> None:
    [read] = readValues(buildTable(Decimal(number)))
    assert isinstance(read, Decimal)
    assert read.as_tuple() == Decimal(number).as_tuple()


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryNumberInADocumentReadsBackExactly(path: Path) -> None:
    document = pybers.open(path)
    tree = readTree(pybers.formatJsonForm(document))
    for sheet, sheetTree in zip(document.sheets, tree["document"]["sheets"],
                                strict=True):
        for table, tableTree in zip(sheet.tables, sheetTree["tables"], strict=True):
            for cellTree in tableTree["cells"]:
                value = table.cells[pybers.CellAddress.parse(cellTree["address"])].value
                read = cellTree["value"]
                if isinstance(value, pybers.CurrencyAmount):
                    value, read = value.amount, read["amount"]
                if isinstance(value, Decimal):
                    assert read.as_tuple() == value.as_tuple()


def testANumberIsABareJsonNumberNeverAString() -> None:
    assert '"value": 1.50,' in pybers.formatJsonForm(buildTable(Decimal("1.50")))


def testACurrencyAmountIsItsAmountAndItsCode() -> None:
    [read] = readValues(buildTable(pybers.CurrencyAmount(Decimal("99.50"), "CHF")))
    assert read == {"amount": Decimal("99.50"), "currency": "CHF"}
    assert read["amount"].as_tuple() == Decimal("99.50").as_tuple()


@pytest.mark.parametrize(("value", "written"), [
    (datetime.datetime(2026, 10, 24, 13, 45), "2026-10-24T13:45:00"),
    (datetime.datetime(2026, 10, 24, 13, 45, 0, 500), "2026-10-24T13:45:00.000500"),
    (datetime.timedelta(days=1, hours=2, minutes=30), "P1DT2H30M"),
    (datetime.timedelta(seconds=-0.5), "-PT0.5S"),
    (datetime.timedelta(0), "PT0S"),
    (datetime.timedelta(weeks=2, microseconds=1), "P14DT0.000001S"),
])
def testADateAndADurationAreIso8601AndReadBack(value: object, written: str) -> None:
    table = buildTable(value)
    assert readValues(table) == [written]
    readBack = pybers.parseJsonForm(pybers.formatJsonForm(table))
    assert isinstance(readBack, pybers.Table)
    assert readBack.cell("A1").value == value


def testWhatJsonPrintsForADurationIsTextSetReadsAsThatDuration() -> None:
    duration = datetime.timedelta(days=2, hours=4, milliseconds=500)
    [written] = readValues(buildTable(duration))
    assert pybers.parseCellValue(written) == duration


@pytest.mark.parametrize(
    "found", [pybers.NOT_REQUESTED, pybers.UNDETERMINED, pybers.WITHHELD]
)
def testASentinelIsWrittenAsItsName(found: object) -> None:
    assert readTree(pybers.formatJsonForm(found)) == repr(found)


def testAMappingKeyedByNumbersIsWrittenWithTextKeys() -> None:
    assert readTree(pybers.formatJsonForm(frozendict({3008: 2}))) == {
        "3008": Decimal(2)
    }


def testAFieldOutsideEqualityIsLeftOut() -> None:
    failure = pybers.CheckFailure("KeyError", pybers.WITHHELD, (), error=KeyError())
    assert readTree(pybers.formatJsonForm(failure)) == {
        "errorType": "KeyError", "message": "WITHHELD", "frames": []
    }


def testACellPositionIsWrittenAsItsText() -> None:
    assert readTree(pybers.formatJsonForm(pybers.CellAddress(3, 2))) == "B3"
    reference = pybers.CellReference.parse("Q3::$B3")
    assert readTree(pybers.formatJsonForm(reference)) == "Q3::$B3"


def testAValueWithNoJsonFormIsRefusedByName() -> None:
    with pytest.raises(JsonFormDefinitionError, match="no JSON form for complex"):
        pybers.formatJsonForm(1j)


def testNoFrontEndBuildsJsonItself() -> None:
    builders = [
        f"{path.name}:{node.lineno}"
        for path in cliDirectory.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if (isinstance(node, ast.Import) and any(
            alias.name == "json" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "json")
    ]
    assert builders == []


def testAValueCachedContradictingTheFormulaIsRefused() -> None:
    with pytest.raises(pybers.JsonFormError, match="valueCached is false"):
        pybers.parseJsonForm(editCell(writeFormulaCell(), valueCached=False))


def testAValueCachedLeftOutIsReadFromTheFormula() -> None:
    readBack = pybers.parseJsonForm(editCell(writeFormulaCell(), drop_valueCached=None))
    assert isinstance(readBack, pybers.Cell) and readBack.valueCached


def testAFormulaGivenNoValueIsHeldUncalculated() -> None:
    readBack = pybers.parseJsonForm(
        editCell(writeFormulaCell(), value=None, kind="error")
    )
    assert isinstance(readBack, pybers.Cell)
    assert (readBack.value, readBack.formulaText) == (None, "=SUM(A1:A10)")


def testFormulaTextThatDoesNotParseIsRefusedNamingTheCell() -> None:
    with pytest.raises(pybers.JsonFormError, match=r"cells\[0\]\.formulaText"):
        pybers.parseJsonForm(editCell(writeFormulaCell(), formulaText="=SUM(A1:"))


def testNodesDisagreeingWithTheTextAreRefused() -> None:
    document = pybers.open(findDocumentPath("70-retirement-template-15-4"))
    cell = next(cell for _, _, cell in document.cellsIterate()
                if cell.formula is not None
                and {32, 33} & {node.nodeType for node in cell.formula.nodes})
    with pytest.raises(pybers.JsonFormError, match="its nodes show"):
        pybers.parseJsonForm(editCell(pybers.formatJsonForm(cell), formulaText="=1"))


def testAValueOfTheWrongKindIsRefusedNamingWhatItMustBe() -> None:
    text = pybers.formatJsonForm(buildTable("words"))
    with pytest.raises(pybers.JsonFormError, match="must be a string or null"):
        pybers.parseJsonForm(editCell(text, value=5))


@pytest.mark.parametrize(("text", "refusal"), [
    ("not json", "not JSON"),
    ('{"jsonFormVersion": 1, "jsonFormVersion": 1}', "appears twice"),
    ('{"jsonFormVersion": NaN}', "no number NaN"),
    ('{"jsonFormVersion": 99, "document": {"sheets": []}}', "jsonFormVersion being 99"),
    ('{"jsonFormVersion": 2, "document": {"localeIdentifier": null, "sheets": [], '
     '"extra": 1}}', "no key 'extra'"),
    ('{"jsonFormVersion": 2, "document": {"localeIdentifier": null}}',
     "sheets is missing"),
    ('{"jsonFormVersion": 2, "document": {"sheets": []}}',
     "localeIdentifier is missing"),
])
def testTextThatIsNotTheFormIsRefusedSayingWhy(text: str, refusal: str) -> None:
    with pytest.raises(pybers.JsonFormError, match=refusal):
        pybers.parseJsonForm(text)


def testOnlyATableIsNarrowedToARange() -> None:
    sheet = pybers.Sheet(name="Sheet 1")
    with pytest.raises(pybers.JsonFormError, match="Only a table"):
        pybers.formatJsonForm(sheet, "A1:B2")


def testATableIsNarrowedToOneRangeAlone() -> None:
    with pytest.raises(pybers.JsonFormError, match="names 2"):
        pybers.formatJsonForm(buildTable(Decimal(1)), "A1, B2")


def testATableIsNarrowedByARangeNamingIt() -> None:
    table = buildTable(Decimal(1), Decimal(2))
    assert readTree(pybers.formatJsonForm(table, "Values::A2"))["extent"] == "A2"


def testATableIsNotNarrowedByARangeNamingAnother() -> None:
    with pytest.raises(pybers.ReferenceError, match="names another table"):
        pybers.formatJsonForm(buildTable(Decimal(1)), "Elsewhere::A1")


def testACellOutsideAnyTableHasNoForm() -> None:
    with pytest.raises(pybers.JsonFormError, match="belongs to no table"):
        pybers.formatJsonForm(pybers.Cell(pybers.CellAddress(1, 1)))


def testARangeHoldingACellOutsideItIsRefused() -> None:
    table = buildTable(Decimal(1), Decimal(2))
    tree = readTree(pybers.formatJsonForm(table, "A1"))
    tree["table"]["cells"].append({**tree["table"]["cells"][0], "address": "A2"})
    with pytest.raises(pybers.JsonFormError, match="outside A1"):
        pybers.parseJsonForm(writeJsonText(tree))

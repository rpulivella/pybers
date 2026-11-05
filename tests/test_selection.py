#!/usr/bin/env python3
"""\
Selecting anything in a document one way, by the selector and its one resolver.

`buildLedger` makes a document from nothing: a sheet `Budget` holding tables
`Q1`, `Q2`, `Q3` and `Notes`, and a sheet `Summary` holding a second `Q3`. Each
quarter is four rows by three columns, a header row and a footer row, numbers down
column B, a duration in C2 and a formula in B4. Fields pybers reads only from a file
are selected in documents Numbers made: `12-number-currency` for a format,
`81-control-formats` for a control and `57-structure-refusals-base` for
conditional highlighting.

UPDATES
2026-11-03  Written for PYB-223.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

import dataclasses
import datetime
from decimal import Decimal

import pytest

import pybers
from conftest import findDocumentPath
from pybers import Selector


def buildLedger() -> pybers.Document:
    """Return the document every test here selects in, made by `pybers.create`."""
    document = pybers.create("en_US")
    budget = document.sheet()
    budget.name = "Budget"
    for name in ("Q1", "Q2", "Q3"):
        table = budget.tableAdd(name, 4, 3)
        table.headersSet(headerRows=1, footerRows=1)
        table.cell("A1").value = "Item"
        for row in (2, 3):
            table.cell(f"B{row}").value = Decimal(row)
        table.cell("C2").value = datetime.timedelta(hours=1)
        table.cell("B4").formulaSet("=SUM(B2:B3)")
    budget.tableAdd("Notes", 2, 2).cell("A1").value = "Remember"
    document.sheetAdd("Summary").tableAdd("Q3", 2, 2).cell("A1").value = Decimal(1)
    return document


@pytest.fixture
def ledger() -> pybers.Document:
    return buildLedger()


def listWritten(selection: tuple[pybers.SelectionMatch, ...]) -> list[str]:
    """Return each match of a selection as it is written."""
    return [str(each) for each in selection]


# AC 01, 05.i

def testComponentsFillThePositionsFromTheLeft(ledger: pybers.Document) -> None:
    assert listWritten(ledger.select("Budget")) == ["Budget"]
    assert listWritten(ledger.select("Budget::Q3")) == ["Budget::Q3"]
    assert listWritten(ledger.select("Budget::Q3::B2")) == ["Budget::Q3::B2"]


def testEachOwnerReadsASelectorRelativeToItself(ledger: pybers.Document) -> None:
    budget = ledger.sheet("Budget")
    assert listWritten(budget.select("Q3::B2")) == ["Budget::Q3::B2"]
    assert listWritten(budget.table("Q3").select("B2")) == ["Budget::Q3::B2"]


def testASelectorGivenToATableNeverNamesItsSheet(ledger: pybers.Document) -> None:
    with pytest.raises(pybers.SelectorError, match="at most 1: cells"):
        ledger.table(pybers.TableReference(
            sheet=pybers.SheetReference("Budget"), name="Q3"
        )).select("Q3::B2")


# AC 05.ii, 06

def testALeadingSeparatorFillsThePositionsFromTheRight(
    ledger: pybers.Document,
) -> None:
    assert listWritten(ledger.select("::Q3::B4")) == ["Budget::Q3::B4"]
    assert listWritten(ledger.select("::Notes::A1")) == ["Budget::Notes::A1"]
    assert len(ledger.select("::A1")) == 5


def testAPositionAlwaysNamesTheSamePart(ledger: pybers.Document) -> None:
    with pytest.raises(pybers.ReferenceError, match="^Q3 names no cell"):
        ledger.select("::Q3")
    assert listWritten(ledger.select("*::Q3")) == ["Budget::Q3", "Summary::Q3"]


# AC 05.iii

@pytest.mark.parametrize(("cells", "written"), [
    ("B3", "Budget::Q1::B3"),
    ("B2:C3", "Budget::Q1::B2:C3"),
    ("B", "Budget::Q1::B"),
    ("3", "Budget::Q1::3"),
])
def testTheCellsPositionTakesAnAddressARangeAColumnOrARow(
    ledger: pybers.Document, cells: str, written: str
) -> None:
    assert listWritten(ledger.select(f"Budget::Q1::{cells}")) == [written]


def testARangeIsReturnedAsOneRangeNamingItsSheetAndTable(
    ledger: pybers.Document,
) -> None:
    (found,) = ledger.select("Budget::Q1::B2:C3")
    assert isinstance(found, pybers.CellRange)
    assert found.table == pybers.TableReference(
        sheet=pybers.SheetReference("Budget"), name="Q1"
    )


# AC 05.iv, 08

def testAConditionAppliesToTheCellsOfEverythingSelected(
    ledger: pybers.Document,
) -> None:
    assert len(ledger.select("[kind=number]")) == 7
    assert listWritten(ledger.select("Budget::Q*[kind=number]"))[:2] == [
        "Budget::Q1::B2", "Budget::Q1::B3",
    ]
    assert len(ledger.select("Budget::Q*[kind=number]")) == 6


def testABareAttributeMatchesAnyValueOfIt(ledger: pybers.Document) -> None:
    assert len(ledger.select("Summary::*[kind]")) == 4


def testADurationIsSelectedByItsKind(ledger: pybers.Document) -> None:
    assert listWritten(ledger.select("Budget::Q2[kind=duration]")) == [
        "Budget::Q2::C2"
    ]


@pytest.mark.parametrize(("stem", "selector", "first"), [
    ("12-number-currency", "[format=currency]", "Sheet 1::Table 1::B1"),
    ("81-control-formats", "[control=slider]", "Sheet 1::Table 1::A1"),
    ("57-structure-refusals-base", "[conditional]", "Sheet 1::Conditions::A1"),
])
def testAnAttributeReadsWhatPybersModels(stem: str, selector: str, first: str) -> None:
    found = pybers.open(findDocumentPath(stem)).select(selector)
    assert str(found[0]) == first


def testEachAttributeIsMappedOnceToTheFieldItReads() -> None:
    from pybers.selection.conditions import selectorAttributes

    assert list(selectorAttributes) == ["kind", "format", "control", "conditional"]


# AC 09

@pytest.mark.parametrize(("selector", "written"), [
    ("Budget::Q1:: :header", ["A1", "B1", "C1"]),
    ("Budget::Q1:: :footer", ["A4", "B4", "C4"]),
    ("Budget::Q1:: :formula", ["B4"]),
    ("Budget::Q1:: :empty:nth-column(1)", ["A2", "A3", "A4"]),
])
def testAPseudoClassConditionsOnACellsState(
    ledger: pybers.Document, selector: str, written: list[str]
) -> None:
    assert [str(each.address) for each in ledger.select(selector)] == written


def testAMergedCellIsSelectedAtItsAnchorOnce(ledger: pybers.Document) -> None:
    table = ledger.sheet("Budget").table("Notes")
    table.mergeAdd("A2:B2")
    assert listWritten(table.select(":merged")) == ["Budget::Notes::A2"]
    assert listWritten(table.select("2[kind]")) == ["Budget::Notes::A2"]


# AC 10

@pytest.mark.parametrize(("pattern", "rows"), [
    ("2n", [2, 4]), ("odd", [1, 3]), ("even", [2, 4]), ("2n+3", [3]),
    ("-n+2", [1, 2]), ("3", [3]), ("n", [1, 2, 3, 4]),
])
def testAPositionIsMatchedByPatternCountedFromOne(
    ledger: pybers.Document, pattern: str, rows: list[int]
) -> None:
    found = ledger.select(f"Budget::Q1::A:nth-row({pattern})")
    assert [each.address.row for each in found] == rows


def testEveryThirdColumnIsSelected() -> None:
    table = pybers.create("en_US").sheet().tableAdd("Wide", 1, 7)
    assert [each.address.col for each in table.select(":nth-column(3n+1)")] == [
        1, 4, 7
    ]


# AC 11

def testANegationRemovesAConditionsCells(ledger: pybers.Document) -> None:
    found = ledger.select("Budget::Q1:not(:empty):not(:header, :footer)")
    assert [str(each.address) for each in found] == ["B2", "C2", "B3"]


def testANegationRemovesNamesFromAComponent(ledger: pybers.Document) -> None:
    assert listWritten(ledger.select("Budget::*:not(Notes, Q2)")) == [
        "Budget::Q1", "Budget::Q3"
    ]


def testANegationRemovesCellsFromARange(ledger: pybers.Document) -> None:
    found = ledger.select("Budget::Q1::B2:B4:not(B3)")
    assert [str(each.address) for each in found] == ["B2", "B4"]


# AC 07

def testCommasGroupSeveralSelectorsEachMatchedOnce(ledger: pybers.Document) -> None:
    assert listWritten(ledger.select("Summary, Budget::Notes, Summary")) == [
        "Summary", "Budget::Notes"
    ]


@pytest.mark.parametrize(("selector", "written"), [
    ("Budget::Q?", ["Budget::Q1", "Budget::Q2", "Budget::Q3"]),
    ("*::q3", ["Budget::Q3", "Summary::Q3"]),
    ("S*", ["Summary"]),
])
def testANameIsMatchedInPartWithWildcards(
    ledger: pybers.Document, selector: str, written: list[str]
) -> None:
    assert listWritten(ledger.select(selector)) == written


def testAnEscapedCharacterIsTakenLiterally() -> None:
    document = pybers.create("en_US")
    document.sheetAdd("Q3, draft*")
    assert listWritten(document.select("Q3\\, draft\\*")) == ["Q3, draft*"]
    assert pybers.quoteSelectorName("Q3, draft*") == "Q3\\, draft\\*"


# AC 12

@pytest.mark.parametrize("text", [
    "Budget", "::Q3::B4", "Budget::Q*:not(Q4)::B2:D9[kind=number]:not(:empty)",
    "[format=currency]:nth-row(2n+1), Summary::*", "Q3\\, draft::A",
])
def testASelectorsTextFormReadsBackToTheSameSelector(text: str) -> None:
    selector = Selector.parse(text)
    assert Selector.parse(str(selector)) == selector


def testASelectorIsFrozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Selector.parse("Budget").groups = ()  # type: ignore[misc]


def testTheLibraryTakesTheSelectorTypeAndItsTextAlike(ledger: pybers.Document) -> None:
    text = "Budget::Q*[kind=number]"
    assert ledger.select(Selector.parse(text)) == ledger.select(text)


# AC 15

@pytest.mark.parametrize(("selector", "message"), [
    ("Ledger", "No sheet in this document is named 'Ledger'. The sheets are "
               "'Budget', 'Summary'."),
    ("Budget::Q4", "No table in 'Budget' is named 'Q4'. The tables are 'Q1', 'Q2', "
                   "'Q3', 'Notes'."),
    ("Budget::Notes::Z9", "Z9 is outside 'Notes', which is 2 rows by 2 columns."),
])
def testAnExactNameNothingCarriesIsRefusedListingWhatIsThere(
    ledger: pybers.Document, selector: str, message: str
) -> None:
    with pytest.raises(pybers.PybersError) as raised:
        ledger.select(selector)
    assert str(raised.value) == message


@pytest.mark.parametrize("selector", [
    "Z*", "Budget::Z*", "Budget::Q1[kind=boolean]", "Z*::Q4::A1",
])
def testAPatternOrConditionMatchingNothingReturnsNothing(
    ledger: pybers.Document, selector: str
) -> None:
    assert len(ledger.select(selector)) == 0


def testACellSomeTablesLackIsReturnedFromThoseHoldingIt(
    ledger: pybers.Document,
) -> None:
    assert listWritten(ledger.select("::C3")) == [
        "Budget::Q1::C3", "Budget::Q2::C3", "Budget::Q3::C3"
    ]


# AC 16, 17

@pytest.mark.parametrize(("text", "message"), [
    ("", "``, column 1: A selector names something, and this one is empty."),
    ("a::b::c::d", "`a::b::c::d`, column 10: A selector names at most 3 positions"),
    ("[kind=nmber]", "`[kind=nmber]`, column 1: `nmber` is no value of `[kind]`. "
                     "It takes empty, number,"),
    ("[colour]", "`[colour]`, column 1: `[colour]` is no condition pybers knows. "
                 "The conditions are [kind], [format], [control], [conditional]."),
    ("a[kind]::b", "`a[kind]::b`, column 8: Conditions follow every component"),
    ("a,,b", "`a,,b`, column 3: A selector group is empty."),
    ("a(", "`a(`, column 2: `(` is not part of a name. Write `\\(`."),
    ("[kind", "`[kind`, column 1: This `[` is never closed."),
    (":nth-row(x)", "`:nth-row(x)`, column 10: `x` is not a position pattern."),
    ("[kind]:emty", "`[kind]:emty`, column 7: `:emty` is no condition pybers knows."),
    ("[conditional=yes]", "`[conditional=yes]`, column 1: `[conditional]` takes no "
                          "value."),
])
def testAMalformedSelectorIsRefusedNamingThePartAndWhereItSits(
    text: str, message: str
) -> None:
    with pytest.raises(pybers.SelectorError) as raised:
        Selector.parse(text)
    assert str(raised.value).startswith(message)


def testACellsPositionThatIsNoAddressIsRefusedWhereItSits(
    ledger: pybers.Document,
) -> None:
    with pytest.raises(pybers.SelectorError) as raised:
        ledger.select("Budget::Q1::B0")
    assert str(raised.value).startswith(
        "`Budget::Q1::B0`, column 13: `B0` is in the cells position, and is not an "
        "address, a range, a column or a row"
    )


def testNoRefusalAsksAQuestion(ledger: pybers.Document) -> None:
    for selector in ("Ledger", "Budget::Q4", "Budget::Notes::Z9", "a::b::c::d"):
        with pytest.raises(pybers.PybersError) as raised:
            ledger.select(selector)
        assert "?" not in str(raised.value)


# AC 18.ii

def testAWriteSetsEveryCellMatchedAndSkipsWhatItCannot(
    ledger: pybers.Document,
) -> None:
    changes = ledger.cellSet("Budget::Q1::B3:B4, Budget::Notes", 7)
    assert [str(each.reference) for each in changes.changes] == ["Budget::Q1::B3"]
    assert [each.reason for each in changes.skipped] == [
        "Budget::Notes is a table, and a value is written into cells.",
        "Budget::Q1::B4 is backed by a formula, which a value would discard.",
    ]
    assert ledger.sheet("Budget").table("Q1").cell("B3").value == Decimal(7)


def testAWriteAcrossTablesSetsTheCellInEach(ledger: pybers.Document) -> None:
    changes = ledger.cellSet("Budget::Q*::B2", 1)
    assert [str(each.reference) for each in changes.changes] == [
        "Budget::Q1::B2", "Budget::Q2::B2", "Budget::Q3::B2",
    ]


def testAWriteMatchingNothingChangesNothing(ledger: pybers.Document) -> None:
    changes = ledger.cellSet("Z*::*::B2", 1)
    assert changes.changes == () and not changes.changed


def testAValueNoCellHoldsIsRefusedBeforeAnyIsWritten(
    ledger: pybers.Document,
) -> None:
    before = [each.value for each in ledger.sheet("Budget").table("Q1").cells.values()]
    with pytest.raises(pybers.WriteError):
        ledger.cellSet("[kind=number]", 0.5)
    after = [each.value for each in ledger.sheet("Budget").table("Q1").cells.values()]
    assert after == before


def testGrowingATableTakesOneCellInOneTable(ledger: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="matches 3 tables"):
        ledger.cellSet("Budget::Q*::B9", 1, extend=True)
    with pytest.raises(pybers.SelectionError, match="names more than one address"):
        ledger.cellSet("Budget::Q1::B2:B3", 1, extend=True)


# AC 02, 13

def testTheTypedLookupsAreTheResolversOneGroupSelections(
    ledger: pybers.Document,
) -> None:
    budget = ledger.sheet("Budget")
    assert ledger.select("Budget") == (pybers.SheetReference(budget.name),)
    assert ledger.select("*::Notes") == (ledger.table("Notes").reference,)


def testSelectingCreatesNothing(ledger: pybers.Document) -> None:
    table = ledger.sheet("Budget").table("Notes")
    stored = dict(table.cells)
    ledger.select("Budget::Notes:: :empty")
    assert dict(table.cells) == stored


def testThePartSelectorAndCellLookupsAreGone() -> None:
    for name in ("partSelect", "cell"):
        assert not hasattr(pybers.Document, name)
    assert not hasattr(pybers.Sheet, "cell")
    assert not hasattr(pybers.Table, "range")


# AC 19: what a script author writes

def testAScriptDoublesEveryNumberInTheQuarterlyTables(
    ledger: pybers.Document,
) -> None:
    for found in ledger.select("Budget::Q*[kind=number]"):
        assert isinstance(found, pybers.CellReference) and found.table is not None
        cell = ledger.table(found.table).cell(found)
        assert isinstance(cell.value, Decimal)
        cell.value = cell.value * 2
    assert ledger.sheet("Budget").table("Q2").cell("B3").value == Decimal(6)


def testAScriptSeesWhatASelectorMatchesBeforeActing(
    ledger: pybers.Document,
) -> None:
    assert listWritten(ledger.select("*::Q3::B2")) == [
        "Budget::Q3::B2", "Summary::Q3::B2"
    ]


# Regressions found in review

def testTwoSheetsOfOneNameAreRefusedRatherThanMerged() -> None:
    document = pybers.create("en_US")
    document.sheetAdd("Sheet 1")
    with pytest.raises(pybers.SelectionError) as raised:
        document.select("Sheet 1")
    assert str(raised.value) == (
        "2 sheets in this document are named 'Sheet 1', at positions 1, 2. A "
        "selector reaches a sheet by its name, so rename one."
    )


def testACellTwoGroupsReachIsWrittenOnce(ledger: pybers.Document) -> None:
    changes = ledger.cellSet("Budget::Q1::B2:B3, Budget::Q1::B3", 7)
    assert [str(each.reference) for each in changes.changes] == [
        "Budget::Q1::B2", "Budget::Q1::B3",
    ]


def testANameItsOwnExclusionRemovesMatchesNothing(ledger: pybers.Document) -> None:
    assert ledger.select("Budget:not(Budget)") == ()


def testAnEmptyNameIsNeitherANameNorAPosition(ledger: pybers.Document) -> None:
    with pytest.raises(pybers.SelectionError, match="'' is neither"):
        ledger.sheet("")

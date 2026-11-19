#!/usr/bin/env python3
"""\
How every golden is built: its source document and the mutation pybers writes into it.

A golden with no source starts from a document `pybers.create` made.

The one place a golden's construction is written down. `test_goldens.py` rebuilds each
from here and compares the whole archive, and `--golden-write` writes each from here,
so no golden is made any other way. A test asserting what a golden holds reads its
writes from here rather than keeping a second copy.

UPDATES
2026-11-19  `00-created-cell-boxes-updated-by-pybers`, part of a cell's style
            changed or cleared, for PYB-290.
2026-11-18  `00-created-rows-banded-by-pybers`, a table's banded rows, for PYB-267.
2026-11-10  A label names a format or control a golden changed over the same value,
            for PYB-145.
2026-11-03  A golden setting a created table's headers, for PYB-223.
2026-11-02  A golden starting from a fixture or measurement names why, for PYB-261.
2026-11-02  A golden can start from a created document, for PYB-261.
2026-10-29  A golden for each measured region, for PYB-272.
2026-10-22  Written for PYB-255, gathering the builders the tests held.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

import dataclasses
import datetime
import random
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pybers
from conftest import copyDocument
from pybers import (
    CellValueFill,
    CurrencyAmount,
    Formula,
    FormulaReferenceRelocation,
)
from tools.local.lib.golden_expected import labelRow, measuredRow

relative = FormulaReferenceRelocation.PRESERVE_RELATIVE_POSITION
named = FormulaReferenceRelocation.PRESERVE_NAMED_CELL
repeat = CellValueFill.REPEAT_SOURCE_VALUE
series = CellValueFill.CONTINUE_SERIES
# The region a golden starting from a created document is created in.
createdLocale: str = "en_US"

@dataclass(frozen=True, slots=True)
class GoldenBuilder:
    """One golden: its name, the document it starts from, and what pybers writes.

    A source of None starts from a document created in `createdLocale`, and a golden
    starting from a fixture or measurement names in `sourceReason` the ticket enabling
    pybers to create its source, or why it does not. `labeled` marks a golden laid out
    as a measurement, and from a source, the label beneath each changed cell is
    rewritten.
    """

    name: str
    source: str | None
    mutate: Callable[[pybers.Document], None]
    labeled: bool = False
    sourceReason: str = ""


@contextmanager
def holdSeededIdentities(name: str) -> Iterator[None]:
    """Make every identity pybers creates follow from a golden's name, while it builds.

    pybers gives a created line, sheet or table a random identity, as Numbers does, so
    without a seed no two builds of a golden would agree.
    """
    generator = random.Random(name)
    created = uuid.uuid4
    uuid.uuid4 = lambda: uuid.UUID(int=generator.getrandbits(128), version=4)
    try:
        yield
    finally:
        uuid.uuid4 = created


def findShownText(table: pybers.Table, address: pybers.CellAddress) -> str:
    """Return what a cell holds as text: its formula, value, or the merge over it."""
    merge = table.mergeFind(address)
    if merge is not None and merge.anchor != address:
        return f"covered by the merge {merge.extent}"
    cell = table.cell(address)
    if cell.formula is not None:
        return cell.formulaText or ""
    return pybers.formatCellValue(cell.value)


def formatGoldenLabel(shown: str, sourceLabel: str) -> str:
    """Return the label beneath a cell pybers changed: what it wrote, and over what."""
    return f"written by pybers as {shown} over {sourceLabel}"


@dataclass(frozen=True, slots=True)
class MeasuredCell:
    """A measured cell's text, how it shows it, and the label beneath it."""

    shown: str
    presentation: str
    label: str


def findPresentationText(table: pybers.Table, address: pybers.CellAddress) -> str:
    """Return a cell's format and control as text, Automatic named without its pick.

    The pick is left out because it is UNDETERMINED until a save, and a label is
    written before one. A merge's covered cell shows nothing of its own.
    """
    merge = table.mergeFind(address)
    if merge is not None and merge.anchor != address:
        return ""
    shown = table.cell(address).presentation
    cellFormat = (
        "none" if shown.format is None
        else "automatic" if isinstance(shown.format, pybers.CellFormatAutomatic)
        else pybers.formatCellFormat(shown.format)
    )
    if shown.control is None:
        return cellFormat
    return f"{cellFormat} through {pybers.formatCellControl(shown.control)}"


def findGoldenLabel(source: MeasuredCell, built: MeasuredCell) -> str:
    """Return the label a measured cell should carry once pybers has changed it.

    A changed value is named alone, and a format or control changed over the same
    value is named with it.
    """
    if built.shown != source.shown:
        return formatGoldenLabel(built.shown, source.label)
    if built.presentation != source.presentation:
        return formatGoldenLabel(
            f"{built.shown} in {built.presentation}", source.label
        )
    return source.label


def listMeasuredCells(table: pybers.Table) -> list[pybers.CellAddress]:
    """Return the address of every measured cell, the row its labels describe."""
    return [pybers.CellAddress(measuredRow, column)
            for column in range(1, table.colCount + 1)]


def readMeasuredCells(table: pybers.Table) -> dict[pybers.CellAddress, MeasuredCell]:
    """Return each measured cell's text, presentation and label, by its address."""
    return {
        address: MeasuredCell(
            findShownText(table, address),
            findPresentationText(table, address),
            str(table.cell(row=labelRow, col=address.col).value),
        )
        for address in listMeasuredCells(table)
    }


def writeGoldenLabels(
    table: pybers.Table, before: dict[pybers.CellAddress, MeasuredCell]
) -> None:
    """Rewrite the label beneath every measured cell the mutation changed."""
    for address, measured in readMeasuredCells(table).items():
        wanted = findGoldenLabel(before[address], measured)
        if wanted != before[address].label:
            table.cell(row=labelRow, col=address.col).value = wanted


def buildGolden(builder: GoldenBuilder, into: Path) -> Path:
    """Write a golden's mutation into its source or a created document, return it."""
    with holdSeededIdentities(builder.name):
        if builder.source is None:
            working = into / f"{builder.name}.numbers"
            document = pybers.create(createdLocale)
            builder.mutate(document)
            document.save(working)
            return working
        working = copyDocument(builder.source, into)
        document = pybers.open(working)
        table = findFirstTable(document)
        before = readMeasuredCells(table) if builder.labeled else {}
        builder.mutate(document)
        if builder.labeled:
            writeGoldenLabels(table, before)
        document.save()
    return working


def findFirstTable(document: pybers.Document) -> pybers.Table:
    """Return the document's first table, which every measurement edits."""
    return document.sheets[0].tables[0]


def writeValues(
    writes: tuple[tuple[str, object], ...],
) -> Callable[[pybers.Document], None]:
    """Return a mutation writing each value into the first table, in order."""

    def mutate(document: pybers.Document) -> None:
        table = findFirstTable(document)
        for address, value in writes:
            table.cell(address).value = value

    return mutate


def writeFormulaTexts(
    sheet: str, table: str, formulas: tuple[tuple[str, str], ...],
) -> Callable[[pybers.Document], None]:
    """Return a mutation writing each formula as text into one table, in order."""

    def mutate(document: pybers.Document) -> None:
        target = document.sheet(sheet).table(table)
        for address, text in formulas:
            target.cell(address).formulaText = text

    return mutate


# ── 11: values written over each kind ───────────────────────────────────────

# Each golden's writes into its measurement, every one of whose cells it changes.
kindWrites: dict[str, tuple[str, tuple[tuple[str, object], ...]]] = {
    "11-booleans-written-by-pybers": ("90-values-for-booleans", (
        ("A1", True), ("B1", False), ("C1", False), ("D1", True), ("E1", True),
    )),
    "11-dates-written-by-pybers": ("90b-values-for-dates", (
        ("A1", datetime.datetime(2027, 1, 31)),
        ("B1", datetime.datetime(2026, 10, 20, 9, 30)),
        ("C1", datetime.datetime(2027, 6, 16)),
        ("D1", datetime.datetime(2026, 12, 25, 18, 45)),
    )),
    "11-durations-written-by-pybers": ("90c-values-for-durations", (
        ("A1", datetime.timedelta(minutes=90)),
        ("B1", datetime.timedelta(hours=2)),
        ("C1", datetime.timedelta(days=1, hours=2)),
    )),
    "11-controls-written-by-pybers": ("91-controls-for-values", (
        ("A1", False), ("B1", Decimal("7")), ("C1", Decimal("100")),
        ("D1", Decimal("500")), ("E1", "Banana"),
    )),
    "11-text-written-and-retyped": ("90e-values-for-text-and-retyping", (
        ("A1", "text over a number"),
        ("B1", "text over a number"),
        ("C1", "text over a control"),
        ("D1", Decimal("98765.4321")),
        ("E1", "into an empty cell"),
    )),
    "11-value-types-noformats-A1-edited": ("90f-number-for-an-edit", (
        ("A1", Decimal("98765.4321")),
    )),
}

# A number written into dollars stays dollars, so it reads back as an amount.
currencyWrites: tuple[tuple[str, Decimal | CurrencyAmount], ...] = (
    ("A1", CurrencyAmount(Decimal("99.5"), "CHF")),
    ("B1", Decimal("12.5")),
    ("C1", CurrencyAmount(Decimal("7"), "EUR")),
    ("D1", CurrencyAmount(Decimal("1000"), "GBP")),
)

# A literal retyping a number and one into an empty cell, beside plain text.
literalCells: tuple[tuple[str, str], ...] = (
    ("A1", "=SUM(B1:C1)"),
    ("C1", "=A1+1"),
)
plainCell: tuple[str, str] = ("B1", "=1+1")


def writeLiterals(document: pybers.Document) -> None:
    """Write the literal texts and the plain text beside them."""
    table = findFirstTable(document)
    for address, text in literalCells:
        table.cell(address).textLiteralSet(text)
    table.cell(plainCell[0]).value = plainCell[1]


# ── 18 and 19: formulas edited as nodes ─────────────────────────────────────


def editLiteral(document: pybers.Document) -> None:
    """Change `A1`'s `=1+1` to `=1+5` by replacing one literal node."""
    cell = findFirstTable(document).cell("A1")
    assert cell.formula is not None
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(5))
    cell.formula = Formula(nodes=tuple(nodes))


def editSharedRange(document: pybers.Document) -> None:
    """Narrow `F2`, one of two cells sharing an archive, to end at column 3."""
    table = findFirstTable(document)
    formula = table.cell("F2").formula
    assert formula is not None
    nodes = list(formula.nodes)
    extent = nodes[0].content
    nodes[0] = dataclasses.replace(
        nodes[0],
        content=dataclasses.replace(
            extent, columns=dataclasses.replace(extent.columns, end=3)  # type: ignore[union-attr,arg-type]
        ),
    )
    table.cell("F2").formula = Formula(nodes=tuple(nodes))


def attachAndDetach(document: pybers.Document) -> None:
    """Attach `A1`'s formula to the text at `B1`, and detach `C1`'s."""
    table = findFirstTable(document)
    table.cell("B1").formula = table.cell("A1").formula
    table.cell("C1").formula = None


def createFormulaInEmptyCell(document: pybers.Document) -> None:
    """Write `=SUM(1,2,3)` into `A1`, which has no record."""
    findFirstTable(document).cell("A1").formulaText = "=SUM(1,2,3)"


# ── 20: formulas written into 20-formula-shapes ─────────────────────────────

authoredFormulas: tuple[tuple[str, str], ...] = (
    ("B1", "=Table 1::A11*2+1"),
    ("C1", '=IF(SUM(A1:A10)>10,"big","small")'),
    ("D1", '=$A$1&" units"'),
)

# One bracket per open question: redundant, required by precedence, around an
# atom, and required by associativity alone.
bracketedFormulas: tuple[tuple[str, str], ...] = (
    ("B1", "=22+(3/12)"),
    ("C1", "=(1+2)*3"),
    ("D1", "=(5)"),
    ("E1", "=1-(2-3)"),
)

createdRowFormulas: tuple[tuple[str, str], ...] = (
    ("A3", "=1+1"),
    ("C3", "=2*3"),
    ("B7", "=SUM(A1:A2)"),
    ("E10", "=A1*2"),
)

# One call to each function Numbers 15.4 added, `TRUE()` written as the function
# Numbers stores, and the two paired statistics reading `Table 1`'s first ten rows.
addedFunctionFormulas: tuple[tuple[str, str], ...] = (
    ("B1", "=ACOT(1)"), ("B2", "=ACOTH(2)"), ("B3", "=COT(1)"), ("B4", "=COTH(1)"),
    ("B5", "=CSC(1)"), ("B6", "=CSCH(1)"), ("B7", "=SEC(1)"), ("B8", "=SECH(1)"),
    ("B9", "=XOR(TRUE(),FALSE())"),
    ("C1", "=COMBINA(4,3)"), ("C2", "=GAMMA(5)"), ("C3", "=PHI(0)"),
    ("C4", "=FISHER(0.5)"), ("C5", "=FISHERINV(0.5)"), ("C6", "=PERMUTATIONA(3,2)"),
    ("C7", "=DAYS(DATE(2026,10,13),DATE(2026,1,1))"),
    ("C8", "=PEARSON(Table 1::A1:A5,Table 1::A6:A10)"),
    ("C9", "=RSQ(Table 1::A1:A5,Table 1::A6:A10)"),
)

# Every anchoring of a reference and a range, so each axis a retarget moves is seen.
anchoredFormulas: tuple[tuple[str, str], ...] = (
    ("E1", "=$A$3*10"),
    ("F1", "=$A$5*2"),
    ("G1", "=A$5*2"),
    ("H1", "=$A5*2"),
    ("I1", "=SUM($A$3:$A$7)"),
    ("J1", "=SUM(A$3:A$7)"),
    ("K1", "=SUM($A3:$A7)"),
    ("L1", "=$A$6"),
)


def editEveryNumber(document: pybers.Document) -> None:
    """Add 1000 to every number in rows 1 to 10 of every table on every sheet."""
    for _, _, cell in document.cellsIterate():
        # Rows 11 and 12 are the formula row and its labels, never numbers to edit.
        if isinstance(cell.value, Decimal) and cell.address.row <= 10:
            cell.value = cell.value + Decimal(1000)


def writeFirstText(document: pybers.Document) -> None:
    """Write the first text into a table holding none, at `B1` and an unstored row."""
    table = document.sheet("Sheet 1").table("Table 2")
    table.cell("B1").value = "first text here"
    table.cell("A3").value = "and a row with no storage"


def editPrecedent(document: pybers.Document) -> None:
    """Give `Table 2` two inputs and a formula, save, then point it at the other."""
    table = document.sheet("Sheet 1").table("Table 2")
    table.cell("A1").value = Decimal(2)
    table.cell("A2").value = Decimal(7)
    table.cell("B1").formulaText = "=A1*3"
    document.save()
    table.cell("B1").formulaText = "=A2*3"


def relocateTableReferences(document: pybers.Document) -> int:
    """Write the anchored formulas, move each reference into `Table 1`, and count."""
    target = document.sheet("Sheet 1").table("Table 1")
    for address, text in anchoredFormulas:
        target.cell(address).formulaText = text
    return sum(
        location.shift(rows=1, cols=7)
        for location in document.referencesIterate()
        if location.target is target
    )


def relocateTable(document: pybers.Document) -> None:
    """Retarget `Table 1` as the golden does, the count being the test's to check."""
    relocateTableReferences(document)


def addFormulaTables(document: pybers.Document) -> None:
    """Add two tables on `Sheet 1` and four formulas reading them and `Table 2`."""
    inputs = document.sheet("Sheet 1").tableAdd("Inputs", rows=2, cols=2)
    inputs.cell("A1").value = Decimal("5")
    calc = document.sheet("Sheet 1").tableAdd("Calc", rows=3, cols=3)
    calc.cell("A1").value = Decimal("2")
    calc.cell("B1").formulaText = "=A1*3"
    calc.cell("C1").formulaText = "=Table 2::A1"
    calc.cell("A2").formulaText = "=Inputs::A1+1"
    calc.cell("A3").formulaText = "=SUM(A1:B1)"


def addCreatedFormulaTables(document: pybers.Document) -> None:
    """Add two tables to a created document and formulas reading within and across."""
    inputs = document.sheet("Sheet 1").tableAdd("Inputs", rows=2, cols=2)
    inputs.cell("A1").value = Decimal("5")
    calc = document.sheet("Sheet 1").tableAdd("Calc", rows=3, cols=3)
    calc.cell("A1").value = Decimal("2")
    calc.cell("B1").formulaText = "=A1*3"
    calc.cell("C1").formulaText = "=Inputs::A1*2"
    calc.cell("A2").formulaText = "=Inputs::A1+1"
    calc.cell("A3").formulaText = "=SUM(A1:B1)"


def addSheets(document: pybers.Document) -> None:
    """Insert a sheet second and append another."""
    document.sheetAdd("Inserted", position=2)
    document.sheetAdd("Appended")


def addTables(document: pybers.Document) -> None:
    """Add three tables, two on `Sheet 1` and one on a new sheet, with values."""
    first = document.sheet("Sheet 1").tableAdd("Table 1", rows=3, cols=4)
    first.cell("A1").value = "text in a created table"
    first.cell("B2").value = Decimal("12.5")
    second = document.sheet("Sheet 1").tableAdd("table 2", rows=2, cols=3)
    second.cell("C2").value = "second created"
    output = document.sheetAdd("Fresh").tableAdd("Output", rows=5, cols=2)
    output.cell("A1").value = Decimal("1")
    output.cell("B5").value = "last cell"


def setHeaders(document: pybers.Document) -> None:
    """Set every header and footer count of one table, and grow another's header."""
    sheet = document.sheet()
    headers = sheet.tableAdd("Headers", rows=8, cols=4)
    headers.headersSet(headerRows=2, headerColumns=1, footerRows=1)
    for row, label in ((1, "header"), (3, "body"), (8, "footer")):
        headers.cell(f"B{row}").value = label
    headers.cell("A5").value = "side"
    grown = sheet.tableAdd("Grown", rows=4, cols=2)
    grown.headersSet(headerRows=1)
    grown.rowAdd(1)
    grown.cell("A1").value = "header"


def fillAcross(rule: FormulaReferenceRelocation) -> Callable[[pybers.Document], None]:
    """Return a mutation filling `A1` across `A1:D1` under a reference rule."""

    def mutate(document: pybers.Document) -> None:
        table = findFirstTable(document)
        table.cellsFill("A1", "A1:D1", references=rule, values=repeat)

    return mutate


# ── 20: whole-axis ranges and booleans, typed in Numbers in `70` ────────────

typedFormulas: tuple[tuple[str, str], ...] = (
    ("B1", "=SUM(C:D)"),
    ("B2", "=SUM(5:6)"),
    ("B3", "=SUM(Table 1::B:C)"),
    ("B4", "=SUM(Table 1::2:3)"),
    ("B5", "=TRUE"),
    ("B6", "=IF(FALSE,1,2)"),
    ("B7", "=SUM(Table 1::$B:$C)"),
    ("B8", "=SUM(Table 1::$2:$3)"),
)


# ── 22 and 45: merges ───────────────────────────────────────────────────────


def mergePairs(document: pybers.Document) -> None:
    """Merge `A1:B1`, `C1:D1`, `E1:F1`, `G1:H1` and `I1:J1`."""
    table = document.sheet(1).table(1)
    for start in "ACEGI":
        table.mergeAdd(f"{start}1:{chr(ord(start) + 1)}1")


def removeMerges(document: pybers.Document) -> None:
    """Remove every merge the first table holds."""
    table = document.sheet(1).table(1)
    for merge in list(table.mergeRanges):
        table.mergeRemove(merge.anchor)


def setLocale(identifier: str) -> Callable[[pybers.Document], None]:
    """Return a mutation changing the document's language and region."""

    def mutate(document: pybers.Document) -> None:
        document.localeSet(identifier)

    return mutate


def mergeRange(extent: str) -> Callable[[pybers.Document], None]:
    """Return a mutation merging one range of the first table."""

    def mutate(document: pybers.Document) -> None:
        findFirstTable(document).mergeAdd(extent)

    return mutate


# ── 56 and 61: lines added and removed ──────────────────────────────────────


def editStructure(
    edit: Callable[[pybers.Table], object],
) -> Callable[[pybers.Document], None]:
    """Return a mutation applying one structural edit to `Sheet 1 / Table 1`."""

    def mutate(document: pybers.Document) -> None:
        edit(document.sheet(1).table("Table 1"))

    return mutate


def addLinesBesideNoBorder(document: pybers.Document) -> None:
    """Add a row and a column beside lines with no border."""
    table = document.sheet(1).table("Table 1")
    table.rowAdd(2)
    table.columnAdd(2)


# ── 60 to 68: moves, copies and fills ───────────────────────────────────────


def moveBlock(rule: FormulaReferenceRelocation) -> Callable[[pybers.Document], None]:
    """Return a mutation moving `B2:D5` to `F8` under a reference rule."""

    def mutate(document: pybers.Document) -> None:
        findFirstTable(document).cellsMove("B2:D5", "F8", references=rule)

    return mutate


def copyBlock(rule: FormulaReferenceRelocation) -> Callable[[pybers.Document], None]:
    """Return a mutation copying `B2:D5` to `F8` under a reference rule."""

    def mutate(document: pybers.Document) -> None:
        findFirstTable(document).cellsCopy("B2:D5", "F8", references=rule)

    return mutate


def fillBlock(source: str, through: str) -> Callable[[pybers.Document], None]:
    """Return a mutation filling a block of the first table, repeating its values."""

    def mutate(document: pybers.Document) -> None:
        findFirstTable(document).cellsFill(
            source, through, references=relative, values=repeat
        )

    return mutate


def findSeedCount(index: int) -> int:
    """Return how many seeds case `index` of the `66` bases holds."""
    return 3 if index == 2 else 1 if index >= 15 else 2


def fillCase(table: pybers.Table, direction: str, index: int) -> None:
    """Fill one case of a `66` base the way its drag was made."""
    count = findSeedCount(index)
    if direction in ("down", "up"):
        letter = chr(65 + index)
        source = f"{letter}10:{letter}{9 + count}"
        through = (
            f"{letter}{10 + count}:{letter}21" if direction == "down"
            else f"{letter}2:{letter}9"
        )
    else:
        row = index + 1
        source = f"J{row}:{chr(73 + count)}{row}"
        through = (
            f"{chr(74 + count)}{row}:U{row}" if direction == "right"
            else f"B{row}:I{row}"
        )
    table.cellsFill(source, through, references=relative, values=series)


def fillSeriesCases(direction: str) -> Callable[[pybers.Document], None]:
    """Return a mutation filling all twenty cases of a `66` base in one direction."""

    def mutate(document: pybers.Document) -> None:
        table = findFirstTable(document)
        for index in range(20):
            fillCase(table, direction, index)

    return mutate


seedCountsByColumn: dict[str, int] = {
    "A": 2, "B": 1, "C": 2, "D": 3, "E": 3, "F": 3, "G": 3, "H": 3,
}


def fillRichSeries(document: pybers.Document) -> None:
    """Continue each column of `67` from its seeds down to row 13."""
    table = findFirstTable(document)
    for letter, count in seedCountsByColumn.items():
        table.cellsFill(
            f"{letter}2:{letter}{1 + count}", f"{letter}{2 + count}:{letter}13",
            references=relative, values=series,
        )


def fillKindSeries(document: pybers.Document) -> None:
    """Continue each of the 21 columns of `68` from its seeds down to row 13."""
    table = findFirstTable(document)
    for index in range(21):
        letter = chr(65 + index)
        count = 1 if letter in "QRST" else 2
        table.cellsFill(
            f"{letter}2:{letter}{1 + count}", f"{letter}{2 + count}:{letter}13",
            references=relative, values=series,
        )


# The regions findings-12-language-and-region.md measures, besides the base's en_US.
measuredLocales: tuple[str, ...] = (
    "de_DE", "en_GB", "ja_JP", "en_ZA", "pt_BR", "en_AU", "en_IN",
)

def writeNothing(document: pybers.Document) -> None:
    """Write nothing, for a golden that is its starting document."""


# ── 145: formats and controls set by pybers ─────────────────────────────────

# Each row of a created table: a label, then a value in its family chosen by a person.
chosenFormats: tuple[tuple[str, object, pybers.CellFormat], ...] = (
    ("0.25 in a chosen number format", Decimal("0.25"), pybers.CellFormatNumber()),
    ("words in a chosen text format", "words", pybers.CellFormatText()),
    ("10 November 2026 in a chosen date format", datetime.datetime(2026, 11, 10),
     pybers.CellFormatDateTime()),
    ("90 minutes in a chosen duration format", datetime.timedelta(minutes=90),
     pybers.CellFormatDuration()),
)


def chooseFormats(document: pybers.Document) -> None:
    """Give a created table one value of each kind in its family, chosen by a person."""
    table = document.sheet().tableAdd("Formats", rows=len(chosenFormats), cols=2)
    for row, (label, value, chosen) in enumerate(chosenFormats, start=1):
        table.cell(f"A{row}").value = label
        document.cellSet(f"::Formats::B{row}", value, format=chosen)


def writeAutomaticFormats(document: pybers.Document) -> None:
    """Return every percent of `13-number-percent` to Numbers' Automatic format."""
    document.cellSet("::Table 1::B1:G1", format=pybers.CellFormatAutomatic())


# Each row of a created table: a label, a formula with no result yet, and its format.
formulaFormats: tuple[tuple[str, str, pybers.CellFormat], ...] = (
    ("the input, 5", "", pybers.CellFormatAutomatic()),
    ("a tenth of the input in a chosen number format", "=B1/10",
     pybers.CellFormatNumber()),
    ("10 November 2026 in a chosen date format", "=DATE(2026,11,10)",
     pybers.CellFormatDateTime()),
    ("90 minutes in a chosen duration format", "=DURATION(0,0,1,30)",
     pybers.CellFormatDuration()),
)


def chooseFormulaFormats(document: pybers.Document) -> None:
    """Give formulas pybers created, with no result yet, their formats."""
    table = document.sheet().tableAdd("Formulas", rows=len(formulaFormats), cols=2)
    table.cell("B1").value = Decimal(5)
    for row, (label, formula, chosen) in enumerate(formulaFormats, start=1):
        table.cell(f"A{row}").value = label
        if formula:
            table.cell(f"B{row}").formulaText = formula
            document.cellSet(f"::Formulas::B{row}", format=chosen)


# Each row of a created table: a label, and a blank cell given a chosen format.
emptyFormats: tuple[tuple[str, pybers.CellFormat], ...] = (
    ("blank, in a chosen number format", pybers.CellFormatNumber()),
    ("blank, in a chosen date format", pybers.CellFormatDateTime()),
    ("blank, in a chosen duration format", pybers.CellFormatDuration()),
    ("blank, in a chosen text format", pybers.CellFormatText()),
)


def chooseEmptyFormats(document: pybers.Document) -> None:
    """Give blank cells of a created table their formats, each labeled beside it."""
    table = document.sheet().tableAdd("Blanks", rows=len(emptyFormats), cols=2)
    for row, (label, chosen) in enumerate(emptyFormats, start=1):
        table.cell(f"A{row}").value = label
        document.cellSet(f"::Blanks::B{row}", format=chosen)


def chooseFormulaFormat(document: pybers.Document) -> None:
    """Give the sum Numbers calculated in `20-formula-shapes` a chosen number format."""
    document.cellSet("Sheet 1::Table 1::A11", format=pybers.CellFormatNumber())


def removeControls(document: pybers.Document) -> None:
    """Remove each of the five controls `11-value-types-noformats` holds."""
    document.cellSet("::Table 1::E1:I1", control=None)


# Each case of a cell's box: what its own style states, and the value it shows.
wrappingText: str = (
    "words enough to run past the edge of this column, so wrapping shows on a "
    "second line"
)
cellBoxes: tuple[tuple[pybers.CellStyle, str | Decimal], ...] = (
    (pybers.CellStyle(background=pybers.Color.parse("#ffd60aff")), Decimal(1)),
    (pybers.CellStyle(padding=Decimal(12)), Decimal(2)),
    (pybers.CellStyle(padding=Decimal(0)), Decimal(3)),
    (pybers.CellStyle(verticalAlign=pybers.CellStyleVerticalAlign.MIDDLE), "middle"),
    (pybers.CellStyle(verticalAlign=pybers.CellStyleVerticalAlign.BOTTOM), "bottom"),
    (pybers.CellStyle(textWrap=pybers.CellStyleTextWrap.WRAP), wrappingText),
    (pybers.CellStyle(
        background=pybers.Color.parse("#ffd60aff"), padding=Decimal(8),
        verticalAlign=pybers.CellStyleVerticalAlign.MIDDLE,
        textWrap=pybers.CellStyleTextWrap.WRAP,
    ), wrappingText),
)


def setCellBoxes(document: pybers.Document) -> None:
    """Style one cell per case across row 1, its style as text beneath it.

    The wrapping cells make row 1 tall, so the aligned cells beside them show where
    their text sits.
    """
    columns = len(cellBoxes) + 1
    table = document.sheet().tableAdd("Boxes", rows=2, cols=columns)
    for column, (cellStyle, value) in enumerate(cellBoxes, start=1):
        document.cellSet(
            f"::Boxes::{pybers.CellAddress(1, column)}", value, cellStyle=cellStyle
        )
        table.cell(pybers.CellAddress(2, column)).value = (
            f"set by pybers to {pybers.formatCellStyle(cellStyle)}"
        )
    table.cell(pybers.CellAddress(2, columns)).value = "empty"



# The box every cell of the update golden starts from, all four properties stated.
updatedBase: pybers.CellStyle = pybers.CellStyle(
    background=pybers.Color.parse("#ffd60aff"), padding=Decimal(8),
    verticalAlign=pybers.CellStyleVerticalAlign.MIDDLE,
    textWrap=pybers.CellStyleTextWrap.WRAP,
)

# Each change to the base, one per column: a style updated, or a property cleared.
boxUpdates: tuple[pybers.CellStyle | pybers.CellStyleProperty, ...] = (
    pybers.CellStyle(background=pybers.Color.parse("#0a84ffff")),
    pybers.CellStyle(padding=Decimal(16)),
    pybers.CellStyle(verticalAlign=pybers.CellStyleVerticalAlign.BOTTOM),
    *pybers.CellStyleProperty,
)


def updateCellBoxes(document: pybers.Document) -> None:
    """Style every cell of row 1 alike, then change or clear one property per column.

    Each label beneath states the change and the box it leaves, wrapped so it reads
    in full, and the last cell keeps the base unchanged.
    """
    columns = len(boxUpdates) + 1
    table = document.sheet().tableAdd("Updated", rows=2, cols=columns)
    document.cellSet("::Updated::1", wrappingText, cellStyle=updatedBase)
    for column, change in enumerate(boxUpdates, start=1):
        target = f"::Updated::{pybers.CellAddress(1, column)}"
        if isinstance(change, pybers.CellStyle):
            document.cellStyleUpdate(target, change)
            how = f"updated with {pybers.formatCellStyle(change)}"
        else:
            document.cellStylePropertyRemove(target, change)
            how = f"{change.value} removed"
        shown = table.cell(pybers.CellAddress(1, column)).cellStyle
        table.cell(pybers.CellAddress(2, column)).value = (
            f"{how}, leaving {pybers.formatCellStyle(shown or pybers.CellStyle())}"
        )
    table.cell(pybers.CellAddress(2, columns)).value = (
        f"set by pybers to {pybers.formatCellStyle(updatedBase)}"
    )
    document.cellStyleUpdate(
        "::Updated::2", pybers.CellStyle(textWrap=pybers.CellStyleTextWrap.WRAP)
    )


# Each color case of a fill, the text naming it, in a column of its own.
fillColors: tuple[tuple[pybers.Color, str], ...] = (
    (pybers.Color.parse("#ff8000ff"), "sRGB 255 128 0, #ff8000ff"),
    (pybers.Color.parse("color(display-p3 1 0.5019608 0 / 1)"),
     "Display P3 255 128 0, color(display-p3 1 0.5019608 0 / 1)"),
    (pybers.Color.parse("color(srgb 1 0.5 0 / 0.5)"),
     "translucent sRGB 1 0.5 0 at opacity 50%, color(srgb 1 0.5 0 / 0.5)"),
    (pybers.Color.gray(Decimal("0.5"), 1),
     "Color.gray 0.5, color(srgb 0.5 0.5 0.5 / 1)"),
    (pybers.Color.black, "Color.black, #000000ff"),
    (pybers.Color.white, "Color.white, #ffffffff"),
)


def setCellFills(document: pybers.Document) -> None:
    """Fill one cell per color case across row 1, its color as text beneath it."""
    columns = len(fillColors) + 1
    table = document.sheet().tableAdd("Fills", rows=2, cols=columns)
    for column, (color, label) in enumerate(fillColors, start=1):
        above = pybers.CellAddress(1, column)
        document.cellSet(
            f"::Fills::{above}", Decimal(column),
            cellStyle=pybers.CellStyle(background=color),
        )
        table.cell(pybers.CellAddress(2, column)).value = f"filled with {label}"
    table.cell(pybers.CellAddress(2, columns)).value = "empty"


# ── PYB-266: a table's lines ────────────────────────────────────────────────

red: pybers.Color = pybers.Color(pybers.ColorSpace.SRGB, (1, 0, 0), 1)
borderStyleCases: tuple[tuple[str, dict[str, object]], ...] = (
    ("outer, solid, width and color left as offered", {}),
    ("outer, dashed, 1pt", {"style": pybers.CellBorderStyle.DASHED, "width": 1}),
    ("outer, dashed, 5pt", {"style": pybers.CellBorderStyle.DASHED, "width": 5}),
    ("outer, dotted, 1pt", {"style": pybers.CellBorderStyle.DOTTED, "width": 1}),
    ("outer, dotted, 5pt", {"style": pybers.CellBorderStyle.DOTTED, "width": 5}),
    ("outer, solid, 1pt, red at 50% opacity", {
        "style": pybers.CellBorderStyle.SOLID, "width": 1,
        "color": pybers.Color(pybers.ColorSpace.SRGB, (1, 0, 0), Decimal("0.5")),
    }),
    ("outer, hidden, the gridlines hidden around it", {
        "style": pybers.CellBorderStyle.HIDDEN,
    }),
)
positionRows: tuple[tuple[str, tuple[pybers.CellBorderPosition, ...]], ...] = (
    ("Positions Top", (pybers.CellBorderPosition.OUTER,
                       pybers.CellBorderPosition.BETWEEN,
                       pybers.CellBorderPosition.ALL)),
    ("Positions Middle", (pybers.CellBorderPosition.OUTER_LEFT,
                          pybers.CellBorderPosition.BETWEEN_COLUMNS,
                          pybers.CellBorderPosition.OUTER_RIGHT)),
    ("Positions Bottom", (pybers.CellBorderPosition.OUTER_TOP,
                          pybers.CellBorderPosition.BETWEEN_ROWS,
                          pybers.CellBorderPosition.OUTER_BOTTOM)),
)


def applyCellBorders(document: pybers.Document) -> None:
    """Draw each line style, each position, a later border over an earlier, a merge."""
    sheet = document.sheet()
    styles = sheet.tableAdd("Styles", rows=2, cols=2 * len(borderStyleCases) + 1)
    styles.tableStyleSet(
        bodyHorizontalGridlines=pybers.TableLine(
            True, styles.tableStyle.bodyHorizontalGridlines.stroke
        ),
        bodyVerticalGridlines=pybers.TableLine(
            True, styles.tableStyle.bodyVerticalGridlines.stroke
        ),
    )
    for at, (label, arguments) in enumerate(borderStyleCases):
        column = 2 * at + 1
        above = pybers.CellAddress(1, column)
        styles.cell(above).value = Decimal(1)
        document.cellBordersSet(
            f"::Styles::{above}", pybers.CellBorderPosition.OUTER,
            **arguments,  # type: ignore[arg-type]
        )
        styles.cell(pybers.CellAddress(2, column)).value = f"drawn {label}"
    for name, positions in positionRows:
        table = sheet.tableAdd(name, rows=3, cols=3 * len(positions))
        for at, position in enumerate(positions):
            left = 3 * at + 1
            block = pybers.CellRange.fromReferences(
                pybers.CellAddress(1, left), pybers.CellAddress(2, left + 1)
            )
            for address in block:
                table.cell(address).value = Decimal(1)
            document.cellBordersSet(f"::{name}::{block}", position)
            table.cell(pybers.CellAddress(3, left)).value = (
                f"{block} drawn {position}, solid"
            )
    order = sheet.tableAdd("Order", rows=3, cols=3)
    document.cellBordersSet("::Order::A1", pybers.CellBorderPosition.OUTER,
                            width=3, color=red)
    document.cellBordersSet("::Order::B1", pybers.CellBorderPosition.OUTER,
                            width=5, color=pybers.Color.black)
    order.cell("A2").value = "A1 red 3pt, then B1 black 5pt: their edge black"
    merged = sheet.tableAdd("Merged", rows=3, cols=4)
    merged.mergeAdd("B1:C2")
    document.cellBordersSet("::Merged::B1", pybers.CellBorderPosition.ALL,
                            style=pybers.CellBorderStyle.DASHED, width=2)
    merged.cell("A3").value = "B1:C2 merged, all borders dashed 2pt: its outline only"


tableLineCases: tuple[tuple[str, str], ...] = (
    ("Reset", ""),
    ("Body horizontal", "body-horizontal-gridlines: 1pt solid #ff0000ff"),
    ("Body vertical", "body-vertical-gridlines: 1pt solid #ff0000ff"),
    ("Header rows vertical", "header-rows-vertical-gridlines: 1pt solid #ff0000ff"),
    ("Header columns horizontal",
     "header-columns-horizontal-gridlines: 1pt solid #ff0000ff"),
    ("Footer rows vertical", "footer-rows-vertical-gridlines: 1pt solid #ff0000ff"),
    ("Header rows separator", "header-rows-separator: 2pt solid #ff0000ff"),
    ("Header columns separator", "header-columns-separator: 2pt solid #ff0000ff"),
    ("Footer rows separator", "footer-rows-separator: 2pt solid #ff0000ff"),
    ("Outline dashed", "table-outline: 2pt dashed #ff0000ff"),
    ("Outline dotted", "table-outline: 2pt dotted #ff0000ff"),
    ("Outline title", "table-title: yes; table-outline: 1pt solid #ff0000ff; "
                      "table-outline-title: yes"),
)


def setTableLines(document: pybers.Document) -> None:
    """Give each table one line in red, its declaration as text in B2."""
    for name, declarations in tableLineCases:
        table = document.sheet().tableAdd(name, rows=4, cols=3)
        table.headersSet(headerRows=1, headerColumns=1, footerRows=1)
        if declarations:
            table.tableStyleSet(pybers.parseTableStyle(declarations, table.tableStyle))
        table.cell("B1").value = Decimal(1)
        table.cell("B2").value = declarations or "the reset, unchanged"


deepBandLineCases: tuple[tuple[str, str], ...] = (
    ("Header rows horizontal",
     "header-rows-horizontal-gridlines: 1pt solid #ff0000ff"),
    ("Header columns vertical",
     "header-columns-vertical-gridlines: 1pt solid #ff0000ff"),
    ("Footer rows horizontal",
     "footer-rows-horizontal-gridlines: 1pt solid #ff0000ff"),
)


def setDeepBandLines(document: pybers.Document) -> None:
    """Give each table of two header rows, columns and footer rows one red line."""
    for name, declarations in (*tableLineCases[:9], *deepBandLineCases):
        table = document.sheet().tableAdd(name, rows=7, cols=5)
        table.headersSet(headerRows=2, headerColumns=2, footerRows=2)
        if declarations:
            table.tableStyleSet(pybers.parseTableStyle(declarations, table.tableStyle))
        table.cell("C1").value = Decimal(1)
        table.cell("C2").value = declarations or "the reset, unchanged"


# ── PYB-267: a table's banded rows ──────────────────────────────────────────

bandCases: tuple[tuple[str, str], ...] = (
    ("Reset", ""),
    ("Gray", "banded-rows: color(srgb 0.9601849 0.9601849 0.9601849 / 1)"),
    ("Yellow", "banded-rows: #ffd60aff"),
    ("Translucent", "banded-rows: color(srgb 1 0.23137255 0.1882353 / 0.5)"),
    ("Off keeping yellow", "banded-rows: hidden #ffd60aff"),
)


def setBandedRows(document: pybers.Document) -> None:
    """Band each table as the declaration in B2 states, and one with headers and fills.

    `Headers` has one header row, one header column and a footer row on a banded
    position, none of them filled, and C3 on a banded row filled red.
    """
    for name, declarations in bandCases:
        table = document.sheet().tableAdd(name, rows=7, cols=3)
        table.headersSet(headerRows=1)
        if declarations:
            table.tableStyleSet(pybers.parseTableStyle(declarations, table.tableStyle))
        table.cell("B1").value = Decimal(1)
        table.cell("B2").value = declarations or "the reset, unchanged"
    table = document.sheet().tableAdd("Headers", rows=7, cols=4)
    table.headersSet(headerRows=1, headerColumns=1, footerRows=1)
    table.tableStyleSet(pybers.parseTableStyle(
        "banded-rows: #ffd60aff", table.tableStyle
    ))
    document.cellSet("::Headers::C3", cellStyle=pybers.CellStyle(background=red))
    table.cell("B2").value = "banded-rows: #ffd60aff"
    table.cell("C2").value = "C3 background: #ff0000ff"
    table.cell("A3").value = "header column, banded row"
    table.cell("A7").value = "footer, banded position"


def editBorderedLines(document: pybers.Document) -> None:
    """Add and remove a row inside a red line, and move an empty bordered cell."""
    sheet = document.sheet()
    for name, edit, label in (
        ("Row added", lambda table: table.rowAdd(4),
         "B2:B5 outer-left red, then a row added at 4: the line unbroken over B2:B6"),
        ("Row removed", lambda table: table.rowRemove(4),
         "B2:B5 outer-left red, then row 4 removed: the line unbroken over B2:B4"),
    ):
        table = sheet.tableAdd(name, rows=7, cols=3)
        document.cellBordersSet(
            f"::{name}::B2:B5", pybers.CellBorderPosition.OUTER_LEFT, width=2,
            color=red,
        )
        edit(table)
        table.cell("C1").value = Decimal(1)
        table.cell("C2").value = label
    moved = sheet.tableAdd("Moved", rows=6, cols=6)
    document.cellBordersSet("::Moved::B2", pybers.CellBorderPosition.OUTER,
                            width=2, color=red)
    moved.cellsMove("B2", "D4", references=named)
    moved.cell("A1").value = Decimal(1)
    moved.cell("A2").value = "B2, empty and bordered red, moved to D4: the border at D4"


# Goldens of what pybers cannot create yet, each naming the ticket that enables it.
enabledLaterGoldens: tuple[GoldenBuilder, ...] = (
    GoldenBuilder("13-formats-made-automatic-by-pybers", "13-number-percent",
                  writeAutomaticFormats, labeled=True,
                  sourceReason="PYB-233 enables pybers to create a percent format."),
    GoldenBuilder("20-formula-format-chosen-by-pybers", "20-formula-shapes",
                  chooseFormulaFormat,
                  sourceReason="PYB-198 enables pybers to calculate a created "
                  "formula's result, which its format must fit."),
    GoldenBuilder("11-controls-removed-by-pybers", "11-value-types-noformats",
                  removeControls, labeled=True,
                  sourceReason="PYB-240 to PYB-244 enable pybers to create controls."),
)


# The reason every golden confirmed before pybers could create a document gives.
confirmedBeforeCreation: str = (
    "Edits a document Numbers made, confirmed before pybers could create one."
)

createdGoldens: tuple[GoldenBuilder, ...] = (
    GoldenBuilder("00-created-blank-by-pybers", None, writeNothing),
    GoldenBuilder("00-created-sheets-added-by-pybers", None, addSheets),
    GoldenBuilder("00-created-tables-added-by-pybers", None, addTables),
    GoldenBuilder("00-created-formulas-in-tables-by-pybers", None,
                  addCreatedFormulaTables),
    GoldenBuilder("00-created-headers-set-by-pybers", None, setHeaders),
    GoldenBuilder("00-created-formats-chosen-by-pybers", None, chooseFormats),
    GoldenBuilder("00-created-formula-formats-chosen-by-pybers", None,
                  chooseFormulaFormats),
    GoldenBuilder("00-created-empty-formats-chosen-by-pybers", None,
                  chooseEmptyFormats),
    GoldenBuilder("00-created-cell-boxes-styled-by-pybers", None, setCellBoxes,
                  labeled=True),
    GoldenBuilder("00-created-cell-fills-colored-by-pybers", None, setCellFills,
                  labeled=True),
    GoldenBuilder("00-created-cell-boxes-updated-by-pybers", None, updateCellBoxes,
                  labeled=True),
    GoldenBuilder("00-created-cell-borders-drawn-by-pybers", None, applyCellBorders,
                  labeled=True),
    GoldenBuilder("00-created-table-lines-set-by-pybers", None, setTableLines,
                  labeled=True),
    GoldenBuilder("00-created-borders-edited-by-pybers", None, editBorderedLines,
                  labeled=True),
    GoldenBuilder("00-created-table-lines-deep-bands-by-pybers", None,
                  setDeepBandLines, labeled=True),
    GoldenBuilder("00-created-rows-banded-by-pybers", None, setBandedRows,
                  labeled=True),
)

# No golden joins this tuple, since one added from a measurement states its own reason.
confirmedOnNumbersDocuments: tuple[GoldenBuilder, ...] = (
    *(GoldenBuilder(f"95-region-{identifier.lower().replace('_', '-')}-by-pybers",
                    "95-region-base", setLocale(identifier), labeled=True)
      for identifier in measuredLocales),
    *(GoldenBuilder(name, source, writeValues(writes), labeled=True)
      for name, (source, writes) in kindWrites.items()),
    GoldenBuilder("12-currency-written-by-pybers", "92-values-for-currency",
                  writeValues(currencyWrites), labeled=True),
    GoldenBuilder("11-text-literal-written", "90d-values-for-literal-text",
                  writeLiterals, labeled=True),
    GoldenBuilder("18-formula-attached-and-detached", "93-formulas-for-attaching",
                  attachAndDetach, labeled=True),
    GoldenBuilder("18-formula-created-in-empty-cell", "93b-empty-for-a-formula",
                  createFormulaInEmptyCell, labeled=True),
    GoldenBuilder("18-formula-literals-A1-changed", "93c-formula-for-a-literal-change",
                  editLiteral, labeled=True),
    GoldenBuilder("18-merged-over-a-formula", "93d-formulas-for-a-merge",
                  mergeRange("A1:B1"), labeled=True),
    GoldenBuilder("19-formula-dragged-F2-narrowed", "19-formula-dragged",
                  editSharedRange),
    GoldenBuilder("20-cells-filled-named-by-pybers", "94-values-for-a-named-fill",
                  fillAcross(named), labeled=True),
    GoldenBuilder("20-cells-filled-relative-by-pybers",
                  "94b-values-for-a-relative-fill",
                  fillAcross(relative), labeled=True),
    GoldenBuilder("20-first-text-in-a-table", "20-formula-shapes", writeFirstText),
    GoldenBuilder("20-formula-authored-as-text", "20-formula-shapes",
                  writeFormulaTexts("Sheet 1", "Table 2", authoredFormulas)),
    GoldenBuilder("20-formula-brackets", "20-formula-shapes",
                  writeFormulaTexts("Sheet 1", "Table 2", bracketedFormulas)),
    GoldenBuilder("20-formula-precedent-replaced", "20-formula-shapes",
                  editPrecedent),
    GoldenBuilder("20-formula-retargeted", "94c-references-for-a-retarget",
                  relocateTable, labeled=True),
    GoldenBuilder("20-formula-rows-created", "20-formula-shapes",
                  writeFormulaTexts("Sheet 1", "Table 2", createdRowFormulas)),
    GoldenBuilder("20-formula-shapes-multisheet-edited", "20-formula-shapes",
                  editEveryNumber),
    GoldenBuilder("20-formulas-in-created-tables", "20-formula-shapes",
                  addFormulaTables),
    GoldenBuilder("20-functions-added-in-15-4-by-pybers", "20-formula-shapes",
                  writeFormulaTexts("Sheet 1", "Table 2", addedFunctionFormulas)),
    GoldenBuilder("20-sheets-added", "20-formula-shapes", addSheets),
    GoldenBuilder("20-tables-added", "20-formula-shapes", addTables),
    GoldenBuilder("20-whole-axis-ranges-and-booleans-by-pybers", "20-formula-shapes",
                  writeFormulaTexts("Sheet 1", "Table 2", typedFormulas)),
    GoldenBuilder("22-unmerged-by-pybers", "22-merge-2x2", removeMerges),
    GoldenBuilder("22b-merged-by-pybers", "22b-merge-2x2-unmerged", mergePairs),
    GoldenBuilder("22c-merged-by-pybers", "22c-merge-overpaints", mergeRange("L3:M3")),
    GoldenBuilder("45-merged-by-pybers", "45-columns-over-255", mergeRange("KI7:KJ7")),
    GoldenBuilder("56-column-added-by-pybers", "56-structure-base",
                  editStructure(lambda table: table.columnAdd("E"))),
    GoldenBuilder("56-column-removed-by-pybers", "56-structure-base",
                  editStructure(lambda table: table.columnRemove("E"))),
    GoldenBuilder("56-row-added-by-pybers", "56-structure-base",
                  editStructure(lambda table: table.rowAdd(3))),
    GoldenBuilder("56-row-removed-by-pybers", "56-structure-base",
                  editStructure(lambda table: table.rowRemove(8))),
    GoldenBuilder("60-move-cut-pasted-by-pybers", "60-move-base", moveBlock(relative)),
    GoldenBuilder("60-move-dragged-by-pybers", "60-move-base", moveBlock(named)),
    GoldenBuilder("61-cells-filled-by-pybers", "61-move-styles-base",
                  fillBlock("B2:D3", "B2:H7")),
    GoldenBuilder("61-lines-added-beside-no-border-by-pybers", "61-move-styles-base",
                  addLinesBesideNoBorder),
    GoldenBuilder("63-cells-filled-by-pybers", "63d-fill-border-base",
                  fillBlock("B2:D3", "B2:D7")),
    GoldenBuilder("64-cells-copied-named-by-pybers", "60-move-base", copyBlock(named)),
    GoldenBuilder("64-cells-copied-relative-by-pybers", "60-move-base",
                  copyBlock(relative)),
    *(GoldenBuilder(f"66-series-filled-{direction}-by-pybers",
                    "66-series-vertical-base" if direction in ("down", "up")
                    else "66-series-horizontal-base", fillSeriesCases(direction))
      for direction in ("down", "left", "right", "up")),
    GoldenBuilder("67-series-filled-by-pybers", "67-series-rich-base", fillRichSeries),
    GoldenBuilder("68-series-filled-by-pybers", "68-series-kinds-base", fillKindSeries),
)

goldens: tuple[GoldenBuilder, ...] = (
    *createdGoldens,
    *enabledLaterGoldens,
    *(dataclasses.replace(builder, sourceReason=confirmedBeforeCreation)
      for builder in confirmedOnNumbersDocuments),
)


def findBuilder(name: str) -> GoldenBuilder:
    """Return the builder of one golden, named without its extension."""
    return next(builder for builder in goldens if builder.name == name)


__all__ = [
    "GoldenBuilder", "buildGolden", "currencyWrites", "findBuilder", "findFirstTable",
    "findShownText",
    "findGoldenLabel", "formatGoldenLabel", "goldens", "labelRow", "listMeasuredCells",
    "measuredRow", "readMeasuredCells",
]

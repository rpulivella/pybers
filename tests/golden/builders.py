#!/usr/bin/env python3
"""\
How every golden is built: its source document and the mutation pybers writes into it.

The one place a golden's construction is written down. `test_goldens.py` rebuilds each
from here and compares the whole archive, and `--golden-write` writes each from here,
so no golden is made any other way. A test asserting what a golden holds reads its
writes from here rather than keeping a second copy.

UPDATES
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

@dataclass(frozen=True, slots=True)
class GoldenBuilder:
    """One golden: its name, the document it starts from, and what pybers writes.

    `labeled` marks a source laid out as a measurement, whose label beneath each
    cell the mutation changes is rewritten to say what pybers wrote.
    """

    name: str
    source: str
    mutate: Callable[[pybers.Document], None]
    labeled: bool = False


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
    merge = table.mergeCovering(address)
    if merge is not None and merge.anchor != address:
        return f"covered by the merge {merge.extent}"
    cell = table.cell(address)
    if cell.formula is not None:
        return cell.formulaText or ""
    return pybers.formatCellValue(cell.value)


def formatGoldenLabel(shown: str, sourceLabel: str) -> str:
    """Return the label beneath a cell pybers changed: what it wrote, and over what."""
    return f"written by pybers as {shown} over {sourceLabel}"


def listMeasuredCells(table: pybers.Table) -> list[pybers.CellAddress]:
    """Return the address of every measured cell, the row its labels describe."""
    return [pybers.CellAddress(measuredRow, column)
            for column in range(1, table.colCount + 1)]


def readMeasuredCells(table: pybers.Table) -> dict[pybers.CellAddress, tuple[str, str]]:
    """Return each measured cell's text and the label beneath it, by its address."""
    return {
        address: (findShownText(table, address),
                  str(table.cell(row=labelRow, col=address.col).value))
        for address in listMeasuredCells(table)
    }


def writeGoldenLabels(
    table: pybers.Table, before: dict[pybers.CellAddress, tuple[str, str]]
) -> None:
    """Rewrite the label beneath every measured cell the mutation changed."""
    for address, (shown, label) in before.items():
        now = findShownText(table, address)
        if now != shown:
            table.cell(row=labelRow, col=address.col).value = formatGoldenLabel(
                now, label
            )


def buildGolden(builder: GoldenBuilder, into: Path) -> Path:
    """Write a golden's mutation into a fresh copy of its source, and return it."""
    working = copyDocument(builder.source, into)
    with holdSeededIdentities(builder.name):
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


goldens: tuple[GoldenBuilder, ...] = (
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


def findBuilder(name: str) -> GoldenBuilder:
    """Return the builder of one golden, named without its extension."""
    return next(builder for builder in goldens if builder.name == name)


__all__ = [
    "GoldenBuilder", "buildGolden", "currencyWrites", "findBuilder", "findFirstTable",
    "findShownText",
    "formatGoldenLabel", "goldens", "labelRow", "listMeasuredCells", "measuredRow",
    "readMeasuredCells",
]

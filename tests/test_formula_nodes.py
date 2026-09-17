#!/usr/bin/env python3
"""\
Formulas read as the tree the file stores, asserted against measurements 18 to 21.

Every expectation here comes from a document whose formulas are known
independently, which is the only reason these assertions mean anything. This
format answers a wrong offset with a plausible wrong reference rather than an
exception: a relative offset read as an absolute coordinate still names a real
cell, and a sentinel read as a coordinate names one far outside the table.

Two facts these tests depend on were measured against every document on
2026-09-03 rather than read off the schema, which permits far more than Numbers
writes. A formula-backed cell names its formula in the FIRST of its trailing
references, established by reproducing every declared refcount in all nine tables
that declare formulas. And `ASTStickyBits` never accompanies a single-cell
reference, 0 of 21 in the documents, so anchoring for one is read from the coordinate
and nowhere else.

UPDATES
2026-09-03  Written for #41.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/03"

import dataclasses
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from conftest import findDocumentPath, readDataListBytes
from pybers import (
    Formula,
    FormulaFunctionCall,
    FormulaRange,
    FormulaUnknownCall,
    Span,
    toColumnLetter,
)
from pybers._persistence import readPackage
from pybers._persistence.types import readArchiveTypeId
from pybers.formula.nodes import FormulaError

# TST.TableInfoArchive, TSCE.CalculationEngineArchive and the owner_kind a table's
# dependency entry carries, named here rather than read from the writer's constants.
tableInfoTypeId: int = 6000
calculationEngineTypeId: int = 4000
tableOwnerKind: int = 1

# Function indices this file names for itself, measured against the document that
# holds them. Kept here rather than read from the function table, so a test of
# which formula a cell resolves to does not depend on what names that table gives.
spillIndex: int = 337
sequenceIndex: int = 338
makearrayIndex: int = 365
mapIndex: int = 366
lambdaApplyIndex: int = 372


def openFirstTable(name: str) -> pybers.Table:
    """Return the first table of a document, which is where these formulas live."""
    return pybers.open(findDocumentPath(name)).sheets[0].tables[0]


# ── AC 1: a formula is a structure, not a string ─────────────────────────────


def testFormulaCellYieldsNodesRatherThanText() -> None:
    """A formula reads back as its postfix node array.

    `=1+1` is three nodes and not the four characters that describe it, because
    the file holds no text to return. Numbers renders what a person sees from
    this tree every time it draws the cell.
    """
    formula = openFirstTable("18-formula-literals").cell("A1").formula
    assert formula is not None
    assert not isinstance(formula, str)
    assert [node.nodeType for node in formula] == [17, 17, 1]
    assert [node.content for node in formula] == [Decimal(1), Decimal(1), None]


def testNumberLiteralIsDecimalNeverFloat() -> None:
    """A literal decodes from decimal128, not from the float64 copy beside it.

    Both are stored. Reading the float would introduce binary rounding error into
    a document that never had any, and would do it silently.
    """
    formula = openFirstTable("18-formula-literals").cell("E1").formula
    assert formula is not None
    literals = [node.content for node in formula if isinstance(node.content, Decimal)]
    assert literals == [Decimal("2.5"), Decimal(0)]
    assert all(not isinstance(value, float) for value in literals)


def testStringLiteralAndFunctionCallCarryTheirOwnContent() -> None:
    """A string literal holds its text and a call holds its index and arity."""
    concatenation = openFirstTable("18-formula-literals").cell("G1").formula
    assert concatenation is not None
    assert [node.content for node in concatenation][:2] == ["a", "b"]

    summed = openFirstTable("18-formula-literals").cell("C1").formula
    assert summed is not None
    call = summed.nodes[-1].content
    assert isinstance(call, FormulaFunctionCall)
    # 168 is SUM in Apple's own table. Deriving a name map is separate work, so
    # this asserts the number the archive holds and claims nothing more.
    assert (call.index, call.argumentCount) == (168, 3)


# ── AC 2: anchoring is per axis ──────────────────────────────────────────────


def testMixedLockingIsPerAxisOnOneReference() -> None:
    """`$B1` and `C$1` in one formula, an absolute column beside a relative row.

    A single flag per reference cannot represent this, which is why locking is
    two booleans rather than punctuation inside a string.
    """
    references = openFirstTable("19-formula-dragged").cell("G2").formula.references
    assert len(references) == 2
    column, row = references[0], references[1]
    assert (column.column.absolute, column.row.absolute) == (True, False)
    assert (row.column.absolute, row.row.absolute) == (False, True)


def testRelativeReferenceResolvesAgainstTheCellHoldingIt() -> None:
    """One stored archive serving two cells resolves differently in each.

    `19-formula-dragged` carries every formula at refcount 2, a single archive
    shared by the original and its dragged copy. That is only possible because an
    unlocked reference is a signed offset from whichever cell holds it, and it is
    why moving a formula needs no rewriting at all.
    """
    table = openFirstTable("19-formula-dragged")
    second = table.cell("G2").formula.references
    third = table.cell("G3").formula.references

    # The locked column stays put while the relative row follows the cell down.
    assert str(second[0].resolve(pybers.CellReference.parse("G2"))) == "$B1"
    assert str(third[0].resolve(pybers.CellReference.parse("G3"))) == "$B2"
    # The locked row does not move at all, which is what locking means.
    assert str(second[1].resolve(pybers.CellReference.parse("G2"))) == "C$1"
    assert str(third[1].resolve(pybers.CellReference.parse("G3"))) == "C$1"


def testCrossTableReferenceNamesItsTargetByIdentity() -> None:
    """A reference into another table carries a UUID rather than a name.

    Numbers writes the compact form with one extra field rather than the
    `ASTCrossTableCellReferenceNodeArchive` the schema also permits, so a reader
    has to handle what is written rather than what is allowed.
    """
    table = openFirstTable("20-formula-shapes")
    reference = table.cell("G11").formula.references[0]
    assert reference.crossTable
    assert reference.tableId
    # Naming by identity is what makes renaming the target table harmless.
    assert not reference.tableId.isspace()
    assert str(reference.resolve(pybers.CellReference.parse("G11"))) == "A1"


def testASpanOfOneLineOmitsItsEndRatherThanRepeatingIt() -> None:
    """An absent `end` means a span of one, which `last` is what absorbs.

    `SUM(A1:A10)` spans ten rows in one column, so its column axis has no end at
    all. A caller reading `end` directly would see None and have to know the rule;
    reading `last` does not.
    """
    columns = openFirstTable("20-formula-shapes").cell("A11").formula.ranges[0].columns
    assert columns is not None
    assert columns.end is None, "a one-column span omits its end"
    assert columns.last == columns.begin

    rows = openFirstTable("20-formula-shapes").cell("A11").formula.ranges[0].rows
    assert rows is not None
    assert rows.end is not None and rows.last == rows.end


def testARangeResolvesToAnOrdinaryCellRange() -> None:
    """A formula's range rejoins the addressing the rest of the library uses.

    The counterpart of resolving a reference to a `CellReference`. `E2` and `E3`
    share ONE stored archive at refcount 2, so a relative range proving to cover
    different rectangles in each is the offset rule stated in range vocabulary.
    """
    table = openFirstTable("19-formula-dragged")
    relativeSecond = table.cell("E2").formula.ranges[0]
    relativeThird = table.cell("E3").formula.ranges[0]
    assert relativeSecond == relativeThird, "one archive, shared"
    assert str(relativeSecond.resolve(pybers.CellReference.parse("E2"))) == "B1:D1"
    assert str(relativeThird.resolve(pybers.CellReference.parse("E3"))) == "B2:D2"

    # A locked range does not move, and its markers survive into the CellRange.
    lockedSecond = table.cell("F2").formula.ranges[0]
    lockedThird = table.cell("F3").formula.ranges[0]
    for reference, extent in (("F2", lockedSecond), ("F3", lockedThird)):
        resolved = extent.resolve(pybers.CellReference.parse(reference))
        assert str(resolved) == "$B$1:$D$1"


def testAnUnboundedRangeAxisStaysUnboundedWhenResolved() -> None:
    """An axis a range leaves out stays out, rather than spanning every row.

    `CellRange` represents a whole column as absence too, so the two agree. No
    document carries an unbounded RANGE, only an unbounded reference, so this is
    built rather than read.
    """
    wholeColumn = FormulaRange(columns=Span(begin=2, absolute=True), rows=None)
    resolved = wholeColumn.resolve(pybers.CellReference.parse("A5"))
    assert resolved.rowsUnbounded
    assert not resolved.colsUnbounded
    assert str(resolved) == "$B"


def testMultiRangeCallCarriesEachRangeSeparately() -> None:
    """`SUMIFS` decodes to two independent range tracts, not one.

    Each range is its own node with its own anchoring, so adjusting one cannot
    disturb the other. A walk that stopped at the first range in a node array
    would silently miss the rest of the argument list.
    """
    ranges = openFirstTable("20-formula-shapes").cell("C11").formula.ranges
    assert len(ranges) == 2
    assert all(isinstance(extent, FormulaRange) for extent in ranges)


# ── AC 2.i: unboundedness is absence ─────────────────────────────────────────


def testWholeColumnReferenceHasNoRowAtAll() -> None:
    """`SUM(A)` stores a column and no row, rather than row zero or a sentinel.

    Row zero would be a real cell, and a range standing in for the whole column
    would compare equal to a bounded one spanning the same cells while meaning
    something different.
    """
    reference = openFirstTable("20-formula-shapes").cell("F11").formula.references[0]
    assert reference.column is not None
    assert reference.row is None
    with pytest.raises(FormulaError, match="unbounded"):
        reference.resolve(pybers.CellReference.parse("F11"))


# ── AC 2.ii: a broken reference says so ──────────────────────────────────────


def testBrokenReferenceReportsBrokenRatherThanColumn32767() -> None:
    """A deleted reference is recognized, not read as a cell far off the grid.

    The sentinels are the maximum int16 and int32, which parse as ordinary
    coordinates and raise nothing, so recognizing them is the only thing standing
    between a caller and a plausible wrong answer.
    """
    formula = openFirstTable("21-formula-errors").cell("C1").formula
    assert formula is not None
    assert formula.broken
    reference = formula.references[0]
    assert reference.broken
    assert reference.column is None and reference.row is None
    with pytest.raises(FormulaError, match="broken"):
        reference.resolve(pybers.CellReference.parse("C1"))


# ── AC 3: one cell's formula cannot reach another's ──────────────────────────


def testFormulaIsFrozenSoASharedOneCannotBeEditedThroughACell() -> None:
    """Formula and every part of it are frozen, the read-path half of the contract.

    Numbers shares one archive between every cell a formula was dragged into, so
    a model handing out something mutable would turn one edit into a silent edit
    of all of them. This is the same defect the frozen `Style` closes, and the
    format creates the hazard rather than any implementation inviting it.
    """
    formula = openFirstTable("19-formula-dragged").cell("E2").formula
    assert formula is not None
    node = formula.nodes[0]
    extent = formula.ranges[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        formula.nodes = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.nodeType = 0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        extent.columns = None  # type: ignore[misc]
    assert extent.columns is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        extent.columns.begin = 0  # type: ignore[misc]


def testReplacingOneCellsFormulaLeavesItsSiblingAlone() -> None:
    """Two cells sharing one archive, and only one of them changes.

    `19-formula-dragged` carries refcount 2 on every formula, so this is the real
    shared case rather than a constructed one.
    """
    table = openFirstTable("19-formula-dragged")
    assert table.cell("E2").formula == table.cell("E3").formula
    table.cell("E2").formula = Formula(nodes=())
    assert len(table.cell("E3").formula) == 2


# ── AC 4: the round trip changes nothing ─────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["18-formula-literals", "19-formula-dragged",
     "20-formula-shapes", "21-formula-errors",
     "46-formula-rare-functions"],
)
def testUnchangedRoundTripLeavesEveryPooledListByteIdentical(
    name: str, tmp_path: Path
) -> None:
    """Reading and writing back with no edit rewrites no formula at all.

    Compared at the archive bytes rather than through the model, because a model
    comparison would agree with itself while both halves were wrong.
    """
    source = findDocumentPath(name)
    target = tmp_path / f"{name}.numbers"
    pybers.open(source).save(target)
    assert readDataListBytes(source) == readDataListBytes(target)


@pytest.mark.parametrize(
    "name",
    ["18-formula-literals", "19-formula-dragged",
     "20-formula-shapes", "21-formula-errors",
     "46-formula-rare-functions"],
)
def testEveryFormulaSurvivesTheRoundTripThroughTheModel(
    name: str, tmp_path: Path
) -> None:
    """Every formula reads back equal after a save, cell for cell."""
    source = findDocumentPath(name)
    target = tmp_path / f"{name}.numbers"
    before = pybers.open(source)
    before.save(target)
    after = pybers.open(target)

    for sheetBefore, sheetAfter in zip(before.sheets, after.sheets, strict=True):
        for tableBefore, tableAfter in zip(
            sheetBefore.tables, sheetAfter.tables, strict=True
        ):
            for reference, cell in tableBefore.cells.items():
                assert cell.formula == tableAfter.cells[reference].formula


# ── AC 4.i and 4.ii: what the model does not understand survives ─────────────


def testUnrecognizedNodeKeepsItsBytesForRewriting() -> None:
    """An operator carries no content, and its own bytes come back with it.

    The node message has 45 fields and this model gives meaning to 16, so a node
    rebuilt from the model alone would silently drop whatever else it held. The
    bytes are what make a rewritten formula safe for the nodes nobody modeled.
    """
    formula = openFirstTable("18-formula-literals").cell("A1").formula
    operator = formula.nodes[-1]
    assert operator.content is None
    assert not operator.recognized
    assert operator.raw, "an unrecognized node keeps its archive bytes"


def testUnknownFunctionKeepsItsSpelling() -> None:
    """A function Numbers could not resolve survives with its name intact.

    Numbers preserves the text rather than discarding the formula, the same
    instinct this library applies to an unrecognized cell type.
    """
    formula = openFirstTable("21-formula-errors").cell("D1").formula
    assert formula is not None
    unknown = [
        node.content for node in formula
        if isinstance(node.content, FormulaUnknownCall)
    ]
    assert len(unknown) == 1
    assert unknown[0].name == "UNKNOWNFUNC"


def testAStyledCellStillResolvesToItsOwnFormula() -> None:
    """A reference ahead of the formula key must not shift what a cell reads as.

    Byte 8 bit 0x40 puts one reference before the key, and 46 is the only
    document that sets it, because its cells carry a text color. Read at a fixed
    slot every one of its twenty formulas resolved to the same wrong pooled
    entry, naming every call TEXT, which is a plausible wrong answer rather than
    an exception.
    """
    table = openFirstTable("46-formula-rare-functions")
    called = {}
    for address, cell in table.cells.items():
        if cell.formula is None:
            continue
        for node in cell.formula:
            call = node.content
            if isinstance(call, FormulaFunctionCall):
                called[f"{toColumnLetter(address.col)}{address.row}"] = call.index
    # Indices rather than names, so this tests which formula a cell resolves to
    # and not what the function table happens to call it.
    assert called["B13"] == lambdaApplyIndex
    assert called["B14"] == mapIndex
    assert called["C15"] == makearrayIndex
    assert called["B17"] == sequenceIndex
    assert sum(1 for index in called.values() if index == spillIndex) == 5


def testEverySpilledCellHoldsSpillOfItsAnchor() -> None:
    """A spill is ordinary formula cells, not a range recorded somewhere else.

    Each cell a formula spills into holds `SPILL($anchor)` with an absolute
    reference, which is what lets one pooled archive serve every follower of one
    anchor. Measured on the MAKEARRAY at C15 and the SEQUENCE at B17.
    """
    table = openFirstTable("46-formula-rare-functions")
    followers = [
        cell for cell in table.cells.values()
        if cell.formula is not None
        and any(
            isinstance(node.content, FormulaFunctionCall)
            and node.content.index == spillIndex
            for node in cell.formula
        )
    ]
    assert len(followers) == 5
    for cell in followers:
        references = cell.formula.references
        assert len(references) == 1
        assert references[0].column is not None and references[0].column.absolute
        assert references[0].row is not None and references[0].row.absolute


# ── AC 5: a changed formula writes back ──────────────────────────────────────


def testChangedFormulaIsWrittenAndReadsBackChanged(tmp_path: Path) -> None:
    """One literal changed in a formula, saved, and read back as changed."""
    source = shutil.copy(findDocumentPath("18-formula-literals"),
                         tmp_path / "18.numbers")
    document = pybers.open(source)
    cell = document.sheets[0].tables[0].cell("A1")
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(5))
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    after = pybers.open(source).sheets[0].tables[0].cell("A1")
    assert [node.content for node in after.formula] == [
        Decimal(1), Decimal(5), None
    ]
    # The cached result is deliberately left stale. This library never evaluates
    # a formula; it names the changed cell and Numbers does the arithmetic.
    assert after.value == Decimal(2)


def testChangingOneSharedFormulaSplitsThePoolRatherThanEditingBoth(
    tmp_path: Path,
) -> None:
    """The write-path half of the aliasing contract, on a real refcount-2 archive.

    Overwriting the entry in place would edit both cells at once, which is
    precisely the defect the frozen model closes on the read side.
    """
    source = shutil.copy(findDocumentPath("19-formula-dragged"),
                         tmp_path / "19.numbers")
    document = pybers.open(source)
    table = document.sheets[0].tables[0]
    nodes = list(table.cell("E2").formula.nodes)
    nodes[-1] = dataclasses.replace(
        nodes[-1], content=FormulaFunctionCall(index=169, argumentCount=1)
    )
    table.cell("E2").formula = Formula(nodes=tuple(nodes))
    document.save()

    after = pybers.open(source).sheets[0].tables[0]
    assert after.cell("E2").formula.nodes[-1].content == FormulaFunctionCall(169, 1)
    assert after.cell("E3").formula.nodes[-1].content == FormulaFunctionCall(168, 1)


def testChangedFormulaMarksItsCellForRecalculation(tmp_path: Path) -> None:
    """A formula edit populates `refs_to_dirty`, which is what makes Numbers recompute.

    Numbers does not recalculate on open, measured for PYB-25, so an edit that
    did not mark its cell would leave the old result on screen indefinitely.
    A clean document serializes this archive to zero bytes, so any content at all
    is the request having been made.
    """
    from pybers._generated import TSCEArchives_pb2 as tsce
    from pybers._persistence.index import ArchiveIndex

    def readDirtyBytes(path: Path) -> int:
        index = ArchiveIndex(readPackage(path))
        for archive in list(index.byIdentifier.values()):
            if readArchiveTypeId(archive) != 4000:
                continue
            from pybers._persistence.types import parseArchive
            engine = parseArchive(archive)
            if not engine.HasField("refs_to_dirty"):
                continue
            return len(
                index.resolve(
                    engine.refs_to_dirty, tsce.ReferencesToDirtyArchive
                ).SerializeToString()
            )
        return 0

    source = shutil.copy(findDocumentPath("18-formula-literals"),
                         tmp_path / "18.numbers")
    assert readDirtyBytes(Path(source)) == 0, "a clean document asks for nothing"

    document = pybers.open(source)
    cell = document.sheets[0].tables[0].cell("A1")
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(5))
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    assert readDirtyBytes(Path(source)) > 0


# ── AC 6: a failed formula says so, and no more ──────────────────────────────


def testErroredCellReportsErroredAndInventsNoKind() -> None:
    """A failed formula is reported as failed, with its formula still readable.

    The file records THAT a cell errored and never why: the error list is empty
    in every document, so division by zero is indistinguishable from any other
    failure. A broken reference is the one exception, and it is visible through
    the formula rather than through the cell.
    """
    table = openFirstTable("21-formula-errors")
    errored = {
        str(reference): cell for reference, cell in table.cells.items()
        if cell.errored
    }
    assert errored, "21-formula-errors carries error cells"
    for cell in errored.values():
        assert cell.formula is not None, "an error cell keeps its formula"
        assert cell.value is None, "and holds no result"
    # The one failure the file explains, and the only one this library may explain.
    assert errored["C1"].formula.broken
    assert not errored["B1"].formula.broken


def testAnOrdinaryFormulaCellIsNotReportedAsErrored() -> None:
    """Guard the guard: a flag that were always true would pass the test above."""
    cell = openFirstTable("18-formula-literals").cell("A1")
    assert cell.formula is not None
    assert not cell.errored


# ── AC 5: the golden files ───────────────────────────────────────────────────

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"


def testChangedLiteralMatchesItsGoldenFile(tmp_path: Path) -> None:
    """One literal changed, compared against output confirmed in Numbers itself.

    Every other test here checks pybers against pybers, which can agree with
    itself while both halves are wrong. See `tests/golden/README.md` for the
    confirmation state of this file.
    """
    golden = goldenDirectory / "18-formula-literals-A1-changed.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = shutil.copy(findDocumentPath("18-formula-literals"),
                          tmp_path / "18.numbers")
    document = pybers.open(working)
    cell = document.sheets[0].tables[0].cell("A1")
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(5))
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    assert readDataListBytes(golden) == readDataListBytes(Path(working)), (
        "the writer no longer produces the confirmed formula lists"
    )


def testNarrowedSharedRangeMatchesItsGoldenFile(tmp_path: Path) -> None:
    """One of two cells sharing an archive, narrowed, against confirmed output."""
    golden = goldenDirectory / "19-formula-dragged-F2-narrowed.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = shutil.copy(findDocumentPath("19-formula-dragged"),
                          tmp_path / "19.numbers")
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    nodes = list(table.cell("F2").formula.nodes)
    extent = nodes[0].content
    nodes[0] = dataclasses.replace(
        nodes[0],
        content=dataclasses.replace(
            extent, columns=dataclasses.replace(extent.columns, end=3)
        ),
    )
    table.cell("F2").formula = Formula(nodes=tuple(nodes))
    document.save()

    assert readDataListBytes(golden) == readDataListBytes(Path(working)), (
        "the writer no longer produces the confirmed formula lists"
    )


def testTheGoldenFilesHoldWhatTheyClaimTo() -> None:
    """Guard the guard: a golden replaced by an unedited copy would pass silently.

    The two tests above compare files this library produced against each other,
    so each golden's own contents are asserted here as well.
    """
    changed = pybers.open(
        goldenDirectory / "18-formula-literals-A1-changed.numbers"
    ).sheets[0].tables[0]
    assert [node.content for node in changed.cell("A1").formula] == [
        Decimal(1), Decimal(5), None
    ]
    # The cached result is deliberately stale, since pybers never evaluates.
    assert changed.cell("A1").value == Decimal(2)

    narrowed = pybers.open(
        goldenDirectory / "19-formula-dragged-F2-narrowed.numbers"
    ).sheets[0].tables[0]
    assert narrowed.cell("F2").formula.ranges[0].columns.end == 3
    # The sibling that shares the original archive keeps its own span, which is
    # the whole point of splitting a pooled entry rather than overwriting it.
    assert narrowed.cell("F3").formula.ranges[0].columns.end == 4


# ── AC 6 and AC 7: attaching and detaching a formula ─────────────────────────


def readFormulaRecords(path: Path, name: str) -> list[tuple[int, int, int]]:
    """Return (row, column, formula key) for every formula-backed cell of a table."""
    from pybers._generated import TSTArchives_pb2 as tst
    from pybers._persistence import carriesFormula, chooseOffsetUnit, decodeRow
    from pybers._persistence.index import ArchiveIndex
    from pybers._persistence.types import parseArchive, readArchiveTypeId
    from pybers.formula._write import findFormulaKeySlot

    index = ArchiveIndex(readPackage(path))
    found: list[tuple[int, int, int]] = []
    for archive in list(index.byIdentifier.values()):
        if readArchiveTypeId(archive) != tableInfoTypeId:
            continue
        model = index.resolve(parseArchive(archive).tableModel,
                              tst.TableModelArchive)
        if model.table_name != name:
            continue
        store = model.base_data_store
        for entry in store.tiles.tiles:
            tile = index.resolve(entry.tile, tst.Tile)
            for rowInfo in tile.rowInfos:
                unit = chooseOffsetUnit(
                    rowInfo.has_wide_offsets, tile.should_use_wide_rows
                )
                row = entry.tileid * store.tiles.tile_size + rowInfo.tile_row_index
                for record in decodeRow(rowInfo.cell_offsets,
                                        rowInfo.cell_storage_buffer, unit):
                    if carriesFormula(record):
                        found.append(
                            (row, record.column,
                             record.references[findFormulaKeySlot(record)])
                        )
    return found


def readFormulaCellRegister(path: Path) -> tuple[list[tuple[int, int]], ...]:
    """Return the engine's two registers of formula-bearing cells, zero-based.

    Both are returned so a test can assert they agree. A stale one renders
    correctly today and lies about the document.
    """
    from pybers._generated import TSCEArchives_pb2 as tsce
    from pybers._persistence.index import ArchiveIndex
    from pybers._persistence.types import parseArchive

    index = ArchiveIndex(readPackage(path))
    for archive in list(index.byIdentifier.values()):
        if readArchiveTypeId(archive) != calculationEngineTypeId:
            continue
        engine = parseArchive(archive)
        for reference in engine.dependency_tracker.formula_owner_dependencies:
            owner = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
            if owner.owner_kind != tableOwnerKind:
                continue
            expanded = sorted(
                (record.row, record.column)
                for record in owner.cell_dependencies.cell_record
            )
            tiled = sorted(
                (record.row, record.column)
                for tile in owner.tiled_cell_dependencies.cell_record_tiles
                for record in index.resolve(
                    tile, tsce.CellRecordTileArchive
                ).cell_records
            )
            return expanded, tiled
    return [], []


def testAttachingAFormulaToAValueCellRegistersItInBothRegisters(
    tmp_path: Path,
) -> None:
    """AC 6. A cell that held only a value carries a formula afterward.

    The register assertion is the point. A formula whose cell is missing from
    either register is never evaluated, and Numbers gives no warning: it shows the
    formula in its formula bar and the old value in the grid.
    """
    working = Path(shutil.copy(findDocumentPath("18-formula-literals"),
                               tmp_path / "18.numbers"))
    before = readFormulaCellRegister(working)
    assert (1, 0) not in before[0], "A2 holds no formula in the measurement"

    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    assert table.cell("A2").formula is None
    table.cell("A2").formula = table.cell("A1").formula
    document.save()

    after = pybers.open(working).sheets[0].tables[0].cell("A2")
    assert after.formula is not None
    assert [node.content for node in after.formula] == [
        Decimal(1), Decimal(1), None
    ]
    # The label it held is left as the placeholder, which Numbers repairs.
    assert after.value == "1+1"

    expanded, tiled = readFormulaCellRegister(working)
    assert (1, 0) in expanded
    assert expanded == tiled, "the two registers must agree"


def testDetachingAFormulaKeepsTheValueAndDeregistersTheCell(
    tmp_path: Path,
) -> None:
    """AC 7. The formula goes, the result it last computed stays."""
    working = Path(shutil.copy(findDocumentPath("18-formula-literals"),
                               tmp_path / "18.numbers"))
    assert (0, 1) in readFormulaCellRegister(working)[0], "B1 holds a formula"

    document = pybers.open(working)
    document.sheets[0].tables[0].cell("B1").formula = None
    document.save()

    after = pybers.open(working).sheets[0].tables[0].cell("B1")
    assert after.formula is None
    assert after.value == Decimal(6), "the last computed result survives"

    expanded, tiled = readFormulaCellRegister(working)
    assert (0, 1) not in expanded, "a stale entry claims a formula that is gone"
    assert expanded == tiled


def testChangingOneCellsFormulaLeavesTheRegisterAlone(tmp_path: Path) -> None:
    """Guard the guard: only attach and detach may move the register.

    Replacing a formula changes neither which cells hold one nor how many, so a
    register that grew or shrank here would mean the four-way decision misread a
    replacement as an attach.
    """
    working = Path(shutil.copy(findDocumentPath("18-formula-literals"),
                               tmp_path / "18.numbers"))
    before = readFormulaCellRegister(working)

    document = pybers.open(working)
    cell = document.sheets[0].tables[0].cell("A1")
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(9))
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    assert readFormulaCellRegister(working) == before


def testAttachAndDetachMatchTheirGoldenFile(tmp_path: Path) -> None:
    """The pair above, against output confirmed in Numbers itself.

    Confirmed 2026-09-04 on the third attempt. The first two produced a file that
    read back perfectly through pybers and was wrong in Numbers, which is what a
    golden exists to catch. See `tests/golden/README.md`.
    """
    golden = goldenDirectory / "18-formula-attached-and-detached.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = Path(shutil.copy(findDocumentPath("18-formula-literals"),
                               tmp_path / "18.numbers"))
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("A2").formula = table.cell("A1").formula
    table.cell("B1").formula = None
    document.save()

    assert readDataListBytes(golden) == readDataListBytes(working)
    assert readFormulaCellRegister(golden) == readFormulaCellRegister(working)


def testTheAttachGoldenHoldsWhatItClaimsTo() -> None:
    """Guard the guard, against the values confirmed on screen on 2026-09-04."""
    table = pybers.open(
        goldenDirectory / "18-formula-attached-and-detached.numbers"
    ).sheets[0].tables[0]

    assert table.cell("A2").formula is not None, "A2 gained a formula"
    assert table.cell("B1").formula is None, "B1 lost one"
    assert table.cell("B1").value == Decimal(6)
    # Untouched cells keep their own formulas.
    assert table.cell("C1").formula is not None
    assert table.cell("G1").value == "ab"

    expanded, tiled = readFormulaCellRegister(
        goldenDirectory / "18-formula-attached-and-detached.numbers"
    )
    assert (1, 0) in expanded and (0, 1) not in expanded
    assert expanded == tiled


# ── AC 1, 2, 3 and 5: writing a formula into a cell that had no record ────────


def testAFormulaReachesACellWithNoRecordAtAll(tmp_path: Path) -> None:
    """AC 1 and AC 2. `H1` of 18 is genuinely empty, its own label saying so.

    A record has to be CREATED, which the writer could only patch before. The
    offset array already carries a slot for every column, so nothing grows.
    """
    working = Path(shutil.copy(findDocumentPath("18-formula-literals"),
                               tmp_path / "18.numbers"))
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    assert table.cell("H1").value is None and table.cell("H1").formula is None
    assert table.cell("H2").value == "empty", "the measurement labels it so"

    table.cell("H1").formula = table.cell("C1").formula   # =SUM(1,2,3)
    document.save()

    after = pybers.open(working).sheets[0].tables[0].cell("H1")
    assert after.formula == pybers.open(
        findDocumentPath("18-formula-literals")
    ).sheets[0].tables[0].cell("C1").formula
    call = after.formula.nodes[-1].content
    assert isinstance(call, FormulaFunctionCall)
    # AC 5: the function is named by the numeric index the archive stores.
    assert (call.index, call.argumentCount) == (168, 3)

    expanded, tiled = readFormulaCellRegister(working)
    assert (0, 7) in expanded and expanded == tiled


def testACreatedFormulaStoresNoResultOfItsOwn(tmp_path: Path) -> None:
    """AC 3. pybers evaluates nothing, so a new formula caches nothing.

    The record is type 8, the shape Numbers writes for a formula it could not
    compute, which is honestly what this is until Numbers recalculates. Confirmed
    on screen: the cell shows 6 in Numbers and nothing in Quick Look.
    """
    working = Path(shutil.copy(findDocumentPath("18-formula-literals"),
                               tmp_path / "18.numbers"))
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    table.cell("H1").formula = table.cell("C1").formula
    document.save()

    after = pybers.open(working).sheets[0].tables[0].cell("H1")
    assert after.value is None, "no result is stored, because none was computed"
    assert after.errored, "which is the pending state, not a failure"


# ── AC 4: one formula, filled ────────────────────────────────────────────────


def testFillGivesEveryCellTheSameStoredFormula(tmp_path: Path) -> None:
    """AC 4. Four cells, ONE entry, and each resolving against its own column.

    This is what dragging does in Numbers, reproduced by doing the same thing
    rather than by simulating it. An implementation writing a formula per row
    would pass every other assertion here and fail the refcount.
    """
    working = Path(shutil.copy(findDocumentPath("20-formula-shapes"),
                               tmp_path / "20.numbers"))
    document = pybers.open(working)
    table = document.sheets[0].tables[0]
    assert table.formulaFill("A11", through="A11:D11") == 3
    document.save()

    after = pybers.open(working).sheets[0].tables[0]
    for reference, expected in (("A11", "A1:A10"), ("B11", "B1:B10"),
                                ("C11", "C1:C10"), ("D11", "D1:D10")):
        cell = after.cell(reference)
        assert str(cell.formula.ranges[0].resolve(cell.reference)) == expected

    keys = {
        key for row, column, key in readFormulaRecords(working, "Table 1")
        if row == 10 and column < 4
    }
    assert len(keys) == 1, "all four cells name ONE stored formula"


def testFillLeavesEveryCellOutsideTheRangeAlone(tmp_path: Path) -> None:
    """Guard the guard: a fill that reached too far would still pass the above.

    `E11` through `H11` include a cross-table and a cross-sheet reference, which
    are the ones a careless range walk would take with it.
    """
    working = Path(shutil.copy(findDocumentPath("20-formula-shapes"),
                               tmp_path / "20.numbers"))
    before = {
        reference: cell.formula
        for reference, cell in
        pybers.open(working).sheets[0].tables[0].cells.items()
    }
    document = pybers.open(working)
    document.sheets[0].tables[0].formulaFill("A11", through="A11:D11")
    document.save()

    after = pybers.open(working).sheets[0].tables[0]
    for name in ("E11", "F11", "G11", "H11"):
        reference = pybers.CellReference.parse(name)
        assert after.cells[reference].formula == before[reference], name
    assert after.cell("G11").formula.references[0].crossTable


def testFillRefusesWhenTheSourceHoldsNoFormula() -> None:
    """A no-op must report accurately rather than filling nothing in silence."""
    table = openFirstTable("20-formula-shapes")
    with pytest.raises(pybers.ReferenceError, match="no formula"):
        table.formulaFill("A1", through="A1:D1")

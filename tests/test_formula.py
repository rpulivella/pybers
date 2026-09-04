#!/usr/bin/env python3
"""\
Formulas read as the tree the file stores, asserted against fixtures 18 to 21.

Every expectation here comes from a fixture whose formulas are known
independently, which is the only reason these assertions mean anything. This
format answers a wrong offset with a plausible wrong reference rather than an
exception: a relative offset read as an absolute coordinate still names a real
cell, and a sentinel read as a coordinate names one far outside the table.

Two facts these tests depend on were measured against the whole corpus on
2026-09-03 rather than read off the schema, which permits far more than Numbers
writes. A formula-backed cell names its formula in the FIRST of its trailing
references, established by reproducing every declared refcount in all nine tables
that declare formulas. And `ASTStickyBits` never accompanies a single-cell
reference, 0 of 21 in the corpus, so anchoring for one is read from the coordinate
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
from pybers import (
    Formula,
    FormulaRange,
    FunctionCall,
    Span,
    UnknownFunction,
)
from pybers.model.formula import FormulaError
from pybers.numbersfile import readPackage
from pybers.numbersfile.types import archiveTypeId

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

# TST.TableDataList, so a test can compare the pooled lists of two packages
# without reaching for the writer's own constants.
dataListTypeId: int = 6005


def fixturePath(name: str) -> Path:
    """Return a fixture path, skipping when it has not been made yet."""
    path = fixtureDirectory / f"{name}.numbers"
    if not path.is_file():
        pytest.skip(f"Fixture {path.name} is not present.")
    return path


def firstTable(name: str) -> pybers.Table:
    """Return the first table of a fixture, which is where these formulas live."""
    return pybers.open(fixturePath(name)).sheets[0].tables[0]


def dataListBytes(path: Path) -> dict[int, bytes]:
    """Return every pooled data list in a package, keyed by archive identifier."""
    package = readPackage(path)
    return {
        archive.identifier: b"".join(message.data for message in archive.messages)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        if archiveTypeId(archive) == dataListTypeId
    }


# ── AC 1: a formula is a structure, not a string ─────────────────────────────


def testFormulaCellYieldsNodesRatherThanText() -> None:
    """A formula reads back as its postfix node array.

    `=1+1` is three nodes and not the four characters that describe it, because
    the file holds no text to return. Numbers renders what a person sees from
    this tree every time it draws the cell.
    """
    formula = firstTable("18-formula-literals").cell("A1").formula
    assert formula is not None
    assert not isinstance(formula, str)
    assert [node.nodeType for node in formula] == [17, 17, 1]
    assert [node.content for node in formula] == [Decimal(1), Decimal(1), None]


def testNumberLiteralIsDecimalNeverFloat() -> None:
    """A literal decodes from decimal128, not from the float64 copy beside it.

    Both are stored. Reading the float would introduce binary rounding error into
    a document that never had any, and would do it silently.
    """
    formula = firstTable("18-formula-literals").cell("E1").formula
    assert formula is not None
    literals = [node.content for node in formula if isinstance(node.content, Decimal)]
    assert literals == [Decimal("2.5"), Decimal(0)]
    assert all(not isinstance(value, float) for value in literals)


def testStringLiteralAndFunctionCallCarryTheirOwnContent() -> None:
    """A string literal holds its text and a call holds its index and arity."""
    concatenation = firstTable("18-formula-literals").cell("G1").formula
    assert concatenation is not None
    assert [node.content for node in concatenation][:2] == ["a", "b"]

    summed = firstTable("18-formula-literals").cell("C1").formula
    assert summed is not None
    call = summed.nodes[-1].content
    assert isinstance(call, FunctionCall)
    # 168 is SUM in Apple's own table. Deriving a name map is separate work, so
    # this asserts the number the archive holds and claims nothing more.
    assert (call.index, call.argumentCount) == (168, 3)


# ── AC 2: anchoring is per axis ──────────────────────────────────────────────


def testMixedLockingIsPerAxisOnOneReference() -> None:
    """`$B1` and `C$1` in one formula, an absolute column beside a relative row.

    A single flag per reference cannot represent this, which is why locking is
    two booleans rather than punctuation inside a string.
    """
    references = firstTable("19-formula-dragged").cell("G2").formula.references
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
    table = firstTable("19-formula-dragged")
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
    table = firstTable("20-formula-shapes")
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
    columns = firstTable("20-formula-shapes").cell("A11").formula.ranges[0].columns
    assert columns is not None
    assert columns.end is None, "a one-column span omits its end"
    assert columns.last == columns.begin

    rows = firstTable("20-formula-shapes").cell("A11").formula.ranges[0].rows
    assert rows is not None
    assert rows.end is not None and rows.last == rows.end


def testARangeResolvesToAnOrdinaryCellRange() -> None:
    """A formula's range rejoins the addressing the rest of the library uses.

    The counterpart of resolving a reference to a `CellReference`. `E2` and `E3`
    share ONE stored archive at refcount 2, so a relative range proving to cover
    different rectangles in each is the offset rule stated in range vocabulary.
    """
    table = firstTable("19-formula-dragged")
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
    fixture carries an unbounded RANGE, only an unbounded reference, so this is
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
    ranges = firstTable("20-formula-shapes").cell("C11").formula.ranges
    assert len(ranges) == 2
    assert all(isinstance(extent, FormulaRange) for extent in ranges)


# ── AC 2.i: unboundedness is absence ─────────────────────────────────────────


def testWholeColumnReferenceHasNoRowAtAll() -> None:
    """`SUM(A)` stores a column and no row, rather than row zero or a sentinel.

    Row zero would be a real cell, and a range standing in for the whole column
    would compare equal to a bounded one spanning the same cells while meaning
    something different.
    """
    reference = firstTable("20-formula-shapes").cell("F11").formula.references[0]
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
    formula = firstTable("21-formula-errors").cell("C1").formula
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
    formula = firstTable("19-formula-dragged").cell("E2").formula
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
    table = firstTable("19-formula-dragged")
    assert table.cell("E2").formula == table.cell("E3").formula
    table.cell("E2").formula = Formula(nodes=())
    assert len(table.cell("E3").formula) == 2


# ── AC 4: the round trip changes nothing ─────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["18-formula-literals", "19-formula-dragged",
     "20-formula-shapes", "21-formula-errors"],
)
def testUnchangedRoundTripLeavesEveryPooledListByteIdentical(
    name: str, tmp_path: Path
) -> None:
    """Reading and writing back with no edit rewrites no formula at all.

    Compared at the archive bytes rather than through the model, because a model
    comparison would agree with itself while both halves were wrong.
    """
    source = fixturePath(name)
    target = tmp_path / f"{name}.numbers"
    pybers.open(source).save(target)
    assert dataListBytes(source) == dataListBytes(target)


@pytest.mark.parametrize(
    "name",
    ["18-formula-literals", "19-formula-dragged",
     "20-formula-shapes", "21-formula-errors"],
)
def testEveryFormulaSurvivesTheRoundTripThroughTheModel(
    name: str, tmp_path: Path
) -> None:
    """Every formula reads back equal after a save, cell for cell."""
    source = fixturePath(name)
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
    formula = firstTable("18-formula-literals").cell("A1").formula
    operator = formula.nodes[-1]
    assert operator.content is None
    assert not operator.recognized
    assert operator.raw, "an unrecognized node keeps its archive bytes"


def testUnknownFunctionKeepsItsSpelling() -> None:
    """A function Numbers could not resolve survives with its name intact.

    Numbers preserves the text rather than discarding the formula, the same
    instinct this library applies to an unrecognized cell type.
    """
    formula = firstTable("21-formula-errors").cell("D1").formula
    assert formula is not None
    unknown = [
        node.content for node in formula
        if isinstance(node.content, UnknownFunction)
    ]
    assert len(unknown) == 1
    assert unknown[0].name == "UNKNOWNFUNC"


# ── AC 5: a changed formula writes back ──────────────────────────────────────


def testChangedFormulaIsWrittenAndReadsBackChanged(tmp_path: Path) -> None:
    """One literal changed in a formula, saved, and read back as changed."""
    source = shutil.copy(fixturePath("18-formula-literals"),
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
    source = shutil.copy(fixturePath("19-formula-dragged"),
                         tmp_path / "19.numbers")
    document = pybers.open(source)
    table = document.sheets[0].tables[0]
    nodes = list(table.cell("E2").formula.nodes)
    nodes[-1] = dataclasses.replace(
        nodes[-1], content=FunctionCall(index=169, argumentCount=1)
    )
    table.cell("E2").formula = Formula(nodes=tuple(nodes))
    document.save()

    after = pybers.open(source).sheets[0].tables[0]
    assert after.cell("E2").formula.nodes[-1].content == FunctionCall(169, 1)
    assert after.cell("E3").formula.nodes[-1].content == FunctionCall(168, 1)


def testChangedFormulaMarksItsCellForRecalculation(tmp_path: Path) -> None:
    """A formula edit populates `refs_to_dirty`, which is what makes Numbers recompute.

    Numbers does not recalculate on open, measured for PYB-25, so an edit that
    did not mark its cell would leave the old result on screen indefinitely.
    A clean document serializes this archive to zero bytes, so any content at all
    is the request having been made.
    """
    from pybers._generated import TSCEArchives_pb2 as tsce
    from pybers.reader import ArchiveIndex

    def dirtyBytes(path: Path) -> int:
        index = ArchiveIndex(readPackage(path))
        for archive in list(index.byIdentifier.values()):
            if archiveTypeId(archive) != 4000:
                continue
            from pybers.numbersfile.types import parseArchive
            engine = parseArchive(archive)
            if not engine.HasField("refs_to_dirty"):
                continue
            return len(
                index.resolve(
                    engine.refs_to_dirty, tsce.ReferencesToDirtyArchive
                ).SerializeToString()
            )
        return 0

    source = shutil.copy(fixturePath("18-formula-literals"),
                         tmp_path / "18.numbers")
    assert dirtyBytes(Path(source)) == 0, "a clean document asks for nothing"

    document = pybers.open(source)
    cell = document.sheets[0].tables[0].cell("A1")
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(5))
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    assert dirtyBytes(Path(source)) > 0


# ── AC 6: a failed formula says so, and no more ──────────────────────────────


def testErroredCellReportsErroredAndInventsNoKind() -> None:
    """A failed formula is reported as failed, with its formula still readable.

    The file records THAT a cell errored and never why: the error list is empty
    in every fixture, so division by zero is indistinguishable from any other
    failure. A broken reference is the one exception, and it is visible through
    the formula rather than through the cell.
    """
    table = firstTable("21-formula-errors")
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
    cell = firstTable("18-formula-literals").cell("A1")
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

    working = shutil.copy(fixturePath("18-formula-literals"),
                          tmp_path / "18.numbers")
    document = pybers.open(working)
    cell = document.sheets[0].tables[0].cell("A1")
    nodes = list(cell.formula.nodes)
    nodes[1] = dataclasses.replace(nodes[1], content=Decimal(5))
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    assert dataListBytes(golden) == dataListBytes(Path(working)), (
        "the writer no longer produces the confirmed formula lists"
    )


def testNarrowedSharedRangeMatchesItsGoldenFile(tmp_path: Path) -> None:
    """One of two cells sharing an archive, narrowed, against confirmed output."""
    golden = goldenDirectory / "19-formula-dragged-F2-narrowed.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = shutil.copy(fixturePath("19-formula-dragged"),
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

    assert dataListBytes(golden) == dataListBytes(Path(working)), (
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

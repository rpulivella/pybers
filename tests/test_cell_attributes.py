#!/usr/bin/env python3
"""\
A formula cell that also carries a style, a format, a highlight and a comment.

The formula key is not at a fixed place in a cell record. Each attribute a cell
carries puts a reference ahead of it, so the key sits at slot 0 on a plain cell
and at slot 4 on a decorated one. Reading a fixed slot finds a key the table's
pool does not hold, which loses the formula, or a key it holds by accident,
which reports a different formula than the file contains.

`47-formula-cell-attributes` holds both tables. `Plain` leaves every default
alone and `Decorated` gives each formula cell a fill, an explicit alignment and
its own text style, with conditional highlighting on one and a comment on
another. Against the reader as it stood, six of the eight formulas in
`Decorated` were lost and a seventh read as a different formula.

UPDATES
2026-09-10  Written for #65, which #66 turned out to share a cause with.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/10"

import collections
import shutil
from pathlib import Path

import pytest

import pybers
from conftest import archiveBodies
from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence import readPackage
from pybers._persistence.cells import (
    CellRecord,
    decodeRow,
    formulaKeySlot,
    offsetUnitFor,
)
from pybers._persistence.index import ArchiveIndex
from pybers._persistence.types import archiveTypeId, archiveTypes
from pybers.formula._read import resolveFormula

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"
fixtureName: str = "47-formula-cell-attributes"

tableModelType: int = next(
    key for key, value in archiveTypes.items() if value is tst.TableModelArchive
)

# What `Decorated` holds, which its own column C states cell by cell. `B4` down to
# `B8` is one formula dragged, so the pool shares one entry between five cells.
decoratedFormulas: dict[str, str] = {
    "B1": "=SUM(A1:A5)",
    "B2": "=A1*A2",
    "B3": "=SUM(A1:A5)",
    "B4": "=A1*A2",
    "B5": "=A2*A3",
    "B6": "=A3*A4",
    "B7": "=A4*A5",
    "B8": "=A5*A6",
}

# Where the key sits in each of those records. `B2` is the conditionally
# highlighted one, which puts two more references ahead of the key than the rest.
decoratedSlots: dict[str, int] = {
    "B1": 2, "B2": 4, "B3": 2, "B4": 2,
    "B5": 2, "B6": 2, "B7": 2, "B8": 2,
}


def fixturePath(name: str) -> Path:
    """Return a fixture path, skipping when it has not been made yet."""
    path = fixtureDirectory / f"{name}.numbers"
    if not path.is_file():
        pytest.skip(f"Fixture {path.name} is not present.")
    return path


def formulaTables(path: Path) -> list[tuple[str, dict[int, int], list[CellRecord]]]:
    """Return every table's name, its pooled refcounts and its formula records.

    Keyed by archive rather than by name, because `20-formula-shapes` carries a
    `Table 1` on each of two sheets and merging them hides which is which.
    """
    index = ArchiveIndex(readPackage(path))
    tables: list[tuple[str, dict[int, int], list[CellRecord]]] = []
    for identifier in index.byIdentifier:
        archive = index.archive(identifier)
        if archiveTypeId(archive) != tableModelType:
            continue
        model = tst.TableModelArchive()
        model.ParseFromString(archive.messages[0].data)
        store = model.base_data_store
        refcounts: dict[int, int] = {}
        if store.formula_table.identifier:
            dataList = tst.TableDataList()
            dataList.ParseFromString(
                index.archive(store.formula_table.identifier).messages[0].data
            )
            refcounts = {
                entry.key: entry.refcount
                for entry in dataList.entries
                if entry.HasField("formula")
            }
        records: list[CellRecord] = []
        for entry in store.tiles.tiles:
            tile = index.resolve(entry.tile, tst.Tile)
            for info in tile.rowInfos:
                unit = offsetUnitFor(
                    info.has_wide_offsets, tile.should_use_wide_rows
                )
                records.extend(
                    record
                    for record in decodeRow(
                        info.cell_offsets, info.cell_storage_buffer, unit
                    )
                    if record.raw[9] & 0x02
                )
        tables.append((model.table_name, refcounts, records))
    return tables


def recordsOf(path: Path, name: str) -> list[CellRecord]:
    """Return the formula records of the one table carrying a name."""
    found = [records for table, _, records in formulaTables(path) if table == name]
    assert len(found) == 1, f"{name} names {len(found)} tables in {path.name}"
    return found[0]


# ── AC 1: a formula the reader could not resolve now reads ───────────────────


def testEveryFormulaInADecoratedTableReads() -> None:
    """AC 1. Six of these eight read as no formula at all before the fix."""
    table = pybers.open(fixturePath(fixtureName)).sheet(1).table("Decorated")

    assert {
        address: table.cell(address).formulaText for address in decoratedFormulas
    } == decoratedFormulas


def testAPlainTableIsUnaffected() -> None:
    """AC 1. The control: a cell carrying nothing keeps its key at the front."""
    table = pybers.open(fixturePath(fixtureName)).sheet(1).table("Plain")

    assert table.cell("B1").formulaText == "=SUM(A1:A5)"
    assert table.cell("B2").formulaText == "=A1*A2"


def testTheKeyMovesAsACellGainsAttributes() -> None:
    """AC 1. The whole defect in one assertion: the slot is not a constant.

    `Plain` puts the key first, `Decorated` puts it third, and the one cell with
    conditional highlighting puts it fifth.
    """
    path = fixturePath(fixtureName)

    assert {formulaKeySlot(r) for r in recordsOf(path, "Plain")} == {0}
    assert sorted(
        formulaKeySlot(r) for r in recordsOf(path, "Decorated")
    ) == sorted(decoratedSlots.values())


def testTheSlotRuleReproducesEveryPooledRefcount() -> None:
    """AC 1. The measurement the rule rests on, run over the whole corpus.

    A pooled formula records how many cells name it. Reading the key from the
    right slot reproduces that count for every entry in every table; reading it
    from the wrong one does not, which is what makes this stronger than checking
    that a formula merely appears.
    """
    checked = 0
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        for table, refcounts, records in formulaTables(path):
            if not refcounts:
                continue
            counted = collections.Counter(
                record.references[formulaKeySlot(record)] for record in records
            )
            assert dict(counted) == refcounts, f"{path.name} / {table}"
            checked += 1
    # Thirteen tables in the corpus pool a formula, and 47 contributes two of
    # them. A floor rather than an equality, so adding a fixture cannot fail this.
    assert checked >= 13


def testAFormulaKeyThePoolDoesNotHoldIsRefused() -> None:
    """AC 1.i. Returning None here is what let a save delete the formula."""
    record = CellRecord(
        column=0,
        typeByte=2,
        flags=0,
        value=None,
        references=(99,),
        raw=bytes(9) + bytes([0x02]),
    )

    with pytest.raises(pybers.ReadError, match="does not hold"):
        resolveFormula(record, {1: pybers.Formula()})


# ── AC 2 and AC 3: the document survives being opened and saved ──────────────


def testANoOpSaveDetachesNothing(tmp_path: Path) -> None:
    """AC 2. Six formulas were removed from this file by opening and saving it."""
    working = Path(shutil.copy(fixturePath(fixtureName), tmp_path / "47.numbers"))
    pybers.open(working).save()

    table = pybers.open(working).sheet(1).table("Decorated")
    assert {
        address: table.cell(address).formulaText for address in decoratedFormulas
    } == decoratedFormulas


def testADecoratedDocumentRoundTripsWithEveryArchiveUnchanged(
    tmp_path: Path,
) -> None:
    """AC 3. The base contract, on the one fixture that used to fail it."""
    working = Path(shutil.copy(fixturePath(fixtureName), tmp_path / "47.numbers"))
    before = archiveBodies(readPackage(working))
    pybers.open(working).save()

    assert archiveBodies(readPackage(working)) == before


# ── #66, which shares this cause: a reference that resolves nowhere ──────────


def testNoReferenceInTheCorpusResolvesBeforeTheFirstColumn() -> None:
    """Reading the wrong key resolved a formula against the wrong host.

    `B1` of `Decorated` read as `=A-2*A-1`, a column two places before the first,
    which is the shape #66 was filed for. A reference is an offset from the cell
    holding it, so attributing a formula to the wrong cell moves every reference
    in it.
    """
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        for _, _, cell in pybers.open(path).cellsIterate():
            if cell.formula is None:
                continue
            for reference in cell.formula.references:
                if reference.broken or reference.column is None:
                    continue
                assert reference.column.resolve(cell.reference.col) >= 1, (
                    f"{path.name} {cell.reference}"
                )

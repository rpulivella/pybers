#!/usr/bin/env python3
"""\
Cells moved or copied, carried into the tiles, headers and borders that hold them.

**The move is derived, never recorded**, as a structural edit is. Each cell read
from the file remembers where its record sat, so comparing that, after any rows
or columns an edit added or removed, with where the cell is now gives every move.

**A record moves whole**, so its style, format, highlighting and formula keys go
with it, measured 2026-09-23 in `61-move-*`. A row left holding nothing is dropped,
and each line's header counts the records it holds, dropped when it holds none and
carries nothing else, as Numbers left them in `61b-move-styles-cut-pasted`.

**A copied record is duplicated whole** and claims every entry it names, and rich
text is given an entry of its own. A record naming an entry this library cannot
count is refused rather than guessed.

Private. Part of the table feature's archive half.

UPDATES
2026-10-01  The format slots are read from `_persistence.cells`, for PYB-141.
2026-09-29  A copy carries every position of a merge it copies, as a move does,
            so what an import stores under covered cells goes with it, for PYB-136.
2026-09-29  A copied cell takes exactly its source's borders, for PYB-136.
2026-09-29  A filled cell's record is duplicated from the cell it copied, and the
            record it replaces is returned for release, for PYB-118.
2026-09-24  A moved merge carries the records an import left under it.
2026-09-24  A highlighting rule whose conditions a move changed is rebuilt.
2026-09-23  Written for PYB-18.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/23"

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .._generated import TSTArchives_pb2 as tst
from .._persistence import chooseOffsetUnit, decodeRow
from .._persistence.cells import (
    CellRecord,
    carriesFormula,
    conditionalSlot,
    countedFormatSlots,
    displayedKindSlot,
    findSlotValue,
    formulaFlagBit,
    formulaFlagOffset,
    listReferenceSlots,
    matchSlot,
    offsetWidth,
    patchSlotValue,
)
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry
from ..addressing import CellReference
from ..addressing.reference import originOffset
from ..errors import WriteError
from ..formula._read import readFormula
from ._conditions import readConditionalPlan, writeConditionalCounts
from ._lines import GridMaps
from ._records import controlSlot
from ._refcounts import countedStyleSlots
from ._strokes import copyStrokeEdges, listStrokeLayers, moveStrokeEdges
from ._structure import rowsPerBucket
from ._tiles import (
    TileRange,
    buildTileRange,
    createRowStorage,
    rewriteRow,
    writeTileRange,
)
from .cells import Cell, Table

# A stored (row, column), counted from zero, mapped to where its cell now sits.
type CellMoves = dict[tuple[int, int], tuple[int, int]]



@dataclass(frozen=True, slots=True)
class CellCopies:
    """Each copied (row, column) mapped to where the record it copies sits, or None.

    None leaves the copied position with no record. A position a merge covers is
    `covered`, since the model cannot say whether a record sits under it, so one
    absent there is copied as absent rather than refused.
    """

    records: dict[tuple[int, int], tuple[int, int] | None]
    covered: frozenset[tuple[int, int]]

    def __bool__(self) -> bool:
        """Report whether anything is copied."""
        return bool(self.records)

# Each slot a duplicated record may carry: counted on copy, or naming no entry.
copyableSlots: frozenset[tuple[int, int]] = frozenset({
    *countedStyleSlots, *countedFormatSlots, conditionalSlot, matchSlot,
    (formulaFlagOffset, formulaFlagBit), displayedKindSlot, controlSlot,
})

# Claims every entry a duplicated record names, returning the record to place.
type RecordClaim = Callable[[CellRecord, CellReference], bytes]


def findCellMoves(table: Table, maps: GridMaps) -> CellMoves:
    """Return every cell whose record sits elsewhere than the cell, after any edit.

    A cell whose stored line an edit removed has no record left to move, which is
    how a merged value carried off its anchor's line is written afresh. A position
    holding no record moves nothing, so a merge's covered cells cost nothing.
    """
    moves: CellMoves = {}
    for reference, cell in table.cells.items():
        origin = cell._origin
        if origin is None:
            continue
        row = maps.rows.lineMap(origin.row - originOffset)
        column = maps.columns.lineMap(origin.col - originOffset)
        if row is None or column is None:
            continue
        landed = (reference.row - originOffset, reference.col - originOffset)
        if (row, column) == landed:
            continue
        moves[(row, column)] = landed
        for down, across in listCoveredOffsets(cell):
            moves[(row + down, column + across)] = (
                landed[0] + down, landed[1] + across
            )
    return moves


def listCoveredOffsets(cell: Cell) -> list[tuple[int, int]]:
    """Return each position the merge a cell anchors covers, as an offset from it.

    A block operation carries every position of its rectangle, and a covered one
    has no model cell, so whatever the file stores there, as an import does, goes
    with the anchor without the model knowing it is there.
    """
    merge = cell.mergeAnchored
    if merge is None:
        return []
    return [
        (covered.row - cell.reference.row, covered.col - cell.reference.col)
        for covered in merge.extent if covered != merge.anchor
    ]


def findCellCopies(table: Table) -> CellCopies:
    """Return every filled cell and where the record of the cell it copied now sits.

    Named by where each source sits in the model, which is where its record sits
    once any move is carried, and copies are carried after moves.
    """
    records: dict[tuple[int, int], tuple[int, int] | None] = {}
    covered: set[tuple[int, int]] = set()
    for reference, cell in table.cells.items():
        copy = cell._copiedFrom
        if copy is None:
            continue
        source = copy.source
        if table.cells.get(source.reference) is not source:
            raise WriteError(
                f"{reference} was copied from a cell no longer in {table.name!r}, "
                "so there is no record to copy."
            )
        stored = source.reference
        row, column = reference.row - originOffset, reference.col - originOffset
        top, left = stored.row - originOffset, stored.col - originOffset
        records[(row, column)] = None if source._origin is None else (top, left)
        for down, across in listCoveredOffsets(source):
            records[(row + down, column + across)] = (top + down, left + across)
            covered.add((row + down, column + across))
    return CellCopies(records, frozenset(covered))


def findBorderCopies(table: Table) -> CellMoves:
    """Return each copied cell drawing its source's borders, and where that source sits.

    Keyed by where the copy landed, since one source may be copied twice. A source
    holding no record may still hold a border, so every one is named.
    """
    copies: CellMoves = {}
    for reference, cell in table.cells.items():
        copy = cell._copiedFrom
        if copy is None or not copy.borders:
            continue
        source = copy.source.reference
        row, column = reference.row - originOffset, reference.col - originOffset
        top, left = source.row - originOffset, source.col - originOffset
        copies[(row, column)] = (top, left)
        for down, across in listCoveredOffsets(copy.source):
            copies[(row + down, column + across)] = (top + down, left + across)
    return copies


@dataclass(frozen=True, slots=True)
class RecordMoves:
    """What moving the records changed: formulas moved, and every line touched."""

    formulas: list[tuple[tuple[int, int], tuple[int, int]]]
    rows: frozenset[int]
    columns: frozenset[int]


def placeRecords(
    registry: PackageRegistry,
    store: tst.DataStore,
    tileRange: TileRange,
    removals: Mapping[int, set[int]],
    placements: Mapping[int, dict[int, bytes]],
) -> None:
    """Remove and place records row by row, creating and dropping rows and tiles."""
    tileSize = store.tiles.tile_size
    created = False
    for row in sorted(set(removals) | set(placements)):
        tileid = row // tileSize
        created |= tileid not in tileRange.tiles
        tile = tileRange.tileFor(tileid)
        if not any(held.tile_row_index == row % tileSize for held in tile.rowInfos):
            createRowStorage(tile, row % tileSize)
        # Found after creation, because a repeated field stores a copy of its input.
        rowInfo = next(
            held for held in tile.rowInfos if held.tile_row_index == row % tileSize
        )
        placed = placements.get(row, {})
        slots = len(rowInfo.cell_offsets) // offsetWidth
        beyond = [column for column in placed if column >= slots]
        if beyond:
            raise WriteError(
                f"A record would land in column {min(beyond) + originOffset}, past "
                f"the {slots} offset slots row {row + originOffset} carries."
            )
        unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
        rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit, placed,
            frozenset(removals.get(row, set()) - placed.keys()),
        )
        rowInfo.cell_count = len(
            decodeRow(rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit)
        )
        if not rowInfo.cell_count:
            tile.rowInfos.remove(rowInfo)
        tile.numrows = len(tile.rowInfos)

    spent = {
        tileid for tileid, tile in tileRange.tiles.items()
        if tileid and not tile.rowInfos
    }
    if created or spent:
        writeTileRange(registry, store, tileRange.tiles, spent)


def moveCellRecords(
    index: ArchiveIndex,
    registry: PackageRegistry,
    store: tst.DataStore,
    moves: Mapping[tuple[int, int], tuple[int, int]],
) -> RecordMoves:
    """Lift every moved record, then set each down where its cell landed.

    Lifted before any is placed, so a block overlapping where it was never
    overwrites a record it has yet to move.
    """
    tileSize = store.tiles.tile_size
    tileRange = buildTileRange(index, registry, store)
    lifted: dict[tuple[int, int], CellRecord] = {}
    for tileid, tile in tileRange.tiles.items():
        for rowInfo in tile.rowInfos:
            row = tileid * tileSize + rowInfo.tile_row_index
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                if (row, record.column) in moves:
                    lifted[(row, record.column)] = record

    removals: dict[int, set[int]] = {}
    placements: dict[int, dict[int, bytes]] = {}
    for (row, column), record in lifted.items():
        removals.setdefault(row, set()).add(column)
        newRow, newColumn = moves[(row, column)]
        placements.setdefault(newRow, {})[newColumn] = record.raw
    placeRecords(registry, store, tileRange, removals, placements)
    return RecordMoves(
        formulas=[
            (stored, moves[stored])
            for stored, record in lifted.items() if carriesFormula(record)
        ],
        rows=frozenset(
            line for stored, landed in moves.items() for line in (stored[0], landed[0])
        ),
        columns=frozenset(
            line for stored, landed in moves.items() for line in (stored[1], landed[1])
        ),
    )


@dataclass(frozen=True, slots=True)
class RecordCopies:
    """What copying the records changed: each record placed, and each it replaced."""

    placed: dict[tuple[int, int], CellRecord]
    displaced: dict[tuple[int, int], CellRecord]


def refuseUncopyableRecord(record: CellRecord, where: CellReference) -> None:
    """Refuse a record whose duplicate would name an entry nobody counted."""
    for at, bit in listReferenceSlots(record.raw):
        if (at, bit) not in copyableSlots:
            raise WriteError(
                f"{where} names an entry through byte {at} bit {bit:#04x}, which is "
                "not identified, so a copy of it could not be counted."
            )


def copyCellRecords(
    index: ArchiveIndex,
    registry: PackageRegistry,
    store: tst.DataStore,
    copies: CellCopies,
    claim: RecordClaim,
) -> RecordCopies:
    """Duplicate each copied record where its cell was filled, removing what was there.

    Every record is read before any is placed, so a source that is also filled is
    copied as it stood.
    """
    tileSize = store.tiles.tile_size
    tileRange = buildTileRange(index, registry, store)
    records = copies.records
    wanted = set(records) | {
        stored for stored in records.values() if stored is not None
    }
    found: dict[tuple[int, int], CellRecord] = {}
    for tileid, tile in tileRange.tiles.items():
        for rowInfo in tile.rowInfos:
            row = tileid * tileSize + rowInfo.tile_row_index
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                if (row, record.column) in wanted:
                    found[(row, record.column)] = record

    missing = [
        stored for landed, stored in records.items()
        if stored is not None and stored not in found and landed not in copies.covered
    ]
    if missing:
        row, column = min(missing)
        raise WriteError(
            f"A copy names the record at "
            f"{CellReference(row + originOffset, column + originOffset)}, and the file "
            "holds none there."
        )
    placed = {
        landed: found[stored] for landed, stored in records.items()
        if stored is not None and stored in found
    }
    for (row, column), record in placed.items():
        refuseUncopyableRecord(
            record, CellReference(row + originOffset, column + originOffset)
        )
    displaced = {landed: found[landed] for landed in records if landed in found}
    removals: dict[int, set[int]] = {}
    placements: dict[int, dict[int, bytes]] = {}
    for row, column in displaced:
        removals.setdefault(row, set()).add(column)
    for (row, column), record in placed.items():
        where = CellReference(row + originOffset, column + originOffset)
        placements.setdefault(row, {})[column] = claim(record, where)
    placeRecords(registry, store, tileRange, removals, placements)
    return RecordCopies(placed, displaced)


def applyConditionChanges(
    index: ArchiveIndex,
    registry: PackageRegistry,
    store: tst.DataStore,
    table: Table,
) -> None:
    """Point each record at a rule holding the conditions its cell now holds.

    A cell holding no conditions keeps whatever rule its record names, since the
    model says nothing about it. Used after a move, where a condition that keeps its
    named cell has to change while the rule it came from stays for other cells.
    """
    plan = readConditionalPlan(index, registry, store)
    if plan is None or not plan.rules:
        return
    tileSize = store.tiles.tile_size
    tiles = []
    changed = False
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        tiles.append(tile)
        for rowInfo in tile.rowInfos:
            row = entry.tileid * tileSize + rowInfo.tile_row_index
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            replacements = {}
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                key = findSlotValue(record, conditionalSlot)
                cell = table.cells.get(
                    CellReference(row + originOffset, record.column + originOffset)
                )
                if key is None or key not in plan.rules or cell is None:
                    continue
                stored = tuple(
                    readFormula(rule.predicate.formula)
                    for rule in plan.rules[key].rules.rule
                )
                if not cell._conditions or cell._conditions == stored:
                    continue
                moved = plan.keyForConditions(key, cell._conditions)
                replacements[record.column] = patchSlotValue(
                    record.raw, conditionalSlot, moved
                )
            if replacements:
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit,
                    replacements,
                )
                changed = True
    if changed:
        writeConditionalCounts(plan, tiles)


def countLineRecords(
    index: ArchiveIndex, store: tst.DataStore
) -> tuple[Counter[int], Counter[int]]:
    """Return how many records each row and each column holds."""
    tileSize = store.tiles.tile_size
    rows: Counter[int] = Counter()
    columns: Counter[int] = Counter()
    for entry in store.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        for rowInfo in tile.rowInfos:
            unit = chooseOffsetUnit(rowInfo.has_wide_offsets, tile.should_use_wide_rows)
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, unit
            ):
                rows[entry.tileid * tileSize + rowInfo.tile_row_index] += 1
                columns[record.column] += 1
    return rows, columns


def carriesOnlyCount(header: tst.HeaderStorageBucket.Header) -> bool:
    """Report whether a header says nothing beyond how many cells its line holds."""
    return (
        header.size == 0
        and header.hidingState == 0
        and not header.HasField("cell_style")
        and not header.HasField("text_style")
    )


def updateHeaderCounts(
    buckets: list[tst.HeaderStorageBucket], lines: Iterable[int], counts: Counter[int]
) -> None:
    """Recount the headers of the lines a move touched, adding or dropping them."""
    for line in lines:
        bucket = buckets[min(line // rowsPerBucket, len(buckets) - 1)]
        header = next((held for held in bucket.headers if held.index == line), None)
        if header is None:
            if counts[line]:
                bucket.headers.add(
                    index=line, size=0, hidingState=0, numberOfCells=counts[line]
                )
        elif counts[line] or not carriesOnlyCount(header):
            header.numberOfCells = counts[line]
        else:
            bucket.headers.remove(header)
    for bucket in buckets:
        bucket.headers.sort(key=lambda held: held.index)


def recountLineHeaders(
    index: ArchiveIndex,
    store: tst.DataStore,
    rows: Iterable[int],
    columns: Iterable[int],
) -> None:
    """Recount and write the headers of every line whose records changed."""
    rowCounts, columnCounts = countLineRecords(index, store)
    rowBuckets = [
        index.resolve(reference, tst.HeaderStorageBucket)
        for reference in store.rowHeaders.buckets
    ]
    updateHeaderCounts(rowBuckets, sorted(rows), rowCounts)
    for reference, bucket in zip(store.rowHeaders.buckets, rowBuckets, strict=True):
        index.archiveWrite(reference.identifier, bucket)
    columnBucket = index.resolve(store.columnHeaders, tst.HeaderStorageBucket)
    updateHeaderCounts([columnBucket], sorted(columns), columnCounts)
    index.archiveWrite(store.columnHeaders.identifier, columnBucket)


def applyCellCopies(
    index: ArchiveIndex,
    registry: PackageRegistry,
    store: tst.DataStore,
    copies: CellCopies,
    claim: RecordClaim,
) -> RecordCopies:
    """Carry every copied cell into its records, headers and highlighting counts."""
    copied = copyCellRecords(index, registry, store, copies, claim)
    recountLineHeaders(
        index, store,
        {row for row, _ in copies.records}, {column for _, column in copies.records},
    )
    plan = readConditionalPlan(index, registry, store)
    if plan is not None and plan.rules:
        writeConditionalCounts(
            plan,
            [index.resolve(entry.tile, tst.Tile) for entry in store.tiles.tiles],
        )
    return copied


def applyBorderCopies(
    index: ArchiveIndex,
    registry: PackageRegistry,
    model: tst.TableModelArchive,
    copies: CellMoves,
) -> None:
    """Give every copied cell exactly its source's borders, as a paste did in `64f`."""
    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    copyStrokeEdges(index, registry, sidecar, copies)
    index.archiveWrite(
        model.stroke_sidecar.identifier, sidecar, listStrokeLayers(sidecar)
    )


def applyCellMoves(
    index: ArchiveIndex,
    registry: PackageRegistry,
    model: tst.TableModelArchive,
    moves: Mapping[tuple[int, int], tuple[int, int]],
) -> RecordMoves:
    """Carry every moved cell into its records, headers and borders."""
    store = model.base_data_store
    moved = moveCellRecords(index, registry, store, moves)
    recountLineHeaders(index, store, moved.rows, moved.columns)

    sidecar = index.resolve(model.stroke_sidecar, tst.StrokeSidecarArchive)
    moveStrokeEdges(index, registry, sidecar, moves)
    index.archiveWrite(
        model.stroke_sidecar.identifier, sidecar, listStrokeLayers(sidecar)
    )
    return moved


__all__ = [
    "CellCopies",
    "CellMoves",
    "RecordCopies",
    "RecordClaim",
    "RecordMoves",
    "applyBorderCopies",
    "applyCellCopies",
    "applyCellMoves",
    "applyConditionChanges",
    "findBorderCopies",
    "findCellCopies",
    "listCoveredOffsets",
    "findCellMoves",
]

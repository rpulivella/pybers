#!/usr/bin/env python3
"""\
One table back into its archives: cell records, the tiles holding them, and merges.

**A record is patched, never rebuilt.** Only the sixteen value bytes move. The
header carries the storage version, the type and a flags bitmask, and the trailing
references point into the table's format and style lists, so a record rebuilt from
the model alone opens in Numbers showing the right number with the wrong formatting
and raises nothing on the way.

**A merge is stored as a formula**, shaped like `SUM($A$1:$B$1)` and evaluated by
nothing. It lives here rather than with the calculation engine because a merge
belongs to a table, and it was the one thing in the engine that knew a model type.

Private. The table feature offers `Table` and `Cell`, not the machinery that saves
one.

UPDATES
2026-09-14  A table's pooled strings can be written, for #61.
2026-09-14  A row the file stores nothing for is created rather than the
            formula being dropped, for #78. The walk over `rowInfos` never
            saw it, and the save reported success.
2026-09-08  Split out of the writer for #58, taking the merge formula with it.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from dataclasses import dataclass
from decimal import Decimal

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence import IWAFile, decodeRow, offsetUnitFor
from .._persistence.cells import (
    CellRecord,
    carriesFormula,
    emptyOffset,
    formulaKeySlot,
    offsetWidth,
    valueOffset,
)
from .._persistence.decimal128 import Decimal128, encodedLength
from .._persistence.index import (
    ArchiveIndex,
    originOffset,
    wordBits,
    wordMask,
)
from ..addressing import CellReference
from ..errors import WriteError
from ..formula._write import (
    FormulaPool,
    attachFormulaKey,
    buildFormulaRecord,
    detachFormulaKey,
    formulaEdit,
    formulaPoolFor,
    patchFormulaKey,
)
from ._read import (
    readMerges,
    readRichTextTable,
    readStringTable,
    resolveValue,
)
from .cells import Cell, MergeRange, Table

# `TST.Tile` and the type bytes a numeric record may carry. 2 is a plain number
# and 10 is currency, which is the same encoding under a different type.
tileTypeId: int = 6002
numericTypeBytes: tuple[int, ...] = (2, 10)

# A record's value is patched in place, leaving the twelve-byte header and the
# trailing references alone. Those references point at the table's format and
# style lists, so rewriting the whole record would strip a cell's number format
# while appearing to succeed.
valueEnd: int = valueOffset + encodedLength


def checkedValue(cell: Cell, record: CellRecord) -> Decimal:
    """Return the Decimal to write, or refuse and say exactly what is unsupported.

    Three refusals, and every one of them replaces a silent loss. Writing over a
    formula would discard it while leaving a document whose displayed number and
    stored formula disagree until Numbers recalculates. Writing a non-numeric value
    needs the table's pooled string list, which this ticket does not touch. Changing
    a cell's type needs a new record rather than a patched one.
    """
    if carriesFormula(record):
        raise WriteError(
            f"{cell.reference} is backed by a formula, so writing a value would "
            "discard it. Formula writing is not supported yet, and overwriting one "
            "silently would leave the cell's formula and its displayed value "
            "disagreeing until Numbers recalculated."
        )
    if not isinstance(cell.value, Decimal):
        raise WriteError(
            f"{cell.reference} was set to {type(cell.value).__name__}, and only a "
            "Decimal can be written so far. Text needs the table's pooled string "
            "list, which this version does not write."
        )
    if record.typeByte not in numericTypeBytes:
        raise WriteError(
            f"{cell.reference} holds a value of type {record.typeByte} and a "
            "Decimal was written into it. Changing a cell's type is not supported "
            "yet, because it needs a new record rather than a patched one."
        )
    return cell.value


def patchRecord(record: CellRecord, value: Decimal) -> bytes:
    """Return one cell record with its number replaced and everything else kept.

    Only the sixteen value bytes move. The header carries the storage version, the
    type and a flags bitmask, and the trailing references point into the table's
    format and style lists, so a record rebuilt from scratch would open in Numbers
    showing the right number with the wrong formatting and raise nothing on the way.
    """
    if len(record.raw) < valueEnd:
        raise WriteError(
            f"The record for column {record.column + originOffset} is "
            f"{len(record.raw)} bytes, too short to hold a decimal128 value."
        )
    return (
        record.raw[:valueOffset] + Decimal128(value).asBytes() + record.raw[valueEnd:]
    )


@dataclass
class StringPool:
    """A table's pooled strings, and the one place a written one is added.

    The counterpart of `FormulaPool` and shaped like it on purpose. Numbers points
    every cell holding the same text at ONE entry and keeps a refcount, so writing
    an entry per cell diverges from what Numbers itself writes the moment the same
    label appears twice.

    A shared entry is never overwritten. Changing the text of one cell that shares
    an entry with six others must not rewrite all seven, which is the same aliasing
    hazard the frozen model closes on the read side.
    """

    dataList: tst.TableDataList
    stored: dict[int, str]
    touched: bool = False

    def entryFor(self, key: int) -> tst.TableDataList.ListEntry | None:
        """Return one pooled entry by key, or None when the table has no such key."""
        for entry in self.dataList.entries:
            if entry.key == key:
                return entry
        return None

    def keyFor(self, text: str, previous: int | None = None) -> int:
        """Return the key a cell should name, sharing an entry when one matches.

        `previous` is the key the cell names now, released when it stops naming it.
        """
        self.touched = True
        for key, stored in self.stored.items():
            entry = self.entryFor(key)
            if stored != text or entry is None:
                continue
            if key == previous:
                return key
            entry.refcount += 1
            if previous is not None:
                self.release(previous)
            return key

        existing = self.entryFor(previous) if previous is not None else None
        if existing is not None and existing.refcount <= 1:
            existing.string = text
            self.stored[existing.key] = text
            return existing.key
        if previous is not None:
            self.release(previous)
        fresh = self.dataList.entries.add()
        fresh.key = self.dataList.nextListID
        fresh.refcount = 1
        fresh.string = text
        self.dataList.nextListID += 1
        self.stored[fresh.key] = text
        return fresh.key

    def release(self, key: int) -> None:
        """Give up one cell's claim on a stored string.

        Emptied rather than deleted when nothing names it, because `nextListID`
        never reuses a key and a removed entry would invite a reader to assume the
        keys are dense.
        """
        entry = self.entryFor(key)
        if entry is None:
            return
        self.touched = True
        entry.refcount = max(0, entry.refcount - 1)


def stringPoolFor(index: ArchiveIndex, store: tst.DataStore) -> StringPool | None:
    """Return the table's string pool, or None when it carries no string list.

    A table that has never held text carries no list to write into, which is a
    different state from one whose list is empty.
    """
    if not store.stringTable.identifier:
        return None
    return StringPool(
        dataList=index.resolve(store.stringTable, tst.TableDataList),
        stored=readStringTable(index, store),
    )


def rowsNeedingStorage(
    table: Table, firstRow: int, tileSize: int, present: frozenset[int]
) -> list[int]:
    """Return the rows of this tile holding a formula the file stores no row for.

    Numbers writes a `TileRowInfo` only for a row that holds something, so a table
    declaring ten rows can carry one. A formula written into any of the other nine
    was dropped by the walk over `rowInfos`, and the save reported success.
    """
    wanted = set()
    for reference, cell in table.cells.items():
        row = reference.row - originOffset
        if cell.formula is None or row in present:
            continue
        if firstRow <= row < firstRow + tileSize:
            wanted.add(row)
    return sorted(wanted)


def rowStorageCreate(tile: tst.Tile, tileRowIndex: int) -> tst.TileRowInfo:
    """Add an empty row to a tile, shaped like the rows already in it.

    The offset array's length is copied from a sibling rather than computed: a
    narrow row carries a fixed 255 slots whatever the column count, and the one
    wide row measured carries one slot per column, so a rule fitted to that single
    sample would be a guess. A tile holding no row to copy is refused by the caller.

    `numrows` is corrected because Numbers keeps it accurate, and `numCells`,
    `maxRow` and `maxColumn` are left alone because Numbers writes zero in all
    three on tiles full of data.
    """
    sibling = tile.rowInfos[0]
    empty = emptyOffset.to_bytes(offsetWidth, "little") * (
        len(sibling.cell_offsets) // offsetWidth
    )
    created = tst.TileRowInfo()
    created.tile_row_index = tileRowIndex
    created.cell_count = 0
    created.cell_storage_buffer_pre_bnc = b""
    created.cell_offsets_pre_bnc = empty
    created.storage_version = sibling.storage_version
    created.cell_storage_buffer = b""
    created.cell_offsets = empty
    if sibling.has_wide_offsets:
        created.has_wide_offsets = True

    at = len(tile.rowInfos)
    for position, existing in enumerate(tile.rowInfos):
        if existing.tile_row_index > tileRowIndex:
            at = position
            break
    tile.rowInfos.insert(at, created)
    tile.numrows = len(tile.rowInfos)
    return created


def rewriteRow(
    offsets: bytes,
    buffer: bytes,
    offsetUnit: int,
    replacements: dict[int, bytes],
    removals: frozenset[int] = frozenset(),
) -> tuple[bytes, bytes]:
    """Rebuild one row's offset array and storage buffer, replacing and dropping.

    The whole row is rebuilt rather than patched in place because a record's offset
    is where the previous ones ended, so a record that changes length moves every
    record after it. Untouched records are re-emitted from the bytes they were read
    from, so a row with one edit differs in exactly one record.

    A dropped column takes the same empty offset a column that never held anything
    takes, which is what a cell swallowed by a merge looks like in the file: no
    record at all rather than an empty one.
    """
    slots = len(offsets) // offsetWidth
    existing = {
        record.column: record for record in decodeRow(offsets, buffer, offsetUnit)
    }

    rebuiltOffsets = bytearray()
    rebuiltBuffer = bytearray()
    for column in range(slots):
        record = existing.get(column)
        body = replacements.get(column)
        if body is None and record is not None:
            body = record.raw
        # A replacement for a column with no record CREATES one, which is how a
        # formula reaches a cell that was empty. The offset array already carries a
        # slot for every column, so nothing grows.
        if body is None or column in removals:
            rebuiltOffsets += emptyOffset.to_bytes(offsetWidth, "little")
            continue
        # A row counting offsets in words can only name a position the unit
        # divides, so a record of any other length would silently move every
        # record after it. Refuse rather than write a row that reads back wrong.
        if len(rebuiltBuffer) % offsetUnit:
            raise WriteError(
                f"Column {column} would start at byte {len(rebuiltBuffer)} of the "
                f"row buffer, which is not a multiple of the {offsetUnit}-byte "
                "unit this row counts its offsets in."
            )
        rebuiltOffsets += (len(rebuiltBuffer) // offsetUnit).to_bytes(
            offsetWidth, "little"
        )
        rebuiltBuffer += body
    return bytes(rebuiltOffsets), bytes(rebuiltBuffer)


@dataclass(frozen=True, slots=True)
class TableEdits:
    """What one table's write changed, in the terms the engine has to be told.

    `written` drives the dirty set and says a cell moved. `formulaAdded` and
    `formulaRemoved` are a different fact: the calculation engine keeps its own
    register of which cells hold formulas, and a cell that merely changed value
    does not belong in either list.
    """

    written: list[tuple[int, int]]
    formulaAdded: list[tuple[int, int]]
    formulaRemoved: list[tuple[int, int]]


def applyFormulaEdit(
    edit: str, raw: bytes, record: CellRecord, cell: Cell, pool: FormulaPool
) -> bytes:
    """Carry out one cell's formula change against the record and the pool together.

    The two always move as a pair: a key written into a record that the pool does
    not carry names nothing, and an entry the pool holds that no record names is
    dead weight that `refcount` then lies about.
    """
    if edit == "attach":
        assert cell.formula is not None
        return attachFormulaKey(raw, record, pool.keyFor(cell.formula))
    if edit == "detach":
        pool.release(record.references[formulaKeySlot(record)])
        return detachFormulaKey(raw, record)
    assert cell.formula is not None
    return patchFormulaKey(
        raw,
        record,
        pool.keyFor(cell.formula, record.references[formulaKeySlot(record)]),
    )


def applyTableEdits(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    table: Table,
    model: tst.TableModelArchive,
    swallowed: frozenset[tuple[int, int]] = frozenset(),
) -> TableEdits:
    """Write every changed cell of one table back into the tiles it came from.

    Returns the stored coordinates it wrote, counted from zero, because the
    calculation engine has to be told which cells moved and this is the only place
    that knows. Returning them rather than a count is what lets `refs_to_dirty` name
    exactly the cells that changed.

    Walks the tile list rather than the archives, matching the read path exactly.
    Tile archive identifiers are not in row order, so iterating archives as found
    would write a cell into the wrong row and raise nothing.
    """
    store = model.base_data_store
    tileSize = store.tiles.tile_size

    # Resolved through the same tables the reader used, because a record holds a
    # pooled key rather than its text. Comparing the model's string against that
    # key would make every text cell look edited on every save.
    strings = readStringTable(index, store)
    richText = readRichTextTable(index, store)
    pool = formulaPoolFor(index, store)
    written: list[tuple[int, int]] = []
    formulaAdded: list[tuple[int, int]] = []
    formulaRemoved: list[tuple[int, int]] = []

    # A row belongs to the tile covering its index, and a tile that holds nothing
    # may be absent. No table in the 46 fixtures has such a gap, so this refuses
    # rather than guessing what an absent tile should be built from, and refusing
    # is what keeps the formula from being dropped in silence.
    if pool is not None:
        # Compared by tile rather than by row: a table at Numbers' million-row
        # limit spans 3907 tiles, so naming every row covered would build a
        # million-element set on every save to answer a question this answers in
        # one division.
        coveredTiles = frozenset(entry.tileid for entry in store.tiles.tiles)
        uncovered = [
            reference
            for reference, held in table.cells.items()
            if held.formula is not None
            and (reference.row - originOffset) // tileSize not in coveredTiles
        ]
        if uncovered:
            first = min(uncovered, key=lambda reference: (reference.row, reference.col))
            raise WriteError(
                f"Row {first.row} of {table.name!r} holds a formula and no tile "
                f"covers it. The table declares {model.number_of_rows} rows and "
                f"stores {len(store.tiles.tiles)} tile(s) of {tileSize}."
            )

    for entry in store.tiles.tiles:
        archive = index.archive(entry.tile.identifier)
        tile = index.resolve(entry.tile, tst.Tile)
        firstRow = entry.tileid * tileSize
        touched = False

        # Rows the file stores nothing for, materialized before the walk below,
        # which only ever sees a row that already has storage. Doing it here rather
        # than inside the walk keeps `rowInfos` from being mutated while iterated.
        createdRows: set[int] = set()
        if pool is not None:
            stored = frozenset(
                firstRow + rowInfo.tile_row_index for rowInfo in tile.rowInfos
            )
            for missing in rowsNeedingStorage(table, firstRow, tileSize, stored):
                if not tile.rowInfos:
                    raise WriteError(
                        f"Row {missing + originOffset} of {table.name!r} holds a "
                        "formula and its tile stores no row to take the shape of. "
                        "Writing into an empty tile is not supported, and the "
                        "formula would be lost without this refusal."
                    )
                rowStorageCreate(tile, missing - firstRow)
                createdRows.add(missing)
                touched = True

        for rowInfo in tile.rowInfos:
            offsetUnit = offsetUnitFor(
                rowInfo.has_wide_offsets, tile.should_use_wide_rows
            )
            row = firstRow + rowInfo.tile_row_index
            replacements: dict[int, bytes] = {}
            removals = frozenset(
                column for (swallowedRow, column) in swallowed if swallowedRow == row
            )
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, offsetUnit
            ):
                if (row, record.column) in swallowed:
                    continue
                cell = table.cells.get(
                    CellReference(row + originOffset, record.column + originOffset)
                )
                if cell is None:
                    continue
                valueChanged = cell.value != resolveValue(record, strings, richText)
                edit = formulaEdit(cell.formula, record, pool)
                if not valueChanged and edit == "none":
                    continue
                patched = record.raw
                # The value first, so that writing a value OVER a formula still
                # refuses here rather than being masked by the formula edit below.
                # Attaching a formula is a different act and is allowed.
                if valueChanged:
                    patched = patchRecord(record, checkedValue(cell, record))
                if pool is not None and edit != "none":
                    patched = applyFormulaEdit(edit, patched, record, cell, pool)
                    if edit == "attach":
                        formulaAdded.append((row, record.column))
                    elif edit == "detach":
                        formulaRemoved.append((row, record.column))
                replacements[record.column] = patched
            present = frozenset(
                record.column
                for record in decodeRow(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, offsetUnit
                )
            )
            # A cell the model gave a formula to but the file has no record for.
            # The loop above cannot see these: it walks records, and these have
            # none. Skipped when a merge swallowed the position, which is an
            # absence Numbers means rather than one to fill.
            if pool is not None:
                for column in range(table.colCount):
                    if column in present or (row, column) in swallowed:
                        continue
                    cell = table.cells.get(
                        CellReference(row + originOffset, column + originOffset)
                    )
                    if cell is None or cell.formula is None:
                        continue
                    replacements[column] = buildFormulaRecord(
                        pool.keyFor(cell.formula)
                    )
                    formulaAdded.append((row, column))
            dropped = removals & present
            if not replacements and not dropped:
                continue
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
                rowInfo.cell_offsets,
                rowInfo.cell_storage_buffer,
                offsetUnit,
                replacements,
                dropped,
            )
            # Corrected only on a row this save created. An edited row carries the
            # count Numbers wrote and this library has never maintained it, so
            # fixing those here would rewrite every golden to no measured benefit.
            if row in createdRows:
                rowInfo.cell_count = sum(
                    1 for column in range(len(rowInfo.cell_offsets) // offsetWidth)
                    if int.from_bytes(
                        rowInfo.cell_offsets[column * offsetWidth:][:offsetWidth],
                        "little",
                    ) != emptyOffset
                )
            written.extend((row, column) for column in replacements)
            touched = True

        if touched:
            owners[archive.identifier].messageReplace(
                archive.identifier, 0, tile.SerializeToString()
            )

    if pool is not None and pool.touched:
        poolId = store.formula_table.identifier
        owners[poolId].messageReplace(
            poolId, 0, pool.dataList.SerializeToString()
        )
    return TableEdits(written, formulaAdded, formulaRemoved)


# A merge is written as `SUM($A$1:$B$1)`, so it carries SUM's index in Apple's
# own function table. The number is theirs and is not derivable from the schemas.
sumFunctionIndex: int = 168


def writeMergeFormula(
    store: tst.FormulaStoreArchive, merge: MergeRange, ownerUid: tsp.UUID
) -> None:
    """Add one merged region to a table's merge store, as the formula Numbers writes.

    **A merge is stored as a formula, not as a flag on a cell.** Each region is a
    complete formula shaped like `SUM($A$1:$B$1)`: a colon-tract node carrying the
    rectangle with all four sticky bits set, then the function node for SUM. Nothing
    evaluates it; the shape is how a merge is expressed.

    The tract's table identifier is the table's own `formula_owner_uid`, split from
    two 64-bit halves into four 32-bit words, which is a different spelling of the
    same value in a different archive. Measured 2026-09-02 against `22-merge-2x2`.
    """
    pair = store.formulas.add()
    pair.formula_index = len(store.formulas) - 1

    node = pair.formula.AST_node_array.AST_node.add()
    node.AST_node_type = tsce.ASTNodeArrayArchive.COLON_TRACT_NODE
    identifier = node.AST_cross_table_reference_extra_info.table_id
    identifier.uuid_w0 = ownerUid.lower & wordMask
    identifier.uuid_w1 = ownerUid.lower >> wordBits
    identifier.uuid_w2 = ownerUid.upper & wordMask
    identifier.uuid_w3 = ownerUid.upper >> wordBits
    node.AST_sticky_bits.begin_row_is_absolute = True
    node.AST_sticky_bits.begin_column_is_absolute = True
    node.AST_sticky_bits.end_row_is_absolute = True
    node.AST_sticky_bits.end_column_is_absolute = True

    startRow, startCol, endRow, endCol = merge.bounds
    tract = node.AST_colon_tract
    columns = tract.absolute_column.add()
    columns.range_begin = startCol - originOffset
    rows = tract.absolute_row.add()
    rows.range_begin = startRow - originOffset
    # `range_end` is omitted for a span of one rather than repeating the beginning,
    # which is how Numbers writes its own and how the reader expects to find them.
    if endCol != startCol:
        columns.range_end = endCol - originOffset
    if endRow != startRow:
        rows.range_end = endRow - originOffset
    tract.preserve_rectangular = True

    function = pair.formula.AST_node_array.AST_node.add()
    function.AST_node_type = tsce.ASTNodeArrayArchive.FUNCTION_NODE
    function.AST_function_node_index = sumFunctionIndex
    function.AST_function_node_numArgs = 1


def mergesAdded(table: Table, model: tst.TableModelArchive) -> list[MergeRange]:
    """Return the merges the model holds that the stored archive does not.

    Compared against what is stored rather than tracked as merges are added, for
    the same reason `applyMerges` does it: a caller reaches `mergeRanges`
    directly, so a flag set at `mergeAdd` would go stale.

    **Call this BEFORE `applyMerges`**, which rewrites the very store it reads.
    Measured 2026-09-07 on `22c-merge-overpaints`: the same call returns one
    merge before and none after, so the wrong order leaves every covered position
    unswallowed and raises nothing.
    """
    stored = {str(merge.extent) for merge in readMerges(model)}
    return [merge for merge in table.mergeRanges if str(merge.extent) not in stored]


def applyMerges(
    table: Table, model: tst.TableModelArchive, ownerUid: tsp.UUID
) -> frozenset[tuple[int, int]]:
    """Rewrite a table's merge store when its merges differ, and say which cells moved.

    **A merge changes what a reference means, so it changes results**, which is why
    every position whose merge state changed is returned for dirty-marking. **The
    store is emptied rather than removed** when the last merge goes; `merge_owner` is
    present in both twins. Both measured 2026-09-02 across `22-merge-2x2` and its
    unmerged twin, recorded in findings-03-structure.md.

    Compared against what is stored rather than tracked as merges are added, since a
    caller reaches `mergeRanges` directly and a dirty flag would go stale.
    """
    stored = readMerges(model)
    wanted = sorted(str(merge.extent) for merge in table.mergeRanges)
    if wanted == sorted(str(merge.extent) for merge in stored):
        return frozenset()

    store = model.merge_owner.formula_store
    del store.formulas[:]
    for merge in table.mergeRanges:
        writeMergeFormula(store, merge, ownerUid)
    store.next_formula_index = len(store.formulas)

    # Both directions matter: a merge that appeared invalidates references INTO it,
    # and one that went away makes references valid again.
    before = {str(merge.extent): merge for merge in stored}
    after = {str(merge.extent): merge for merge in table.mergeRanges}
    changed = (set(before) ^ set(after))
    return frozenset(
        (reference.row - originOffset, reference.col - originOffset)
        for extent in changed
        for reference in (before.get(extent) or after[extent]).extent
    )

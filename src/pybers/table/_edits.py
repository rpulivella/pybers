#!/usr/bin/env python3
"""\
The tile pass: every changed cell of one table written into the tiles holding it.

Walks the tile list rather than the archives, matching the read path exactly, and
opens every list a written or removed record claims, so the counts move with the
records in one pass.

Private. Part of the table feature's archive half.

UPDATES
2026-10-29  Every list claimed and released through an `EntryPool`, for PYB-278.
2026-10-22  A save compares a currency cell through its code, for PYB-220.
2026-10-20  A value of any kind is written over any other, releasing the control
            and rich text its record no longer specifies, and dropping a control
            that cannot show the value, for PYB-144.
2026-10-01  A cell's chosen format is read from its description, for PYB-141.
2026-09-29  Filled cells take a duplicate of the record they copied, which claims
            what it names, and a removed record releases its control, for PYB-118.
2026-09-23  Cells moved as a block carry their records first, for PYB-18.
2026-09-22  Split out of the table writer for PYB-113: records, refcounts and
            merges went to modules of their own.
2026-09-22  Archives written through the save's index, for PYB-109.
2026-09-21  Tiles and the row primitives moved to `_tiles`, for PYB-17.
2026-09-18  Rows and records move to their new lines, and a removed one releases
            what it named as a merge-swallowed one does, for PYB-17.
2026-09-16  A record carries the chosen-format bit its cell holds, so literal
            text opens as Text, for PYB-83.
2026-09-16  A formula swapped for another is reported as added, so the engine
            hears what the cell reads now, for PYB-86.
2026-09-15  A merge releases the formulas, rich text, strings and styles of the
            records it removes, and a string nothing names is removed, for
            PYB-92.
2026-09-15  A format's refcount follows the cells naming it, for PYB-89. Each
            written record moves the counts its format slots changed, and a
            borrowed shape keeps only the format slot of its own kind. Byte 9
            `0x10` stores the kind a cell displays with rather than a key. A
            format nothing names is removed, and a merge releases the formats
            of the records it removes.
2026-09-14  Text is written and pooled, and a cell changes between text and
            a number, for #61. A format sits in the slot its kind uses, so a
            type change moves it, drops the control, and keeps the style.
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

from .._generated import TSKArchives_pb2 as tsk
from .._generated import TSTArchives_pb2 as tst
from .._persistence import decodeRecord
from .._persistence.cells import (
    CellRecord,
    carriesChosenFormat,
    carriesFormula,
    emptyOffset,
    findFormulaKeySlot,
    findSlotValue,
    offsetWidth,
)
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry
from .._persistence.pool import EntryPool
from .._persistence.rows import StoredTiles, iterateTileRows
from ..addressing.reference import CellAddress, originOffset
from ..errors import WriteError
from ..formula._write import (
    attachFormulaKey,
    buildFormulaRecord,
    classifyFormulaEdit,
    detachFormulaKey,
    patchFormulaKey,
    readFormulaPool,
)
from ..formula.nodes import Formula
from ._conditions import ConditionalPlan, writeConditionalCounts
from ._controls import readControls
from ._lines import GridMaps
from ._read import (
    controlSlot,
    readCellValue,
    readCurrencyCodes,
    readRichTextTable,
    readStringTable,
)
from ._records import (
    applyAutomaticFormat,
    applyChosenFormat,
    buildWrittenRecord,
    findFormatKey,
    findTemplateRecord,
    findWrittenTypeByte,
    patchRichTextKey,
    plainNumberRecord,
)
from ._refcounts import (
    copyRichText,
    countFormatClaims,
    listRichTextClaims,
    listStringClaims,
    listStyleClaims,
    moveFormatReferences,
    readCountedPool,
    readFormatPool,
    readRichTextPool,
    readStringPool,
    removeSpentRichText,
)
from ._relocation import (
    CellCopies,
    CellMoves,
    applyCellCopies,
    applyCellMoves,
    applyConditionChanges,
)
from ._tiles import (
    buildTileRange,
    createRowStorage,
    moveGridRecords,
    narrowRowSlots,
    rewriteRow,
    writeTileRange,
)
from .cell import Cell, isSameValue
from .cells import Table


def findRowsNeedingStorage(
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
        if (cell.formula is None and cell.value is None) or row in present:
            continue
        if firstRow <= row < firstRow + tileSize:
            wanted.add(row)
    return sorted(wanted)


@dataclass(frozen=True, slots=True)
class TableEdits:
    """What one table's write changed, in the terms the engine has to be told.

    `written` drives the dirty set and says a cell moved. `formulaAdded` and
    `formulaRemoved` are a different fact: the calculation engine keeps its own
    register of which cells hold formulas, and a cell that merely changed value
    does not belong in either list.

    **A formula swapped for another is `formulaAdded`**, since the register also
    carries what each formula reads, and the cell now reads something else.
    """

    written: list[tuple[int, int]]
    formulaAdded: list[tuple[int, int]]
    formulaRemoved: list[tuple[int, int]]


def applyFormulaEdit(
    edit: str, raw: bytes, record: CellRecord, cell: Cell, pool: EntryPool[Formula]
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
        pool.release(record.references[findFormulaKeySlot(record)])
        return detachFormulaKey(raw, record)
    assert cell.formula is not None
    return patchFormulaKey(
        raw,
        record,
        pool.keyFor(cell.formula, record.references[findFormulaKeySlot(record)]),
    )


def applyTableEdits(
    index: ArchiveIndex,
    table: Table,
    model: tst.TableModelArchive,
    swallowed: frozenset[tuple[int, int]],
    maps: GridMaps,
    registry: PackageRegistry,
    plan: ConditionalPlan | None,
    moves: CellMoves,
    copies: CellCopies,
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
    currencyCodes = readCurrencyCodes(index, store)
    pool = readFormulaPool(index, store)
    textPool = readStringPool(index, store)
    # Each list is rewritten only when a written record moved one of its counts.
    formatPool = readFormatPool(index, store)
    formatKeys: dict[bytes, int] = {}
    walkedTiles: list[tuple[int, tst.Tile]] = []
    stylePool = (
        readCountedPool(index, store.styleTable, "style")
        if store.styleTable.identifier else None
    )
    richTextPool = (
        readRichTextPool(index, store) if store.HasField("rich_text_table") else None
    )
    controlPool = (
        readCountedPool(index, store.control_cell_spec_table, "control")
        if store.HasField("control_cell_spec_table") else None
    )
    controls = readControls(index, store)

    def formatFor(wanted: tsk.FormatStructArchive) -> int | None:
        """Return the key naming exactly this format, caching the lookup."""
        if formatPool is None:
            return None
        cached = wanted.SerializeToString(deterministic=True)
        if cached not in formatKeys:
            formatKeys[cached] = findFormatKey(formatPool, wanted)
        return formatKeys[cached]

    def formatOf(key: int) -> tsk.FormatStructArchive | None:
        """Return the format entry a key names, or None when the table names none."""
        entry = None if formatPool is None else formatPool.entryFind(key)
        return None if entry is None else entry.format

    def formatsCount(
        before: bytes | None, after: bytes | None, where: CellAddress
    ) -> None:
        """Move the format refcounts one written or removed record changed."""
        if formatPool is not None:
            moveFormatReferences(formatPool, before, after, str(where))

    def releaseRecord(record: CellRecord, reference: CellAddress) -> bool:
        """Release every list entry a removed record names, reporting a formula."""
        formatsCount(record.raw, None, reference)
        claimed = (
            (textPool, listStringClaims(record)),
            (stylePool, listStyleClaims(record)),
            (richTextPool, listRichTextClaims(record)),
            (controlPool, listControlClaims(record)),
        )
        for listPool, keys in claimed:
            if listPool is not None:
                for key in keys:
                    listPool.release(key)
        if pool is not None and carriesFormula(record):
            pool.release(record.references[findFormulaKeySlot(record)])
            return True
        return False

    def releaseReplaced(record: CellRecord, written: bytes) -> None:
        """Release the control and rich text a rewrite of a record no longer names."""
        after = decodeRecord(record.column, written)
        control = findSlotValue(record, controlSlot)
        if (
            controlPool is not None and control is not None
            and findSlotValue(after, controlSlot) is None
        ):
            controlPool.release(control)
        if richTextPool is not None and after.typeByte != record.typeByte:
            for key in listRichTextClaims(record):
                richTextPool.release(key)

    def dropUnshownControl(raw: bytes, cell: Cell) -> bytes:
        """Return the record without a control that cannot show the cell's value."""
        control = findSlotValue(decodeRecord(0, raw), controlSlot)
        shown = None if control is None else controls.get(control)
        if shown is None or shown.showsValue(cell.value):
            return raw
        return applyAutomaticFormat(raw, cell.value, formatFor)

    def listControlClaims(record: CellRecord) -> list[int]:
        """Return the control key a record names, if it names one."""
        control = findSlotValue(record, controlSlot)
        return [] if control is None else [control]

    def claimRecord(record: CellRecord, reference: CellAddress) -> bytes:
        """Claim every list entry a duplicated record names, and return it to place."""
        raw = record.raw
        formatsCount(None, raw, reference)
        claimed = (
            (textPool, listStringClaims(record)),
            (stylePool, listStyleClaims(record)),
            (controlPool, listControlClaims(record)),
        )
        for listPool, keys in claimed:
            if listPool is not None:
                for key in keys:
                    listPool.claim(key)
        if pool is not None and carriesFormula(record):
            pool.claim(record.references[findFormulaKeySlot(record)])
        if richTextPool is not None:
            for key in listRichTextClaims(record):
                duplicate = copyRichText(registry, richTextPool, key)
                raw = patchRichTextKey(raw, duplicate)
                # The tile pass reads values through this table, so it learns the copy.
                richText[duplicate] = richText[key]
                richTextPool.touched = True
        return raw

    restructured = maps.changed
    if restructured:
        covered = buildTileRange(index, registry, store)
        spent = moveGridRecords(store, covered, maps, table, releaseRecord, plan)
        writeTileRange(registry, store, covered.tiles, spent)
    written: list[tuple[int, int]] = []
    formulaAdded: list[tuple[int, int]] = []
    formulaRemoved: list[tuple[int, int]] = []
    if moves:
        carried = applyCellMoves(index, registry, model, moves)
        applyConditionChanges(index, registry, store, table)
        # A structural edit registers every formula afresh, so only a move alone
        # names the formulas it carried.
        if not restructured:
            formulaRemoved.extend(stored for stored, _ in carried.formulas)
            formulaAdded.extend(landed for _, landed in carried.formulas)
        written.extend(sorted(set(moves) | set(moves.values())))
    if copies:
        # Claimed as each is placed, before any release, so an entry both name
        # never drops to zero.
        copied = applyCellCopies(index, registry, store, copies, claimRecord)
        for (row, column), record in copied.placed.items():
            if carriesFormula(record):
                formulaAdded.append((row, column))
        for (row, column), record in copied.displaced.items():
            released = releaseRecord(
                record, CellAddress(row + originOffset, column + originOffset)
            )
            placed = copied.placed.get((row, column))
            if released and (placed is None or not carriesFormula(placed)):
                formulaRemoved.append((row, column))
        applyConditionChanges(index, registry, store, table)
        written.extend(sorted(copies.records))

    # A row belongs to the tile covering its index, and a tile that holds nothing
    # may be absent. No table in the 46 documents has such a gap, so this refuses
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
        tile = index.resolve(entry.tile, tst.Tile)
        walkedTiles.append((entry.tileid, tile))
        firstRow = entry.tileid * tileSize
        touched = restructured or bool(moves) or bool(copies)

        # Rows the file stores nothing for, materialized before the walk below,
        # which only ever sees a row that already has storage. Doing it here rather
        # than inside the walk keeps `rowInfos` from being mutated while iterated.
        createdRows: set[int] = set()
        if pool is not None:
            stored = frozenset(
                walked.row for walked in iterateTileRows(entry.tileid, tile, tileSize)
            )
            for missing in findRowsNeedingStorage(table, firstRow, tileSize, stored):
                if not tile.rowInfos and table.colCount > narrowRowSlots:
                    raise WriteError(
                        f"Row {missing + originOffset} of {table.name!r} is the first "
                        f"row of an empty tile in a table of {table.colCount} columns. "
                        "Writing that row for more than 255 columns is not "
                        "supported."
                    )
                createRowStorage(tile, missing - firstRow)
                createdRows.add(missing)
                touched = True

        for walked in iterateTileRows(entry.tileid, tile, tileSize):
            rowInfo, offsetUnit, row = walked.info, walked.unit, walked.row
            replacements: dict[int, bytes] = {}
            removals = frozenset(
                column for (swallowedRow, column) in swallowed if swallowedRow == row
            )
            for record in walked.records:
                reference = CellAddress(
                    row + originOffset, record.column + originOffset
                )
                if (row, record.column) in swallowed:
                    if releaseRecord(record, reference):
                        formulaRemoved.append((row, record.column))
                    continue
                cell = table.cells.get(reference)
                if cell is None:
                    continue
                valueChanged = not isSameValue(
                    readCellValue(record, strings, richText, currencyCodes), cell.value
                )
                edit = classifyFormulaEdit(cell.formula, record, pool)
                chosenChanged = (
                    cell.presentation.formatChosen != carriesChosenFormat(record)
                )
                if not valueChanged and edit == "none" and not chosenChanged:
                    continue
                patched = record.raw
                # The value first, so that writing a value OVER a formula still
                # refuses here rather than being masked by the formula edit below.
                # Attaching a formula is a different act and is allowed.
                if valueChanged:
                    patched = dropUnshownControl(
                        buildWrittenRecord(
                            cell, record, textPool, formatFor=formatFor,
                            formatOf=formatOf,
                        ),
                        cell,
                    )
                    formatsCount(record.raw, patched, reference)
                    releaseReplaced(record, patched)
                if pool is not None and edit != "none":
                    patched = applyFormulaEdit(edit, patched, record, cell, pool)
                    if edit in ("attach", "replace"):
                        formulaAdded.append((row, record.column))
                    elif edit == "detach":
                        formulaRemoved.append((row, record.column))
                replacements[record.column] = applyChosenFormat(patched, cell)
            present = frozenset(record.column for record in walked.records)
            # A cell the model gave a formula to but the file has no record for.
            # The loop above cannot see these: it walks records, and these have
            # none. Skipped when a merge swallowed the position, which is an
            # absence Numbers means rather than one to fill.
            if pool is not None:
                for column in range(table.colCount):
                    if column in present or (row, column) in swallowed:
                        continue
                    reference = CellAddress(row + originOffset, column + originOffset)
                    cell = table.cells.get(reference)
                    if cell is None:
                        continue
                    if cell.formula is not None:
                        replacements[column] = applyChosenFormat(
                            buildFormulaRecord(pool.keyFor(cell.formula)), cell
                        )
                        formulaAdded.append((row, column))
                        continue
                    if cell.value is None:
                        continue
                    # A value needs a record shaped like one this table already
                    # holds, since its trailing references are keys into the
                    # table's own lists rather than anything derivable.
                    shape = findTemplateRecord(
                        index, store, findWrittenTypeByte(cell.value)
                    )
                    if shape is None:
                        shape = decodeRecord(column, plainNumberRecord)
                    replacements[column] = applyChosenFormat(
                        buildWrittenRecord(
                            cell, shape, textPool, borrowed=True, formatFor=formatFor,
                            formatOf=formatOf,
                        ),
                        cell,
                    )
                    formatsCount(None, replacements[column], reference)
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
            index.archiveWrite(entry.tile.identifier, tile)

    tiles = StoredTiles(tileSize, tuple(walkedTiles))
    if plan is not None and restructured:
        writeConditionalCounts(plan, tiles)

    if formatPool is not None and formatPool.touched:
        formatPool.spentRemove(
            tiles, lambda record: countFormatClaims(record.raw).keys()
        )
        index.archiveWrite(store.format_table.identifier, formatPool.dataList)

    if stylePool is not None and stylePool.touched:
        index.archiveWrite(store.styleTable.identifier, stylePool.dataList)

    if richTextPool is not None and richTextPool.touched:
        removeSpentRichText(registry, richTextPool, tiles)
        richTextId = store.rich_text_table.identifier
        index.archiveWrite(
            richTextId, richTextPool.dataList,
            registry.referencesReconcile(richTextId, richTextPool.dataList),
        )

    if controlPool is not None and controlPool.touched:
        # Numbers removed the control no cell named, measured in `63b-fill-menu-down`.
        controlPool.spentRemove(tiles, listControlClaims)
        index.archiveWrite(
            store.control_cell_spec_table.identifier, controlPool.dataList
        )

    if textPool is not None and textPool.touched:
        textPool.spentRemove(tiles, listStringClaims)
        index.archiveWrite(store.stringTable.identifier, textPool.dataList)

    if pool is not None and pool.touched:
        index.archiveWrite(store.formula_table.identifier, pool.dataList)
    return TableEdits(written, formulaAdded, formulaRemoved)


__all__ = [
    "TableEdits",
    "applyTableEdits",
]

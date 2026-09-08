#!/usr/bin/env python3
"""\
Write a `Document` back to a `.numbers` package: the write half of the binding.

The mirror of `pybers.reader`, and it lives outside `pybers.model` for the same
reason that one does, so that importing the model never drags in the persistence
layer. `Document.save` reaches this module through a function-local import. See
CLAUDE.md, "Document is the single handle".

Formulas are in `pybers.writeformula` and the calculation engine's three registers
in `pybers.writeengine`. What is left here is the cell records, the tiles they sit
in, and staging a package on disk.

**Saving mutates the archives that were read rather than building new ones.** A
document holds far more than this model represents yet, and every one of those
parts survives only because nothing touched it. Constructing a fresh package from
the model would silently drop all of it, and the loss would show up as a document
Numbers opens with its charts, conditional formats and print settings quietly
gone, rather than as an error.

UPDATES
2026-09-01  Written for #2: the unchanged round trip.
2026-09-01  Numeric edits reach the tile they came from, for #2.
2026-09-02  Edited cells are marked for recalculation, for #25.
2026-09-02  Merges are written back to the merge store, for #16.
2026-09-08  Formulas and the engine moved to modules of their own, for #45.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"

import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ._generated import TNArchives_pb2 as tn
from ._generated import TSPMessages_pb2 as tsp
from ._generated import TSTArchives_pb2 as tst
from .archives import (
    ArchiveIndex,
    WriteError,
    findRoot,
    originOffset,
    tableInfoTypeId,
)
from .model import Cell, CellReference, Document, MergeRange, Table
from .numbersfile import (
    IWAFile,
    NumbersPackage,
    decodeRow,
    offsetUnitFor,
    writePackage,
)
from .numbersfile.cells import (
    CellRecord,
    carriesFormula,
    emptyOffset,
    formulaKeySlot,
    offsetWidth,
    valueOffset,
)
from .numbersfile.decimal128 import Decimal128, encodedLength
from .readengine import calculationEngine, tableOwnerEntries
from .reader import readMerges, readRichTextTable, readStringTable, resolveValue
from .writeengine import (
    ownerEntryFor,
    registerFormulaCells,
    requestRecalculation,
    writeMergeFormula,
)
from .writeformula import (
    FormulaPool,
    attachFormulaKey,
    buildFormulaRecord,
    detachFormulaKey,
    formulaEdit,
    formulaPoolFor,
    patchFormulaKey,
)

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

    for entry in store.tiles.tiles:
        archive = index.archive(entry.tile.identifier)
        tile = index.resolve(entry.tile, tst.Tile)
        firstRow = entry.tileid * tileSize
        touched = False

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
                edit = formulaEdit(cell, record, pool)
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


def applyDocumentEdits(document: Document, package: NumbersPackage) -> int:
    """Write every changed cell of every table back into the package.

    The model is compared against the archives rather than tracked as it is edited.
    A caller assigns to `Cell.value` directly, so there is no hook to record a
    change, and a comparison cannot go stale the way a dirty flag can.
    """
    index = ArchiveIndex(package)
    owners = {
        archive.identifier: iwaFile
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
    }
    root = findRoot(index)
    written: dict[int, list[tuple[int, int]]] = {}
    entries = tableOwnerEntries(index, calculationEngine(index))

    # Both pairings are checked rather than zipped loosely. A plain `zip` stops at
    # the shorter side, so a model holding fewer sheets than the document does would
    # write some of them and skip the rest in silence, which is the failure this
    # format specializes in. Neither count can legitimately differ: the model was
    # built from these archives.
    if len(document.sheets) != len(root.sheets):
        raise WriteError(
            f"This document holds {len(root.sheets)} sheets and the model holds "
            f"{len(document.sheets)}. Adding or removing a sheet is not supported."
        )
    for sheet, reference in zip(document.sheets, root.sheets, strict=True):
        sheetArchive = index.resolve(reference, tn.SheetArchive)
        tableReferences = [
            drawable for drawable in sheetArchive.drawable_infos
            if index.typeOf(drawable) == tableInfoTypeId
        ]
        if len(sheet.tables) != len(tableReferences):
            raise WriteError(
                f"{sheet.name!r} holds {len(tableReferences)} tables and the model "
                f"holds {len(sheet.tables)}. Adding or removing a table is not "
                "supported."
            )
        for table, tableReference in zip(sheet.tables, tableReferences, strict=True):
            tableInfo = index.resolve(tableReference, tst.TableInfoArchive)
            modelArchive = index.archive(tableInfo.tableModel.identifier)
            model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
            entry = ownerEntryFor(entries, tableReference.identifier, table.name)

            # Only a merge being ADDED clears its covered positions. One already
            # in the file may carry a style-only record at each of them, which an
            # XLSX import writes and Numbers then keeps forever, and stripping
            # those would rewrite a document the caller only asked to save.
            swallowed = frozenset(
                (reference.row - originOffset, reference.col - originOffset)
                for merge in mergesAdded(table, model)
                for reference in merge.extent
                if reference != merge.anchor
            )
            edits = applyTableEdits(index, owners, table, model, swallowed)
            moved = applyMerges(
                table, model, entry.dependencies.formula_owner_uid
            )
            if moved or swallowed:
                owners[modelArchive.identifier].messageReplace(
                    modelArchive.identifier, 0, model.SerializeToString()
                )
            # The engine's register of formula-bearing cells, which is a separate
            # fact from a cell having moved and is what makes a newly attached
            # formula evaluate at all.
            for identifier, body in registerFormulaCells(
                index, entry, edits.formulaAdded, edits.formulaRemoved
            ).items():
                owners[identifier].messageReplace(identifier, 0, body)
            if edits.written or moved:
                written[tableReference.identifier] = (
                    edits.written + sorted(moved)
                )

    requestRecalculation(index, owners, written)
    return sum(len(cells) for cells in written.values())


def targetFor(document: Document, path: Path | str | None) -> Path:
    """Resolve where a save lands: the argument, or where the document came from.

    A document that was never read from disk has no path to fall back on, so an
    argumentless save on one is refused rather than guessed at.
    """
    if path is not None:
        return Path(path)
    if document._sourcePath is None:
        raise WriteError(
            "This document was not read from a file, so there is nowhere to save "
            "it in place. Pass a path to save."
        )
    return document._sourcePath


def writeAtomically(package: NumbersPackage, target: Path) -> None:
    """Write a package to a temporary name beside the target, then take its place.

    A `.numbers` package is a zip rewritten whole, so writing straight to the
    target would leave a truncated file where the document used to be if anything
    failed part way through. The temporary lands in the same directory, and
    therefore on the same filesystem, which is what makes the replacement atomic.
    """
    directory = target.parent
    if not directory.is_dir():
        raise WriteError(f"Cannot save to {target}: {directory} is not a directory.")

    # Opened only to reserve a unique name in the target's own directory, so that
    # the replace below is atomic on the same filesystem. `delete=False` keeps the
    # file after the block, and the block is what closes it.
    with tempfile.NamedTemporaryFile(
        dir=directory, prefix=f".{target.stem}-", suffix=".numbers", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        writePackage(package, temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def writeDocument(document: Document, path: Path | str | None = None) -> None:
    """Write a document back to a `.numbers` package.

    Reached through `Document.save`, which is the caller-facing spelling. This
    function exists separately so the model layer can stay free of any import of
    the persistence layer.
    """
    package = document._package
    if package is None:
        raise WriteError(
            "This document carries no archives, so there is nothing to write. Only "
            "a document from `pybers.open` can be saved; building one from scratch "
            "is not supported yet."
        )
    applyDocumentEdits(document, package)
    writeAtomically(package, targetFor(document, path))


# `Document.save` reaches `writeDocument` and nothing else, and no other module in
# `src/` imports from here at all. Everything above exists to get that one function
# its job done, so it is named for the call site rather than for a caller who does
# not exist. Stated rather than assumed, because a published package makes every
# undeclared name someone else's dependency.
__all__ = ["WriteError", "writeDocument"]

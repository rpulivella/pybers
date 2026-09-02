#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Write a `Document` back to a `.numbers` package: the write half of the binding.

The mirror of `pybers.reader`, and it lives outside `pybers.model` for the same
reason that one does, so that importing the model never drags in the
persistence layer. `Document.save` reaches this module through a function-local import. See
CLAUDE.md, "Document is the single handle".

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
from decimal import Decimal
from pathlib import Path

from ._generated import TNArchives_pb2 as tn
from ._generated import TSCEArchives_pb2 as tsce
from ._generated import TSTArchives_pb2 as tst
from .model import Cell, CellReference, Document, Table
from .numbersfile import IWAFile, NumbersPackage, decodeRow, writePackage
from .numbersfile.types import archiveTypeId, parseArchive
from .numbersfile.cells import (
    CellRecord,
    emptyOffsetNarrow,
    emptyOffsetWide,
    valueOffset,
)
from .numbersfile.decimal128 import Decimal128, encodedLength
from .reader import (
    ArchiveIndex,
    findRoot,
    originOffset,
    readRichTextTable,
    readStringTable,
    resolveValue,
    tableInfoTypeId,
)

# `TST.Tile` and the type bytes a numeric record may carry. 2 is a plain number
# and 10 is currency, which is the same encoding under a different type.
tileTypeId: int = 6002

# `TSCE.CalculationEngineArchive`, and the `owner_kind` a table's dependency entry
# carries. Both are named rather than written as literals where they are used,
# because a bare 4000 in a comprehension says nothing about what is being looked for.
calculationEngineTypeId: int = 4000
tableOwnerKind: int = 1
numericTypeBytes: tuple[int, ...] = (2, 10)

# Byte 9 of a record's header is a bitmask, and this bit marks a cell backed by a
# formula. Established across the corpus on 2026-09-01: in all 74 tables, a table
# declaring formulas has marked records and a table declaring none has none. The
# marked count can exceed the declared count, because the formula list is pooled,
# so a dragged formula and a merge both reuse one entry across several cells.
formulaFlagOffset: int = 9
formulaFlagBit: int = 0x02

# A record's value is patched in place, leaving the twelve-byte header and the
# trailing references alone. Those references point at the table's format and
# style lists, so rewriting the whole record would strip a cell's number format
# while appearing to succeed.
valueEnd: int = valueOffset + encodedLength


class WriteError(RuntimeError):
    """A document that could not be written back to a package."""


def carriesFormula(record: CellRecord) -> bool:
    """Report whether a cell record is backed by a formula."""
    return (
        len(record.raw) > formulaFlagOffset
        and bool(record.raw[formulaFlagOffset] & formulaFlagBit)
    )


def valueChecked(cell: Cell, record: CellRecord) -> Decimal:
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


def recordPatched(record: CellRecord, value: Decimal) -> bytes:
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
    return record.raw[:valueOffset] + Decimal128(value).asBytes() + record.raw[valueEnd:]


def rowRewritten(
    offsets: bytes, buffer: bytes, wide: bool, replacements: dict[int, bytes]
) -> tuple[bytes, bytes]:
    """Rebuild one row's offset array and storage buffer with some records replaced.

    The whole row is rebuilt rather than patched in place because a record's offset
    is where the previous ones ended, so a record that changes length moves every
    record after it. Untouched records are re-emitted from the bytes they were read
    from, so a row with one edit differs in exactly one record.
    """
    width = 4 if wide else 2
    empty = emptyOffsetWide if wide else emptyOffsetNarrow
    slots = len(offsets) // width
    existing = {record.column: record for record in decodeRow(offsets, buffer, wide)}

    rebuiltOffsets = bytearray()
    rebuiltBuffer = bytearray()
    for column in range(slots):
        record = existing.get(column)
        if record is None:
            rebuiltOffsets += empty.to_bytes(width, "little")
            continue
        rebuiltOffsets += len(rebuiltBuffer).to_bytes(width, "little")
        rebuiltBuffer += replacements.get(column, record.raw)
    return bytes(rebuiltOffsets), bytes(rebuiltBuffer)


def tableEditsApplied(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    table: Table,
    model: tst.TableModelArchive,
) -> list[tuple[int, int]]:
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
    written: list[tuple[int, int]] = []

    for entry in store.tiles.tiles:
        archive = index.archive(entry.tile.identifier)
        tile = index.resolve(entry.tile, tst.Tile)
        firstRow = entry.tileid * tileSize
        touched = False

        for rowInfo in tile.rowInfos:
            wide = rowInfo.has_wide_offsets or tile.should_use_wide_rows
            row = firstRow + rowInfo.tile_row_index
            replacements: dict[int, bytes] = {}
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, wide
            ):
                cell = table.cells.get(
                    CellReference(row + originOffset, record.column + originOffset)
                )
                if cell is None or cell.value == resolveValue(
                    record, strings, richText
                ):
                    continue
                replacements[record.column] = recordPatched(
                    record, valueChecked(cell, record)
                )
            if not replacements:
                continue
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rowRewritten(
                rowInfo.cell_offsets,
                rowInfo.cell_storage_buffer,
                wide,
                replacements,
            )
            written.extend((row, column) for column in replacements)
            touched = True

        if touched:
            owners[archive.identifier].messageReplace(
                archive.identifier, 0, tile.SerializeToString()
            )
    return written


def tableOwnerIds(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, int]:
    """Return each table's internal calculation-engine owner id, keyed by its archive.

    Read the long way round because there is no short one: a table does not record
    its owner id. The mapping lives in the dependency tracker, where the entry whose
    `owner_kind` is 1 and whose `formula_owner` points at a `TST.TableInfoArchive`
    carries the id for that table. Measured 2026-09-02, see findings-02-formulas.md.
    """
    ownerIds: dict[int, int] = {}
    for reference in engine.dependency_tracker.formula_owner_dependencies:
        dependencies = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        if dependencies.owner_kind != tableOwnerKind:
            continue
        if not dependencies.HasField("formula_owner"):
            continue
        ownerIds[dependencies.formula_owner.identifier] = (
            dependencies.internal_formula_owner_id
        )
    return ownerIds


def dirtySetBuilt(
    edits: dict[int, list[tuple[int, int]]]
) -> tsce.ReferencesToDirtyArchive:
    """Return the archive naming every cell that moved, grouped as Numbers groups them.

    Owners hold columns, columns hold a set of row ranges. Contiguous rows collapse
    into one range, which is how Numbers writes its own, and a run of one omits
    `range_end` rather than repeating the beginning.
    """
    dirty = tsce.ReferencesToDirtyArchive()
    for ownerId, cells in sorted(edits.items()):
        dirty.to_dirty_owner_ids.entries.add(range_begin=ownerId)
        owner = dirty.to_dirty_cells.owner_entries.add()
        owner.owner_id = ownerId
        byColumn: dict[int, list[int]] = {}
        for row, column in sorted(set(cells)):
            byColumn.setdefault(column, []).append(row)
        for column, rows in sorted(byColumn.items()):
            entry = owner.coord_set.column_entries.add()
            entry.column = column
            start = previous = rows[0]
            for row in rows[1:] + [None]:
                if row == previous + 1:
                    previous = row
                    continue
                added = entry.row_set.entries.add(range_begin=start)
                if previous != start:
                    added.range_end = previous
                if row is None:
                    break
                start = previous = row
    return dirty


def recalculationRequested(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    written: dict[int, list[tuple[int, int]]],
) -> int:
    """Tell Numbers which cells moved, so it recalculates whatever depends on them.

    **A formula caches its result, and opening the document does not refresh it.**
    Patching a cell's value bytes leaves the calculation engine with no reason to know
    a dependency changed, so a document saved without this displays arithmetic that
    disagrees with its own operands, silently and with no repair prompt.

    Naming the edited cells is enough. Numbers walks its own dependency graph from
    there, transitively and across tables and sheets, which is why this library never
    evaluates a formula and never writes a result. Measured 2026-09-02 twice, a broad
    set naming the dependent formulas and a minimal one naming only the edited cells
    producing identical output; findings-02-formulas.md records both.

    Everything here is reached only when something actually changed, so a save that
    edits nothing does no engine work at all.
    """
    if not written:
        return 0
    engineArchive = next(
        (
            archive for archive in index.byIdentifier.values()
            if archiveTypeId(archive) == calculationEngineTypeId
        ),
        None,
    )
    if engineArchive is None:
        raise WriteError(
            "This document has no TSCE.CalculationEngineArchive, so Numbers cannot "
            "be asked to recalculate and the saved file would display stale formula "
            "results. Every document in the fixture corpus carries one."
        )
    engine = parseArchive(engineArchive)
    if not isinstance(engine, tsce.CalculationEngineArchive):
        raise WriteError(
            f"Archive {engineArchive.identifier} carries the calculation engine's "
            f"type but parsed as {type(engine).__name__}."
        )
    if not engine.HasField("refs_to_dirty"):
        raise WriteError(
            "The calculation engine carries no refs_to_dirty reference, so the cells "
            "that changed cannot be marked and the saved file would display stale "
            "formula results."
        )

    ownerIds = tableOwnerIds(index, engine)
    edits: dict[int, list[tuple[int, int]]] = {}
    for tableIdentifier, cells in written.items():
        ownerId = ownerIds.get(tableIdentifier)
        if ownerId is None:
            raise WriteError(
                f"The table in archive {tableIdentifier} has no calculation-engine "
                "owner id, so the cells edited in it cannot be marked for "
                "recalculation and the saved file would display stale results."
            )
        edits.setdefault(ownerId, []).extend(cells)

    target = engine.refs_to_dirty.identifier
    owners[target].messageReplace(target, 0, dirtySetBuilt(edits).SerializeToString())
    return sum(len(cells) for cells in edits.values())


def documentEditsApplied(document: Document, package: NumbersPackage) -> int:
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

    for sheet, reference in zip(document.sheets, root.sheets):
        sheetArchive = index.resolve(reference, tn.SheetArchive)
        tableReferences = [
            drawable for drawable in sheetArchive.drawable_infos
            if index.typeOf(drawable) == tableInfoTypeId
        ]
        for table, tableReference in zip(sheet.tables, tableReferences):
            tableInfo = index.resolve(tableReference, tst.TableInfoArchive)
            cells = tableEditsApplied(
                index,
                owners,
                table,
                index.resolve(tableInfo.tableModel, tst.TableModelArchive),
            )
            if cells:
                written[tableReference.identifier] = cells

    recalculationRequested(index, owners, written)
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

    handle = tempfile.NamedTemporaryFile(
        dir=directory, prefix=f".{target.stem}-", suffix=".numbers", delete=False
    )
    handle.close()
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
    documentEditsApplied(document, package)
    writeAtomically(package, targetFor(document, path))

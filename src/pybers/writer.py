#!/usr/bin/env python3
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
2026-09-02  Merges are written back to the merge store, for #16.
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
from ._generated import TSPMessages_pb2 as tsp
from ._generated import TSTArchives_pb2 as tst
from .model import Cell, CellReference, Document, MergeRange, Table
from .numbersfile import IWAFile, NumbersPackage, decodeRow, writePackage
from .numbersfile.cells import (
    CellRecord,
    emptyOffsetNarrow,
    emptyOffsetWide,
    valueOffset,
)
from .numbersfile.decimal128 import Decimal128, encodedLength
from .numbersfile.types import archiveTypeId, parseArchive
from .reader import (
    ArchiveIndex,
    findRoot,
    originOffset,
    readMerges,
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

# A merge is written as `SUM($A$1:$B$1)`, so it carries SUM's index in Apple's own
# function table. The number is theirs and is not derivable from the schemas.
sumFunctionIndex: int = 168

# A `TSP.UUID` is two 64-bit halves and a formula's table identifier is four 32-bit
# words, so the same value is spelled two ways and has to be converted between them.
wordBits: int = 32
wordMask: int = 0xFFFFFFFF
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
    return record.raw[:valueOffset] + Decimal128(value).asBytes() + record.raw[valueEnd:]


def rewriteRow(
    offsets: bytes,
    buffer: bytes,
    wide: bool,
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
    width = 4 if wide else 2
    empty = emptyOffsetWide if wide else emptyOffsetNarrow
    slots = len(offsets) // width
    existing = {record.column: record for record in decodeRow(offsets, buffer, wide)}

    rebuiltOffsets = bytearray()
    rebuiltBuffer = bytearray()
    for column in range(slots):
        record = existing.get(column)
        if record is None or column in removals:
            rebuiltOffsets += empty.to_bytes(width, "little")
            continue
        rebuiltOffsets += len(rebuiltBuffer).to_bytes(width, "little")
        rebuiltBuffer += replacements.get(column, record.raw)
    return bytes(rebuiltOffsets), bytes(rebuiltBuffer)


def applyTableEdits(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    table: Table,
    model: tst.TableModelArchive,
    swallowed: frozenset[tuple[int, int]] = frozenset(),
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
            removals = frozenset(
                column for (swallowedRow, column) in swallowed if swallowedRow == row
            )
            for record in decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, wide
            ):
                if (row, record.column) in swallowed:
                    continue
                cell = table.cells.get(
                    CellReference(row + originOffset, record.column + originOffset)
                )
                if cell is None or cell.value == resolveValue(
                    record, strings, richText
                ):
                    continue
                replacements[record.column] = patchRecord(
                    record, checkedValue(cell, record)
                )
            present = frozenset(
                record.column
                for record in decodeRow(
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, wide
                )
            )
            dropped = removals & present
            if not replacements and not dropped:
                continue
            rowInfo.cell_offsets, rowInfo.cell_storage_buffer = rewriteRow(
                rowInfo.cell_offsets,
                rowInfo.cell_storage_buffer,
                wide,
                replacements,
                dropped,
            )
            written.extend((row, column) for column in replacements)
            touched = True

        if touched:
            owners[archive.identifier].messageReplace(
                archive.identifier, 0, tile.SerializeToString()
            )
    return written


def buildDirtySet(
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
            runs: list[list[int]] = []
            for row in rows:
                if runs and row == runs[-1][1] + 1:
                    runs[-1][1] = row
                else:
                    runs.append([row, row])
            for begin, end in runs:
                added = entry.row_set.entries.add(range_begin=begin)
                if end != begin:
                    added.range_end = end
    return dirty


def calculationEngine(index: ArchiveIndex) -> tsce.CalculationEngineArchive:
    """Return the document's one calculation engine, or refuse and say why.

    Exactly one archive in a document carries this type, the same way exactly one
    carries `TN.DocumentArchive`. All 46 fixtures have one, so a document without
    one is not what this library expects rather than a case to work around.
    """
    found = [
        archive for archive in index.byIdentifier.values()
        if archiveTypeId(archive) == calculationEngineTypeId
    ]
    if len(found) != 1:
        raise WriteError(
            f"Expected exactly one TSCE.CalculationEngineArchive, found {len(found)}. "
            "Without it neither a merge nor a recalculation request can be written."
        )
    engine = parseArchive(found[0])
    if not isinstance(engine, tsce.CalculationEngineArchive):
        raise WriteError(
            f"Archive {found[0].identifier} carries the calculation engine's type "
            f"but parsed as {type(engine).__name__}."
        )
    return engine


def ownerEntryFor(
    entries: dict[int, tsce.FormulaOwnerDependenciesArchive],
    identifier: int,
    name: str,
) -> tsce.FormulaOwnerDependenciesArchive:
    """Return one table's dependency entry, or refuse naming the table."""
    entry = entries.get(identifier)
    if entry is None:
        raise WriteError(
            f"{name!r} has no calculation-engine owner entry, so neither its merges "
            "nor its edited cells can be written. Every table in the fixture corpus "
            "has one."
        )
    return entry


def tableOwnerEntries(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, tsce.FormulaOwnerDependenciesArchive]:
    """Return each table's dependency entry, keyed by its `TST.TableInfoArchive`.

    Read the long way round because there is no short one: a table records neither
    its internal owner id nor its owner uid. Both live here, on the entry whose
    `owner_kind` is 1 and whose `formula_owner` points back at the table. Measured
    2026-09-02, see findings-02-formulas.md and findings-03-structure.md.
    """
    entries: dict[int, tsce.FormulaOwnerDependenciesArchive] = {}
    for reference in engine.dependency_tracker.formula_owner_dependencies:
        dependencies = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        if dependencies.owner_kind != tableOwnerKind:
            continue
        if not dependencies.HasField("formula_owner"):
            continue
        entries[dependencies.formula_owner.identifier] = dependencies
    return entries


def tableOwnerIds(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, int]:
    """Return each table's internal owner id, keyed by its own archive."""
    return {
        identifier: entry.internal_formula_owner_id
        for identifier, entry in tableOwnerEntries(index, engine).items()
    }


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


def applyMerges(
    table: Table, model: tst.TableModelArchive, ownerUid: tsp.UUID
) -> frozenset[tuple[int, int]]:
    """Rewrite a table's merge store when its merges differ, and say which cells moved.

    **A merge changes what a formula reference means, so it changes results.** A cell
    covered by a merge cannot be referenced, so `=J1` is a valid number while `I1:J1`
    is apart and an invalid reference once it is merged. Measured 2026-09-02 across
    `22-merge-2x2` and its unmerged twin: the same `L1` is a formula-error cell in
    one and a plain number in the other. So every position whose merge state changed
    is returned, for the same dirty-marking that a value edit gets, or the saved file
    displays the result the reference had before.

    **The store is emptied rather than removed when the last merge goes.** Measured
    across `22-merge-2x2` and its unmerged twin: the merged table holds five formulas
    and the unmerged one holds zero, and `merge_owner` is present in both. Deleting
    it would produce something Numbers does not write.

    Compared against what is stored rather than tracked as merges are added, for the
    same reason cell edits are: a caller reaches `mergeRanges` directly, so there is
    no hook, and a comparison cannot go stale the way a dirty flag can.
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


def requestRecalculation(
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
    owners[target].messageReplace(target, 0, buildDirtySet(edits).SerializeToString())
    return sum(len(cells) for cells in edits.values())


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

    for sheet, reference in zip(document.sheets, root.sheets):
        sheetArchive = index.resolve(reference, tn.SheetArchive)
        tableReferences = [
            drawable for drawable in sheetArchive.drawable_infos
            if index.typeOf(drawable) == tableInfoTypeId
        ]
        for table, tableReference in zip(sheet.tables, tableReferences):
            tableInfo = index.resolve(tableReference, tst.TableInfoArchive)
            modelArchive = index.archive(tableInfo.tableModel.identifier)
            model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
            entry = ownerEntryFor(entries, tableReference.identifier, table.name)

            # A cell a merge swallowed has NO record in the file, so its record is
            # dropped rather than left behind as an empty one Numbers never wrote.
            swallowed = frozenset(
                (reference.row - originOffset, reference.col - originOffset)
                for merge in table.mergeRanges
                for reference in merge.extent
                if reference != merge.anchor
            )
            cells = applyTableEdits(index, owners, table, model, swallowed)
            moved = applyMerges(table, model, entry.formula_owner_uid)
            if moved or swallowed:
                owners[modelArchive.identifier].messageReplace(
                    modelArchive.identifier, 0, model.SerializeToString()
                )
            if cells or moved:
                written[tableReference.identifier] = cells + sorted(moved)

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
    applyDocumentEdits(document, package)
    writeAtomically(package, targetFor(document, path))


# `Document.save` reaches `writeDocument` and nothing else, and no other module in
# `src/` imports from here at all. Everything above exists to get that one function
# its job done, so it is named for the call site rather than for a caller who does
# not exist. Stated rather than assumed, because a published package makes every
# undeclared name someone else's dependency.
__all__ = ["WriteError", "writeDocument"]

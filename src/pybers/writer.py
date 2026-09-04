#!/usr/bin/env python3
"""\
Write a `Document` back to a `.numbers` package: the write half of the binding.

The mirror of `pybers.reader`, and it lives outside `pybers.model` for the same
reason that one does, so that importing the model never drags in the persistence
layer. `Document.save` reaches this module through a function-local import. See
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

import struct
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

from ._generated import TNArchives_pb2 as tn
from ._generated import TSCEArchives_pb2 as tsce
from ._generated import TSPMessages_pb2 as tsp
from ._generated import TSTArchives_pb2 as tst
from .model import (
    Cell,
    CellReference,
    Coordinate,
    Document,
    Formula,
    FormulaFunctionCall,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaUnknownCall,
    MergeRange,
    Span,
    Table,
)
from .model.formula import brokenColumnSentinel, brokenRowSentinel
from .numbersfile import IWAFile, NumbersPackage, decodeRow, writePackage
from .numbersfile.cells import (
    CellRecord,
    carriesFormula,
    decodeCellValue,
    emptyOffsetNarrow,
    emptyOffsetWide,
    formulaFlagBit,
    formulaFlagOffset,
    valueOffset,
)
from .numbersfile.decimal128 import Decimal128, encodedLength
from .numbersfile.types import archiveTypeId, parseArchive
from .reader import (
    ArchiveIndex,
    ColonTractAxis,
    decimalHalfFormat,
    findRoot,
    formulaKeySlot,
    originOffset,
    readFormulaTable,
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

# Every trailing reference in a cell record is a little-endian uint32.
referenceWidth: int = 4

# The calculation engine tiles its register of formula-bearing cells 32 columns
# wide. Measured 2026-09-04: `40-table-bands` carries eight tiles beginning at
# columns 0, 32, 64 and so on to 224, and every tile in the corpus begins at row
# zero, so the row extent of a tile is not established and is never assumed here.
dependencyTileColumns: int = 32

# The generated container both copies of that register are held in. Named so the
# one function updating either can say what it takes.
type CellRecordList = RepeatedCompositeFieldContainer[
    tsce.CellRecordExpandedArchive
]

# Byte 0 of every cell record in the corpus. A created record carries it too.
storageVersion: int = 5

# The type a formula cell takes when no result is stored, which is what Numbers
# writes for a formula it could not compute and what a formula pybers just wrote
# genuinely is until Numbers recalculates.
formulaPendingType: int = 8

# A record's value is patched in place, leaving the twelve-byte header and the
# trailing references alone. Those references point at the table's format and
# style lists, so rewriting the whole record would strip a cell's number format
# while appearing to succeed.
valueEnd: int = valueOffset + encodedLength


class WriteError(RuntimeError):
    """A document that could not be written back to a package."""


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
        body = replacements.get(column)
        if body is None and record is not None:
            body = record.raw
        # A replacement for a column with no record CREATES one, which is how a
        # formula reaches a cell that was empty. The offset array already carries a
        # slot for every column, so nothing grows.
        if body is None or column in removals:
            rebuiltOffsets += empty.to_bytes(width, "little")
            continue
        rebuiltOffsets += len(rebuiltBuffer).to_bytes(width, "little")
        rebuiltBuffer += body
    return bytes(rebuiltOffsets), bytes(rebuiltBuffer)


def encodeCoordinate(coordinate: Coordinate) -> int:
    """Return one axis as the file stores it, undoing the reader's conversion.

    An absolute axis is a line counted from one in the model and from zero in the
    file. A relative axis is a distance and means the same in both, so shifting one
    would move every relative reference by a row and raise nothing.
    """
    return (
        coordinate.value - originOffset if coordinate.absolute else coordinate.value
    )


def encodeSpan(target: ColonTractAxis, span: Span) -> None:
    """Fill one range-tract axis, omitting `range_end` for a span of one line.

    Omitted rather than repeated, because that is how Numbers writes it and a
    range carrying a redundant end is a difference in a file that had none.
    """
    shift = originOffset if span.absolute else 0
    target.range_begin = span.begin - shift
    if span.end is not None:
        target.range_end = span.end - shift


def encodeFormulaNode(
    node: FormulaNode,
) -> tsce.ASTNodeArrayArchive.ASTNodeArchive:
    """Return one node as an archive, patching what was read rather than rebuilding.

    The node message carries 45 fields and this model gives meaning to 16 of them,
    so a node built from scratch would silently drop everything else it was
    carrying. Starting from the bytes as read and overwriting only what the model
    owns is what lets an unrecognized node survive a rewritten formula intact.
    """
    archive = tsce.ASTNodeArrayArchive.ASTNodeArchive()
    if node.raw:
        archive.ParseFromString(node.raw)
    # Assigned as an int rather than through the generated enum, because an
    # unrecognized type has to survive and the enum names only what Apple
    # declared. The wire form is a varint either way.
    archive.AST_node_type = cast(
        "tsce.ASTNodeArrayArchive.ASTNodeType.ValueType", node.nodeType
    )

    content = node.content
    if isinstance(content, Decimal):
        # decimal128 and the float64 copy beside it, because Numbers writes both
        # and a reader of either has to find the same number.
        low, high = struct.unpack(
            decimalHalfFormat, Decimal128(content).asBytes()
        )
        archive.AST_number_node_decimal_low = low
        archive.AST_number_node_decimal_high = high
        archive.AST_number_node_number = float(content)
    elif isinstance(content, str):
        archive.AST_string_node_string = content
    elif isinstance(content, FormulaFunctionCall):
        archive.AST_function_node_index = content.index
        archive.AST_function_node_numArgs = content.argumentCount
    elif isinstance(content, FormulaUnknownCall):
        archive.AST_unknown_function_node_string = content.name
        archive.AST_unknown_function_node_numArgs = content.argumentCount
    elif isinstance(content, FormulaReference):
        encodeFormulaReference(archive, content)
    elif isinstance(content, FormulaRange):
        encodeFormulaRange(archive, content)
    return archive


def encodeFormulaReference(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, reference: FormulaReference
) -> None:
    """Write a single-cell reference, restoring the sentinels for a broken one.

    A broken reference is written back exactly as it was found rather than
    repaired into a real cell. Numbers records `#REF` as coordinates deliberately
    pointing nowhere, and quietly turning that into a working reference would
    change what the document says.
    """
    if reference.broken:
        archive.AST_column.column = brokenColumnSentinel
        archive.AST_row.row = brokenRowSentinel
        return
    if reference.column is None:
        archive.ClearField("AST_column")
    else:
        archive.AST_column.column = encodeCoordinate(reference.column)
        archive.AST_column.absolute = reference.column.absolute
    # Absence is how the file expresses a whole column, so an axis the model
    # dropped is cleared rather than written as zero.
    if reference.row is None:
        archive.ClearField("AST_row")
    else:
        archive.AST_row.row = encodeCoordinate(reference.row)
        archive.AST_row.absolute = reference.row.absolute


def encodeFormulaRange(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, extent: FormulaRange
) -> None:
    """Write one range tract into the field variant its anchoring belongs in.

    The variant an axis sits in IS its anchoring, so every variant is cleared
    first. Writing a relative axis without clearing the absolute one would leave a
    tract claiming both, which the reader resolves by preferring the relative and
    which Numbers has never been observed to write.
    """
    tract = archive.AST_colon_tract
    for name in ("relative_column", "relative_row",
                 "absolute_column", "absolute_row"):
        tract.ClearField(name)
    if extent.columns is not None:
        field = (
            tract.absolute_column if extent.columns.absolute
            else tract.relative_column
        )
        encodeSpan(field.add(), extent.columns)
    if extent.rows is not None:
        field = (
            tract.absolute_row if extent.rows.absolute else tract.relative_row
        )
        encodeSpan(field.add(), extent.rows)


def encodeFormula(formula: Formula) -> tsce.FormulaArchive:
    """Return a whole formula as the postfix node array the file stores."""
    archive = tsce.FormulaArchive()
    for node in formula:
        archive.AST_node_array.AST_node.append(encodeFormulaNode(node))
    return archive


@dataclass(slots=True)
class FormulaPool:
    """A table's pooled formulas, and the one place a changed one is written.

    Numbers shares one stored archive between every cell a formula was dragged
    into, so overwriting an entry that more than one cell names would edit all of
    them at once. That is the same aliasing hazard the frozen model closes on the
    read side, and it has to be closed again here: a shared entry is split rather
    than overwritten, leaving the cells that did not change pointing at what they
    always pointed at.
    """

    dataList: tst.TableDataList
    stored: dict[int, Formula]
    touched: bool = False

    def formulaFor(self, key: int) -> Formula | None:
        """Return the formula a key names, or None when the table has no such entry."""
        return self.stored.get(key)

    def entryFor(self, key: int) -> tst.TableDataList.ListEntry | None:
        """Return one pooled entry by key, or None when the table has no such key."""
        for entry in self.dataList.entries:
            if entry.key == key:
                return entry
        return None

    def keyFor(self, formula: Formula, previous: int | None = None) -> int:
        """Return the key a cell should name, sharing an entry when one matches.

        **Sharing is the only path, and that is what makes filling a column correct.**
        Numbers points every cell a formula was dragged into at ONE archive, so a
        relative reference resolves against whichever cell holds it and anchoring
        needs no special cases. Writing an entry per cell passes a naive test and
        diverges the moment an axis is locked.

        `previous` is the key the cell names now, released when it stops naming it.
        A shared entry is split rather than overwritten, so the cells that did not
        change keep what they had.
        """
        self.touched = True
        for key, stored in self.stored.items():
            entry = self.entryFor(key)
            if stored != formula or entry is None:
                continue
            if key == previous:
                return key
            entry.refcount += 1
            if previous is not None:
                self.release(previous)
            return key

        # Nothing identical is stored. An entry only this cell names may be
        # rewritten in place; a shared one must not be.
        existing = self.entryFor(previous) if previous is not None else None
        if existing is not None and existing.refcount <= 1:
            existing.formula.CopyFrom(encodeFormula(formula))
            self.stored[existing.key] = formula
            return existing.key
        if previous is not None:
            self.release(previous)
        fresh = self.dataList.entries.add()
        fresh.key = self.dataList.nextListID
        fresh.refcount = 1
        fresh.formula.CopyFrom(encodeFormula(formula))
        self.dataList.nextListID += 1
        self.stored[fresh.key] = formula
        return fresh.key

    def release(self, key: int) -> None:
        """Give up one cell's claim on a stored formula.

        The entry stays when others still name it, and is emptied rather than deleted
        when none do: `nextListID` never reuses a key, so a spent entry costs a few
        bytes and removing one would invite a reader to assume keys are dense.
        """
        entry = self.entryFor(key)
        if entry is None:
            return
        self.touched = True
        entry.refcount = max(0, entry.refcount - 1)
        if entry.refcount == 0:
            entry.ClearField("formula")
            self.stored.pop(key, None)


def formulaKeyOffset(record: CellRecord) -> int:
    """Return where a record keeps its formula key.

    Computed from the value's own width rather than from a constant, because the
    key sits immediately after the value and a date, a boolean and a number are
    three different widths. An error cell consumes no value at all, which is why
    the same arithmetic finds its key at byte 12.
    """
    _, width = decodeCellValue(record.typeByte, record.raw[valueOffset:])
    return valueOffset + width + formulaKeySlot * referenceWidth


def buildFormulaRecord(key: int) -> bytes:
    """Return a record for a cell that had none, holding a formula and no result.

    Exactly the shape Numbers writes for a formula whose result it could not
    compute: type 8, byte 8 clear, byte 9 carrying only the formula bit, and the key
    as the single trailing reference. Measured on the ten error cells in
    `21-formula-errors`. That is the honest state for a formula pybers has just
    written, since pybers never evaluates and Numbers recalculates on open.
    """
    header = bytearray(valueOffset)
    header[0] = storageVersion
    header[1] = formulaPendingType
    header[formulaFlagOffset] = formulaFlagBit
    return bytes(header) + key.to_bytes(referenceWidth, "little")


def attachFormulaKey(raw: bytes, record: CellRecord, key: int) -> bytes:
    """Return a record that had no formula, now naming one.

    Measured corpus-wide 2026-09-04: a formula-backed record is the plain record for
    the same result type with byte 9 bit `0x02` set and ONE more trailing reference,
    the key, ahead of the others. Byte 8 never moves, being fixed by the type.

    Derived from matched pairs rather than synthesized, because the rest of byte 9
    encodes things this library does not model. The cached value stays and becomes
    the placeholder, which Numbers repairs while recalculating.
    """
    at = formulaKeyOffset(record)
    if len(raw) < at:
        raise WriteError(
            f"column {record.column} is {len(raw)} bytes and its formula key would "
            f"sit at {at}, past the end."
        )
    patched = bytearray(raw)
    patched[formulaFlagOffset] |= formulaFlagBit
    return (
        bytes(patched[:at])
        + key.to_bytes(referenceWidth, "little")
        + bytes(patched[at:])
    )


def detachFormulaKey(raw: bytes, record: CellRecord) -> bytes:
    """Return a record with its formula removed, keeping the value it last computed.

    The exact inverse of `attachFormulaKey`. The cached result stays, so the cell
    becomes an ordinary one holding the number the formula produced, rather than
    emptying and losing what a reader could see a moment earlier.
    """
    at = formulaKeyOffset(record)
    if len(raw) < at + referenceWidth:
        raise WriteError(
            f"column {record.column} is marked as carrying a formula, but its record "
            f"is {len(raw)} bytes and the key would sit at {at}."
        )
    patched = bytearray(raw)
    patched[formulaFlagOffset] &= ~formulaFlagBit & 0xFF
    return bytes(patched[:at]) + bytes(patched[at + referenceWidth:])


def patchFormulaKey(raw: bytes, record: CellRecord, key: int) -> bytes:
    """Point a cell record at a different formula, leaving everything else alone.

    Four bytes in place, because the references after this one address the table's
    format and style lists and rewriting the record would strip a cell's number
    format while appearing to succeed.
    """
    at = formulaKeyOffset(record)
    if len(raw) < at + referenceWidth:
        raise WriteError(
            f"{record.column} is marked as carrying a formula, but its record is "
            f"{len(raw)} bytes and the key would sit at {at}."
        )
    return raw[:at] + key.to_bytes(referenceWidth, "little") + raw[at + referenceWidth:]


def formulaPoolFor(
    index: ArchiveIndex, store: tst.DataStore
) -> FormulaPool | None:
    """Return the table's formula pool, or None when it declares no formulas.

    A table that has never held one carries no list to write into, which is a
    distinct state from a table whose list is empty and is why this returns None
    rather than an empty pool.
    """
    if not store.formula_table.identifier:
        return None
    return FormulaPool(
        dataList=index.resolve(store.formula_table, tst.TableDataList),
        stored=readFormulaTable(index, store),
    )


def formulaEdit(cell: Cell, record: CellRecord, pool: FormulaPool | None) -> str:
    """Return which of the four things happened to this cell's formula.

    `attach`, `detach`, `replace`, or `none`. Named rather than returned as a pair
    of booleans, because the three actions are mutually exclusive and a caller
    reading `if attaching and not detaching` would be reading a state that cannot
    occur.

    Compared against what the POOL holds rather than against anything on the
    record, because the record carries only a key. Comparing the model's formula
    against that key would make every formula cell look edited on every save, the
    same trap the string table already sidesteps.
    """
    if pool is None:
        return "none"
    stored = carriesFormula(record) and len(record.references) > formulaKeySlot
    if cell.formula is not None and not stored:
        return "attach"
    if cell.formula is None and stored:
        return "detach"
    if cell.formula is not None and stored:
        previous = pool.formulaFor(record.references[formulaKeySlot])
        return "replace" if cell.formula != previous else "none"
    return "none"


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


def rewriteCellRecords(
    records: CellRecordList,
    added: list[tuple[int, int]],
    removed: list[tuple[int, int]],
) -> None:
    """Add and drop entries in one register of formula-bearing cells."""
    dropping = set(removed)
    kept = [
        record for record in records
        if (record.row, record.column) not in dropping
    ]
    present = {(record.row, record.column) for record in kept}
    del records[:]
    for record in kept:
        records.add().CopyFrom(record)
    for row, column in added:
        if (row, column) in present:
            continue
        fresh = records.add()
        fresh.column = column
        fresh.row = row
        # An empty edge set, which is what every entry in the corpus carries.
        fresh.expanded_edges.SetInParent()


def registerFormulaCells(
    index: ArchiveIndex,
    owner: TableOwner,
    added: list[tuple[int, int]],
    removed: list[tuple[int, int]],
) -> dict[int, bytes]:
    """Tell the calculation engine which cells hold formulas now, and report a change.

    **Not optional, and its absence fails silently.** Setting the record flag and
    pooling the archive leaves a formula that is never evaluated, and the register is
    stored TWICE so both copies have to agree. Updating only `cell_dependencies`
    shows the formula in Numbers' formula bar while the cell keeps its old value.
    See findings-02-formulas.md, which records all three attempts.

    Coordinates count from zero here. Returns the archives that changed, since the
    tiles are not part of the owner entry.
    """
    if not added and not removed:
        return {}
    rewriteCellRecords(owner.dependencies.cell_dependencies.cell_record,
                       added, removed)
    changed: dict[int, bytes] = {}
    for reference in owner.dependencies.tiled_cell_dependencies.cell_record_tiles:
        tile = index.resolve(reference, tsce.CellRecordTileArchive)
        band = range(
            tile.tile_column_begin,
            tile.tile_column_begin + dependencyTileColumns,
        )
        inTile = [
            (row, column) for row, column in added
            if column in band and row >= tile.tile_row_begin
        ]
        outTile = [
            (row, column) for row, column in removed
            if column in band and row >= tile.tile_row_begin
        ]
        if not inTile and not outTile:
            continue
        rewriteCellRecords(tile.cell_records, inTile, outTile)
        changed[reference.identifier] = tile.SerializeToString()

    placed = {
        (row, column)
        for reference in owner.dependencies.tiled_cell_dependencies.cell_record_tiles
        for row, column in added
        if column
        in range(
            index.resolve(reference, tsce.CellRecordTileArchive).tile_column_begin,
            index.resolve(reference, tsce.CellRecordTileArchive).tile_column_begin
            + dependencyTileColumns,
        )
    }
    missing = sorted(set(added) - placed)
    if missing:
        raise WriteError(
            f"No dependency tile covers {missing}, so a formula written there would "
            "be registered in one of the engine's two registers and not the other. "
            "Creating a tile has never been measured."
        )
    changed[owner.identifier] = owner.dependencies.SerializeToString()
    return changed


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
        pool.release(record.references[formulaKeySlot])
        return detachFormulaKey(raw, record)
    assert cell.formula is not None
    return patchFormulaKey(
        raw,
        record,
        pool.keyFor(cell.formula, record.references[formulaKeySlot]),
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
                    rowInfo.cell_offsets, rowInfo.cell_storage_buffer, wide
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

    if pool is not None and pool.touched:
        poolId = store.formula_table.identifier
        owners[poolId].messageReplace(
            poolId, 0, pool.dataList.SerializeToString()
        )
    return TableEdits(written, formulaAdded, formulaRemoved)


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


@dataclass(frozen=True, slots=True)
class TableOwner:
    """One table's calculation-engine entry, and the archive holding it.

    The identifier travels with the message because registering a formula cell
    changes that archive and it has to be written back. Looking it up a second
    time would mean walking the dependency tracker again to find what this walk
    already had in hand.
    """

    identifier: int
    dependencies: tsce.FormulaOwnerDependenciesArchive


def ownerEntryFor(
    entries: dict[int, TableOwner],
    identifier: int,
    name: str,
) -> TableOwner:
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
) -> dict[int, TableOwner]:
    """Return each table's dependency entry, keyed by its `TST.TableInfoArchive`.

    Read the long way round because there is no short one: a table records neither
    its internal owner id nor its owner uid. Both live here, on the entry whose
    `owner_kind` is 1 and whose `formula_owner` points back at the table. Measured
    2026-09-02, see findings-02-formulas.md and findings-03-structure.md.
    """
    entries: dict[int, TableOwner] = {}
    for reference in engine.dependency_tracker.formula_owner_dependencies:
        dependencies = index.resolve(reference, tsce.FormulaOwnerDependenciesArchive)
        if dependencies.owner_kind != tableOwnerKind:
            continue
        if not dependencies.HasField("formula_owner"):
            continue
        entries[dependencies.formula_owner.identifier] = TableOwner(
            identifier=reference.identifier, dependencies=dependencies
        )
    return entries


def tableOwnerIds(
    index: ArchiveIndex, engine: tsce.CalculationEngineArchive
) -> dict[int, int]:
    """Return each table's internal owner id, keyed by its own archive."""
    return {
        identifier: owner.dependencies.internal_formula_owner_id
        for identifier, owner in tableOwnerEntries(index, engine).items()
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


def requestRecalculation(
    index: ArchiveIndex,
    owners: dict[int, IWAFile],
    written: dict[int, list[tuple[int, int]]],
) -> int:
    """Tell Numbers which cells moved, so it recalculates whatever depends on them.

    **A formula caches its result and opening the document does not refresh it**, so a
    save without this displays arithmetic that disagrees with its own operands, with
    no prompt. Naming the edited cells is enough: Numbers walks its own graph from
    there, transitively and across sheets, which is why this library never evaluates.
    Measured 2026-09-02 both broadly and minimally, in findings-02-formulas.md.
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

            # A cell a merge swallowed has NO record in the file, so its record is
            # dropped rather than left behind as an empty one Numbers never wrote.
            swallowed = frozenset(
                (reference.row - originOffset, reference.col - originOffset)
                for merge in table.mergeRanges
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

#!/usr/bin/env python3
"""\
One formula back into its archive, and the pool a table shares between cells.

The mirror of `pybers.readformula`, split from the writer for the same reason:
node arrays have nothing to do with tiles or with staging a package.

**A node is patched, never rebuilt.** The node message carries 45 fields and this
model gives meaning to 16, so a node built from what the model holds would
silently drop whatever else it was carrying. Starting from the bytes as read is
what carries a formula this library does not understand through a rewrite intact.

**Numbers points every cell a formula was dragged into at ONE archive.** Changing
one of them therefore means adding an entry rather than overwriting the shared
one, which is the write-path half of the contract the frozen model keeps on the
read path.

UPDATES
2026-09-08  Split out of `pybers.writer` for #45, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

import struct
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from ._generated import TSCEArchives_pb2 as tsce
from ._generated import TSTArchives_pb2 as tst
from ._persistence.cells import (
    CellRecord,
    carriesFormula,
    decodeCellValue,
    formulaFlagBit,
    formulaFlagOffset,
    formulaKeySlot,
    valueOffset,
)
from ._persistence.decimal128 import Decimal128
from ._persistence.index import ArchiveIndex, originOffset
from .errors import WriteError
from .model import (
    Cell,
    Coordinate,
    Formula,
    FormulaFunctionCall,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaUnknownCall,
    Span,
)
from .model.formula import (
    FormulaBinding,
    FormulaLambda,
    FormulaVariable,
    brokenColumnSentinel,
    brokenRowSentinel,
)
from .readformula import ColonTractAxis, decimalHalfFormat, readFormulaTable

# Every trailing reference in a cell record is a little-endian uint32.
referenceWidth: int = 4

# Byte 0 of every cell record in the corpus. A created record carries it too.
storageVersion: int = 5

# A table identity is a 128-bit value the formula spells as four 32-bit words, so
# the model's hexadecimal has to be cut back into them.
uuidHexLength: int = 32
wordHexLength: int = 8

# The type a formula cell takes when no result is stored, which is what Numbers
# writes for a formula it could not compute and what a formula pybers just wrote
# genuinely is until Numbers recalculates.
formulaPendingType: int = 8

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
    owns is what carries an unrecognized node through a rewritten formula intact.
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
    elif isinstance(content, FormulaBinding):
        archive.AST_let_identifier = content.name
        archive.AST_symbol = content.symbol
        archive.AST_let_is_continuation = content.continuation
    elif isinstance(content, FormulaVariable):
        archive.AST_symbol = content.symbol
    elif isinstance(content, FormulaLambda):
        # Cleared first, because a lambda read with two parameters and rewritten
        # with one would otherwise keep the name it no longer binds.
        archive.AST_lambda_idents.ClearField("AST_identifier_string")
        archive.AST_lambda_idents.AST_identifier_string.extend(content.names)
        archive.AST_lambda_idents.AST_first_symbol = content.firstSymbol
    return archive


def encodeTableIdentity(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, identity: str | None
) -> None:
    """Write the table a reference reaches into, or clear the field when it is local.

    Cleared rather than left alone, because a node read as cross-table and rewritten
    as local would keep pointing at the other table while the model said otherwise.
    A node this library built from text carries no bytes to inherit the field from,
    which is why writing it cannot be left to the patch.
    """
    if not identity:
        archive.ClearField("AST_cross_table_reference_extra_info")
        return
    if len(identity) != uuidHexLength:
        raise WriteError(
            f"A table identity is {uuidHexLength} hexadecimal characters and "
            f"{identity!r} is {len(identity)}."
        )
    words = archive.AST_cross_table_reference_extra_info.table_id
    # Four 32-bit words in the order `readOwnerUuid` spelled them, which is the
    # low half of the owner uid first. See findings-08-formula-text.md.
    (words.uuid_w0, words.uuid_w1, words.uuid_w2, words.uuid_w3) = (
        int(identity[start:start + wordHexLength], 16)
        for start in range(0, uuidHexLength, wordHexLength)
    )


def encodeFormulaReference(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, reference: FormulaReference
) -> None:
    """Write a single-cell reference, restoring the sentinels for a broken one.

    A broken reference is written back exactly as it was found rather than
    repaired into a real cell. Numbers records `#REF` as coordinates deliberately
    pointing nowhere, and quietly turning that into a working reference would
    change what the document says.
    """
    encodeTableIdentity(archive, reference.tableId)
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
    encodeTableIdentity(archive, extent.tableId)
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
    return valueOffset + width + formulaKeySlot(record) * referenceWidth


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
    the key, placed at the slot `formulaKeySlot` names rather than always first.
    Byte 8 never moves, being fixed by the type and by what else the cell carries.

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
    slot = formulaKeySlot(record)
    stored = carriesFormula(record) and len(record.references) > slot
    if cell.formula is not None and not stored:
        return "attach"
    if cell.formula is None and stored:
        return "detach"
    if cell.formula is not None and stored:
        previous = pool.formulaFor(record.references[slot])
        return "replace" if cell.formula != previous else "none"
    return "none"


__all__ = ["FormulaPool", "encodeFormula", "formulaEdit", "formulaPoolFor"]

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
2026-10-13  A node's content is written by matching it, checked exhaustive by
            mypy, for PYB-139.
2026-10-13  A boolean literal, and a range axis reaching every line, for PYB-139.
2026-09-29  A copied record claims the formula it names, for PYB-118.
2026-09-21  A broken reference's sentinels and sticky bits carry each axis's
            lock, the end bits never set, for PYB-17.
2026-09-18  A broken reference writes the lines it lost, for PYB-17.
2026-09-11  A bracket is written back as the list node it was read from,
            for #67.
2026-09-08  Split out of `pybers.document._write` for #45, unchanged.
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
from typing import assert_never, cast

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSTArchives_pb2 as tst
from .._persistence.cells import (
    CellRecord,
    carriesFormula,
    decodeCellValue,
    findFormulaKeySlot,
    formulaFlagBit,
    formulaFlagOffset,
    referenceWidth,
    valueOffset,
)
from .._persistence.decimal128 import Decimal128
from .._persistence.index import ArchiveIndex, assignUuid
from ..addressing.reference import originOffset
from ..errors import WriteError
from ._read import ColonTractAxis, decimalHalfFormat, readFormulaTable
from .nodes import (
    Coordinate,
    Formula,
    FormulaBinding,
    FormulaFunctionCall,
    FormulaGroup,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaReferenceLoss,
    FormulaUnknownCall,
    FormulaVariable,
    Span,
    brokenColumnSentinel,
    brokenRowSentinel,
    unboundedRangeColumn,
    unboundedRangeRow,
)

# Byte 0 of every cell record in the documents. A created record carries it too.
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
    `assert_never` makes mypy name any content type the model gains and this skips.
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
    match content:
        case bool():
            archive.AST_boolean_node_boolean = content
        case Decimal():
            # decimal128 and the float64 copy beside it, because Numbers writes both
            # and a reader of either has to find the same number.
            low, high = struct.unpack(
                decimalHalfFormat, Decimal128(content).asBytes()
            )
            archive.AST_number_node_decimal_low = low
            archive.AST_number_node_decimal_high = high
            archive.AST_number_node_number = float(content)
        case str():
            archive.AST_string_node_string = content
        case FormulaFunctionCall():
            archive.AST_function_node_index = content.index
            archive.AST_function_node_numArgs = content.argumentCount
        case FormulaGroup():
            archive.AST_list_node_numArgs = content.argumentCount
        case FormulaUnknownCall():
            archive.AST_unknown_function_node_string = content.name
            archive.AST_unknown_function_node_numArgs = content.argumentCount
        case FormulaReference():
            encodeFormulaReference(archive, content)
        case FormulaRange():
            encodeFormulaRange(archive, content)
        case FormulaBinding():
            archive.AST_let_identifier = content.name
            archive.AST_symbol = content.symbol
            archive.AST_let_is_continuation = content.continuation
        case FormulaVariable():
            archive.AST_symbol = content.symbol
        case FormulaLambda():
            # Cleared first, because a lambda read with two parameters and
            # rewritten with one would otherwise keep the name it no longer binds.
            archive.AST_lambda_idents.ClearField("AST_identifier_string")
            archive.AST_lambda_idents.AST_identifier_string.extend(content.names)
            archive.AST_lambda_idents.AST_first_symbol = content.firstSymbol
        case None:
            pass
        case _:
            assert_never(content)
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
        locks = reference.loss or FormulaReferenceLoss()
        archive.AST_column.column = brokenColumnSentinel
        archive.AST_column.absolute = locks.columnsAbsolute
        archive.AST_row.row = brokenRowSentinel
        archive.AST_row.absolute = locks.rowsAbsolute
        if reference.loss is not None:
            encodeReferenceLoss(archive, reference.loss)
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


def encodeReferenceLoss(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, loss: FormulaReferenceLoss
) -> None:
    """Write the lines a broken reference lost, as the one tract Numbers writes.

    The node's sticky bits mark the beginning of a locked axis only, never the
    end, and the tract's stay clear: measured on `$A$8` and `A8` broken in
    `56h-row-8-deleted`. A highlighting rule repeats the lock in the tract, which
    the rule's own writer adds.
    """
    bits = archive.AST_sticky_bits
    bits.begin_column_is_absolute = loss.columnsAbsolute
    bits.end_column_is_absolute = False
    bits.begin_row_is_absolute = loss.rowsAbsolute
    bits.end_row_is_absolute = False
    clear = archive.AST_tract_list.sticky_bits
    clear.begin_column_is_absolute = False
    clear.end_column_is_absolute = False
    clear.begin_row_is_absolute = False
    clear.end_row_is_absolute = False
    archive.AST_tract_list.ClearField("tract")
    tract = archive.AST_tract_list.tract.add()
    for value in loss.columns:
        assignUuid(tract.columnUids.uid.add(), value)
    for value in loss.rows:
        assignUuid(tract.rowUids.uid.add(), value)
    tract.columnUids.SetInParent()
    tract.rowUids.SetInParent()
    tract.is_range_ref = loss.range
    tract.purpose = tsce.ASTNodeArrayArchive.UIDS_INCLUDED
    tract.preserve_rectangular = True


def encodeFormulaRange(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, extent: FormulaRange
) -> None:
    """Write one range tract into the field variant its anchoring belongs in.

    An axis reaching every line is written as Numbers writes it: absolute, holding
    the unbounded value, with no end.

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
    if extent.columns is None:
        tract.absolute_column.add().range_begin = unboundedRangeColumn
    else:
        field = (
            tract.absolute_column if extent.columns.absolute
            else tract.relative_column
        )
        encodeSpan(field.add(), extent.columns)
    if extent.rows is None:
        tract.absolute_row.add().range_begin = unboundedRangeRow
    else:
        field = (
            tract.absolute_row if extent.rows.absolute else tract.relative_row
        )
        encodeSpan(field.add(), extent.rows)
    encodeStickyBits(archive, extent)


def encodeStickyBits(
    archive: tsce.ASTNodeArrayArchive.ASTNodeArchive, extent: FormulaRange
) -> None:
    """Restate a range's anchoring beside its tract, which is what Numbers reads.

    **A range records its anchoring twice and Numbers believes this copy.** Every
    one of the 9 ranges in the documents carries these bits, and a range pybers built
    from text carried none until 2026-09-09, so `SUM($A$1:$A$5)` was written with
    an absolute tract and displayed by Numbers as `SUM(A1:A5)`. Both ends of an
    axis share one flag because `Span` cannot express a range locked at one end.

    An axis the range leaves unbounded is written as not absolute, though its tract
    holds it absolute, as Numbers wrote every such axis in
    `71-whole-axis-ranges-and-booleans`.
    """
    columns = extent.columns.absolute if extent.columns is not None else False
    rows = extent.rows.absolute if extent.rows is not None else False
    bits = archive.AST_sticky_bits
    bits.begin_column_is_absolute = columns
    bits.end_column_is_absolute = columns
    bits.begin_row_is_absolute = rows
    bits.end_row_is_absolute = rows


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

    def claim(self, key: int) -> None:
        """Add one cell's claim on a stored formula, as a copied record makes."""
        entry = self.entryFor(key)
        if entry is None:
            raise WriteError(
                f"A copied record names formula {key}, which is not stored."
            )
        self.touched = True
        entry.refcount += 1

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


def findFormulaKeyOffset(record: CellRecord) -> int:
    """Return where a record keeps its formula key.

    Computed from the value's own width rather than from a constant, because the
    key sits immediately after the value and a date, a boolean and a number are
    three different widths. An error cell consumes no value at all, which is why
    the same arithmetic finds its key at byte 12.
    """
    _, width = decodeCellValue(record.typeByte, record.raw[valueOffset:])
    return valueOffset + width + findFormulaKeySlot(record) * referenceWidth


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

    Measured in every document 2026-09-04: a formula-backed record is the plain
    record for the same result type with byte 9 bit `0x02` set and ONE more trailing
    reference, the key, placed at the slot `findFormulaKeySlot` names rather than always
    first.
    Byte 8 never moves, being fixed by the type and by what else the cell carries.

    Derived from matched pairs rather than synthesized, because the rest of byte 9
    encodes things this library does not model. The cached value stays and becomes
    the placeholder, which Numbers repairs while recalculating.
    """
    at = findFormulaKeyOffset(record)
    if len(raw) < at:
        raise WriteError(
            f"Column {record.column} is {len(raw)} bytes and its formula key would "
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
    at = findFormulaKeyOffset(record)
    if len(raw) < at + referenceWidth:
        raise WriteError(
            f"Column {record.column} is marked as carrying a formula, but its record "
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
    at = findFormulaKeyOffset(record)
    if len(raw) < at + referenceWidth:
        raise WriteError(
            f"Column {record.column} is marked as carrying a formula, but its record "
            f"is {len(raw)} bytes and the key would sit at {at}."
        )
    return raw[:at] + key.to_bytes(referenceWidth, "little") + raw[at + referenceWidth:]


def readFormulaPool(
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


def classifyFormulaEdit(
    formula: Formula | None, record: CellRecord, pool: FormulaPool | None
) -> str:
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
    slot = findFormulaKeySlot(record)
    stored = carriesFormula(record) and len(record.references) > slot
    if formula is not None and not stored:
        return "attach"
    if formula is None and stored:
        return "detach"
    if formula is not None and stored:
        previous = pool.formulaFor(record.references[slot])
        return "replace" if formula != previous else "none"
    return "none"


__all__ = ["FormulaPool", "encodeFormula", "classifyFormulaEdit", "readFormulaPool"]

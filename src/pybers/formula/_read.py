#!/usr/bin/env python3
"""\
One stored formula out of its archive and into the model, node for node.

Split from `pybers.reader` because it is the whole of one feature and none of the
rest: a formula's node array has nothing to do with tiles, rows or pooled strings.

Two traps, both of which answer with a plausible wrong reference rather than an
error, which is why each is handled here and not left to a caller:

- **Anchoring is recorded in two different places depending on the node.** A range
  carries the field variant its axis sits in and `ASTStickyBits` beside it. A
  single-cell reference carries the flag on the coordinate and no bits at all, 0
  of 21 in the corpus, so reading the bits reports every such reference unlocked.
- **A broken reference is coordinates pointing nowhere on purpose.** Read as
  ordinary numbers they name a cell far outside the table and raise nothing.

UPDATES
2026-09-08  Split out of `pybers.reader` for #45, unchanged.
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
from typing import cast

from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence import carriesFormula
from .._persistence.cells import CellRecord, formulaKeySlot
from .._persistence.decimal128 import Decimal128
from .._persistence.index import (
    ArchiveIndex,
    formulaListType,
    originOffset,
    readDataList,
)
from .nodes import (
    Coordinate,
    Formula,
    FormulaBinding,
    FormulaFunctionCall,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaUnknownCall,
    FormulaVariable,
    NodeContent,
    Span,
    brokenColumnSentinel,
    brokenReferenceNodeType,
    brokenRowSentinel,
    functionNodeType,
    lambdaNodeType,
    letBindNodeType,
    numberNodeType,
    rangeNodeType,
    referenceNodeType,
    stringNodeType,
    unknownFunctionNodeType,
    variableNodeType,
)

# A number literal carries decimal128 as two 64-bit halves rather than as bytes.
decimalHalfFormat: str = "<QQ"

# The GENERATED message for one axis of a colon tract, not a model type: the
# model's own is `Span`. Apple declares the relative and absolute forms as two
# separate messages of identical shape, and which one an axis sits in IS its
# anchoring, so a decoder takes either and is told which it was handed.
type ColonTractAxis = (
    tsce.ASTNodeArrayArchive.ASTColonTractArchive.ASTColonTractRelativeRangeArchive
    | tsce.ASTNodeArrayArchive.ASTColonTractArchive.ASTColonTractAbsoluteRangeArchive
)


def readUuid(archive: tsp.CFUUIDArchive) -> str:
    """Return a `TSP.CFUUIDArchive` as a canonical hexadecimal identity.

    A table is named by identity rather than by name or position, which is why
    renaming a table cannot break a formula pointing into it. The archive spells
    that identity either as raw bytes or as four 32-bit words, so both are read
    and only the string form travels into the model.
    """
    if archive.HasField("uuid_bytes"):
        return archive.uuid_bytes.hex()
    words = (archive.uuid_w0, archive.uuid_w1, archive.uuid_w2, archive.uuid_w3)
    return "".join(f"{word:08x}" for word in words)


def readCoordinate(value: int, absolute: bool) -> Coordinate:
    """Return one axis of a reference, converting only when it is a real line.

    A relative axis is a signed distance and means the same in either counting
    system, so it passes through untouched. An absolute axis is a stored
    coordinate counting from zero and becomes the model's counting from one. This
    is the one place that distinction is applied, and applying it to an offset
    would shift every relative reference by one silently.
    """
    return Coordinate(
        value + originOffset if absolute else value, absolute=absolute
    )


def readSpan(entry: ColonTractAxis, absolute: bool) -> Span:
    """Return one axis of a range tract, in the model's counting.

    `range_end` is omitted for a span of one line rather than repeating the
    beginning, so its absence is preserved rather than filled in.
    """
    begin = entry.range_begin
    end = entry.range_end if entry.HasField("range_end") else None
    shift = originOffset if absolute else 0
    return Span(
        begin=begin + shift,
        end=None if end is None else end + shift,
        absolute=absolute,
    )


def readFormulaReference(
    node: tsce.ASTNodeArrayArchive.ASTNodeArchive,
) -> FormulaReference:
    """Return a single-cell reference, recognizing the sentinels that mean broken.

    An axis that is absent stays absent, because unboundedness is expressed that
    way rather than by a flag: `SUM(A)` stores a column and no row at all.
    """
    column = (
        readCoordinate(node.AST_column.column, node.AST_column.absolute)
        if node.HasField("AST_column")
        else None
    )
    row = (
        readCoordinate(node.AST_row.row, node.AST_row.absolute)
        if node.HasField("AST_row")
        else None
    )
    tableId = (
        readUuid(node.AST_cross_table_reference_extra_info.table_id)
        if node.HasField("AST_cross_table_reference_extra_info")
        else None
    )
    # Node type 46 is the archive's own statement that this reference points
    # nowhere, and the coordinates beside it are sentinels rather than a cell.
    # They are checked as well, because reading them as real coordinates names a
    # cell far outside any table and raises nothing.
    broken = node.AST_node_type == brokenReferenceNodeType or (
        node.HasField("AST_column")
        and node.HasField("AST_row")
        and node.AST_column.column == brokenColumnSentinel
        and node.AST_row.row == brokenRowSentinel
    )
    if broken:
        return FormulaReference(tableId=tableId, broken=True)
    return FormulaReference(column=column, row=row, tableId=tableId)


def readFormulaRange(
    node: tsce.ASTNodeArrayArchive.ASTNodeArchive,
) -> FormulaRange:
    """Return one range tract, taking each axis from whichever field holds it.

    Anchoring lives in the field variant an axis sits in, and `ASTStickyBits`
    records the same fact beside it. The variant is read and the bits are not,
    because a single-cell reference carries no bits at all and one rule covering
    both is what keeps the two node kinds from drifting apart.
    """
    tract = node.AST_colon_tract
    columns = (
        readSpan(tract.relative_column[0], absolute=False)
        if tract.relative_column
        else readSpan(tract.absolute_column[0], absolute=True)
        if tract.absolute_column
        else None
    )
    rows = (
        readSpan(tract.relative_row[0], absolute=False)
        if tract.relative_row
        else readSpan(tract.absolute_row[0], absolute=True)
        if tract.absolute_row
        else None
    )
    tableId = (
        readUuid(node.AST_cross_table_reference_extra_info.table_id)
        if node.HasField("AST_cross_table_reference_extra_info")
        else None
    )
    return FormulaRange(columns=columns, rows=rows, tableId=tableId)


def readFormulaNode(
    node: tsce.ASTNodeArrayArchive.ASTNodeArchive,
) -> FormulaNode:
    """Return one node, giving meaning only to the types the model claims.

    Everything else keeps its type and its bytes and nothing more. The node
    message carries 45 fields and the corpus uses 16, so interpreting the rest
    would be describing the schema rather than the documents, and a formula is
    shared state that other cells depend on.
    """
    content: object = None
    kind = node.AST_node_type
    if kind == numberNodeType:
        # decimal128, never the float64 copy beside it. The float is a
        # convenience Apple stores as well, and reading it would introduce binary
        # rounding error into a document that never had any.
        packed = struct.pack(
            decimalHalfFormat,
            node.AST_number_node_decimal_low,
            node.AST_number_node_decimal_high,
        )
        content = Decimal128.fromBytes(packed).value
    elif kind == stringNodeType:
        content = node.AST_string_node_string
    elif kind == functionNodeType:
        content = FormulaFunctionCall(
            index=node.AST_function_node_index,
            argumentCount=node.AST_function_node_numArgs,
        )
    elif kind == unknownFunctionNodeType:
        content = FormulaUnknownCall(
            name=node.AST_unknown_function_node_string,
            argumentCount=node.AST_unknown_function_node_numArgs,
        )
    elif kind in (referenceNodeType, brokenReferenceNodeType):
        content = readFormulaReference(node)
    elif kind == rangeNodeType:
        content = readFormulaRange(node)
    elif kind == letBindNodeType:
        content = FormulaBinding(
            name=node.AST_let_identifier,
            symbol=node.AST_symbol,
            continuation=node.AST_let_is_continuation,
        )
    elif kind == variableNodeType:
        content = FormulaVariable(symbol=node.AST_symbol)
    elif kind == lambdaNodeType:
        content = FormulaLambda(
            names=tuple(node.AST_lambda_idents.AST_identifier_string),
            firstSymbol=node.AST_lambda_idents.AST_first_symbol,
        )
    return FormulaNode(
        nodeType=kind,
        content=cast(NodeContent, content),
        raw=node.SerializeToString(),
    )


def readFormula(archive: tsce.FormulaArchive) -> Formula:
    """Return one stored formula as its postfix node array."""
    return Formula(
        nodes=tuple(
            readFormulaNode(node) for node in archive.AST_node_array.AST_node
        )
    )


def readFormulaTable(
    index: ArchiveIndex, dataStore: tst.DataStore
) -> dict[int, Formula]:
    """Return the table's pooled formulas, keyed as the cell records address them.

    Pooled exactly like strings: one archive serves every cell a formula was
    dragged into, which is only possible because references are offsets from the
    cell holding them.
    """
    if not dataStore.formula_table.identifier:
        return {}
    entries = readDataList(index, dataStore.formula_table, formulaListType)
    return {
        key: readFormula(entry.formula)
        for key, entry in entries.items()
        if entry.HasField("formula")
    }


def resolveFormula(
    record: CellRecord, formulas: dict[int, Formula]
) -> Formula | None:
    """Return the formula behind a cell, or None when the cell has none.

    A formula that is marked but absent from the table's list is returned as None
    rather than raised on. The flag and the list are two separate records of the
    same fact, and a document Numbers opens happily is not one this library should
    refuse to read.
    """
    if not carriesFormula(record):
        return None
    slot = formulaKeySlot(record)
    if len(record.references) <= slot:
        return None
    return formulas.get(record.references[slot])


__all__ = ["readFormula", "readFormulaTable", "resolveFormula"]

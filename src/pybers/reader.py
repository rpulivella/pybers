#!/usr/bin/env python3
"""\
Turn a `.numbers` package into the object model: the read half of the binding.

`pybers.numbersfile` reads the container and decodes cell records; `pybers.model`
holds the dataclasses. Neither knows about the other, and this module is what
joins them. It lives outside `pybers.model` on purpose, so that importing the
model never drags in the persistence layer. See CLAUDE.md, "Document is the
handle".

Three traps the fixtures established, all of which produce a plausible wrong
answer rather than an error, and all of which are handled here rather than left
to a caller:

- **Order comes from lists, never from archive order.** Sheets come from
  `DocumentArchive.sheets`, drawables from `SheetArchive.drawable_infos`, and
  tiles from `TileStorage.tiles`. Tile archive identifiers are demonstrably not
  in row order, so iterating archives as found scrambles a large table silently.
- **`tile_row_index` is local to its tile.** A document row is
  `tileid * tile_size + tile_row_index`. Reading it as a document row gives eight
  different rows on an eight-tile table and raises nothing.
- **Strings are pooled.** A text cell holds a key into the table's STRING data
  list, not the text, so a decode that stops at the record returns an integer
  that looks like a perfectly good number.

UPDATES
2026-08-31  Written for #1: document, sheets, tables and cell values.
2026-09-01  The package read here travels with the document, for #2.
2026-09-03  Formulas, for #41. The key slot and the sticky-bits rule were
            measured against the corpus, not read off the schema.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/31"

import struct
from pathlib import Path
from typing import cast

from google.protobuf.message import Message

from ._generated import TNArchives_pb2 as tn
from ._generated import TSCEArchives_pb2 as tsce
from ._generated import TSPMessages_pb2 as tsp
from ._generated import TSTArchives_pb2 as tst
from ._generated import TSWPArchives_pb2 as tswp
from .model import (
    CellRange,
    CellReference,
    CellValue,
    Coordinate,
    Document,
    Formula,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FunctionCall,
    MergeRange,
    Sheet,
    Span,
    Table,
    UnknownFunction,
)
from .model.formula import (
    NodeContent,
    brokenColumnSentinel,
    brokenReferenceNodeType,
    brokenRowSentinel,
    functionNodeType,
    numberNodeType,
    rangeNodeType,
    referenceNodeType,
    stringNodeType,
    unknownFunctionNodeType,
)
from .numbersfile import Archive, NumbersPackage, carriesFormula, decodeRow, readPackage
from .numbersfile.cells import CellRecord
from .numbersfile.decimal128 import Decimal128
from .numbersfile.types import archiveTypeId, parseArchive

# The stored format counts rows and columns from zero. The model counts from
# one, because that is what Numbers shows and what a caller means by "row 1". The
# two systems meet HERE and nowhere else: a stored coordinate never reaches the
# model, and a model coordinate never reaches a decoder. A design keeping both in
# one object is how a reader comes to be off by one in only some places.
originOffset: int = 1

# The registry identifiers this module navigates by. Named rather than written as
# literals at the point of use, because a bare 6000 in a conditional says nothing.
documentTypeId: int = 1
tableInfoTypeId: int = 6000

# Cell record type bytes whose decoded value is a key into a pooled data list
# rather than the value itself. See `pybers.numbersfile.cells`.
stringKeyType: int = 3
richTextKeyType: int = 9

# A cell whose formula failed. It holds no value at all, so byte 12 is where its
# formula key sits rather than a result, and `decodeCellValue` consuming nothing
# for this type is what puts that key in the usual slot.
formulaErrorType: int = 8

# `TST.TableDataList.ListType` values, restated so that reading this file does not
# require the generated enum in hand.
stringListType: int = 1
formulaListType: int = 3
richTextListType: int = 8

# A formula-backed cell names its formula in the FIRST of its trailing
# references. Established on 2026-09-03 by reproducing declared refcounts: in all
# nine tables in the corpus that declare formulas, counting the cells that name
# each key through slot 0 equals the refcount the table declares, and no other
# slot does so in any table. Value matching alone could not settle it, because
# formula keys and style indices are both small integers and several slots
# coincide by chance. An error cell consumes no value, so byte 12 is at once its
# value slot and this slot, which is why one rule covers both.
formulaKeySlot: int = 0

# A number literal carries decimal128 as two 64-bit halves rather than as bytes.
decimalHalfFormat: str = "<QQ"


class ReadError(RuntimeError):
    """A `.numbers` document whose structure could not be walked."""


class ArchiveIndex:
    """Every archive in a package, addressable by the identifier references use.

    A `TSP.Reference` carries only an identifier, with no hint of which member
    holds the target, so resolving one means having the whole package indexed
    first. Built once per read.
    """

    def __init__(self, package: NumbersPackage) -> None:
        """Index every archive in the package by identifier.

        Built eagerly and in full, because a reference gives no hint which member
        holds its target, so a lazy index would have to scan every member on the
        first miss anyway.
        """
        self.byIdentifier: dict[int, Archive] = {}
        for iwaFile in package.iwaFiles:
            for archive in iwaFile.archives:
                self.byIdentifier[archive.identifier] = archive

    def archive(self, identifier: int) -> Archive:
        """Return the archive with this identifier, or raise naming it."""
        found = self.byIdentifier.get(identifier)
        if found is None:
            raise ReadError(
                f"Reference to archive {identifier}, which is not in this document."
            )
        return found

    # Every resolve names the archive class it expects, so the expectation is
    # checked rather than assumed, and Message bounds it because only a generated
    # class can be the target of a reference.
    def resolve[ArchiveT: Message](
        self, reference: tsp.Reference, expected: type[ArchiveT]
    ) -> ArchiveT:
        """Parse the archive a `TSP.Reference` points at, as the class named.

        The expected class is required rather than inferred, and it is checked.
        A reference is a bare identifier with no type on it, so following the
        wrong field yields a real archive of the wrong kind, and reading a table
        model as a tile would produce a plausible empty table rather than an
        error. Naming the expectation turns that into a stop.
        """
        message = parseArchive(self.archive(reference.identifier))
        if not isinstance(message, expected):
            raise ReadError(
                f"Archive {reference.identifier} is a "
                f"{type(message).DESCRIPTOR.full_name}, but a "
                f"{expected.DESCRIPTOR.full_name} was expected here."
            )
        return message

    def typeOf(self, reference: tsp.Reference) -> int:
        """Return a reference target's type without parsing it.

        Needed for the drawable list, which mixes tables with shapes, images and
        text boxes. Those have their own tickets and are not in the registry yet,
        so they have to be recognized and skipped rather than parsed and refused.
        """
        return archiveTypeId(self.archive(reference.identifier))


def findRoot(index: ArchiveIndex) -> tn.DocumentArchive:
    """Return the document's root `TN.DocumentArchive`.

    Found by type rather than by position or by member name. Exactly one archive
    in a document carries this type, verified across the whole fixture corpus, so
    a count other than one means the file is not what this library thinks it is
    and is worth stopping on.
    """
    roots = [
        archive for archive in index.byIdentifier.values()
        if archiveTypeId(archive) == documentTypeId
    ]
    if len(roots) != 1:
        raise ReadError(
            f"Expected exactly one TN.DocumentArchive, found {len(roots)}."
        )
    root = parseArchive(roots[0])
    if not isinstance(root, tn.DocumentArchive):
        raise ReadError(f"The root archive parsed as {type(root).__name__}.")
    return root


def readDataList(
    index: ArchiveIndex, reference: tsp.Reference, listType: int
) -> dict[int, tst.TableDataList.ListEntry]:
    """Return one pooled data list as key to entry.

    The entry rather than its payload, because the twelve list types keep theirs
    in different fields and only the caller knows which one it wants.
    """
    dataList = index.resolve(reference, tst.TableDataList)
    if dataList.listType != listType:
        raise ReadError(
            f"Expected data list type {listType}, got {dataList.listType}."
        )
    return {entry.key: entry for entry in dataList.entries}


def readStringTable(index: ArchiveIndex, dataStore: tst.DataStore) -> dict[int, str]:
    """Return the table's pooled strings, keyed as the cell records address them."""
    if not dataStore.HasField("stringTable"):
        return {}
    entries = readDataList(index, dataStore.stringTable, stringListType)
    return {key: entry.string for key, entry in entries.items()}


def readRichTextTable(index: ArchiveIndex, dataStore: tst.DataStore) -> dict[int, str]:
    """Return the plain text of each rich-text payload, keyed as cells address it.

    A rich-text cell is not in this ticket's acceptance criteria, but every cell
    in every fixture has to read without failing, and a payload key returned raw
    would be indistinguishable from a number. The text is taken and the run tables
    are left alone; those are `TSWP.StorageArchive`'s twenty-one parallel tables,
    indexed in UTF-16 code units, and they have their own ticket.
    """
    if not dataStore.HasField("rich_text_table"):
        return {}
    entries = readDataList(index, dataStore.rich_text_table, richTextListType)
    text: dict[int, str] = {}
    for key, entry in entries.items():
        payload = index.resolve(entry.rich_text_payload, tst.RichTextPayloadArchive)
        storage = index.resolve(payload.storage, tswp.StorageArchive)
        text[key] = "".join(storage.text)
    return text


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


def readSpan(entry: object, absolute: bool) -> Span:
    """Return one axis of a range tract, in the model's counting.

    `range_end` is omitted for a span of one line rather than repeating the
    beginning, so its absence is preserved rather than filled in.
    """
    begin = entry.range_begin  # type: ignore[attr-defined]
    end = (
        entry.range_end  # type: ignore[attr-defined]
        if entry.HasField("range_end")  # type: ignore[attr-defined]
        else None
    )
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
        content = FunctionCall(
            index=node.AST_function_node_index,
            argumentCount=node.AST_function_node_numArgs,
        )
    elif kind == unknownFunctionNodeType:
        content = UnknownFunction(
            name=node.AST_unknown_function_node_string,
            argumentCount=node.AST_unknown_function_node_numArgs,
        )
    elif kind in (referenceNodeType, brokenReferenceNodeType):
        content = readFormulaReference(node)
    elif kind == rangeNodeType:
        content = readFormulaRange(node)
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
    if len(record.references) <= formulaKeySlot:
        return None
    return formulas.get(record.references[formulaKeySlot])


def readMerges(model: tst.TableModelArchive) -> list[MergeRange]:
    """Return the table's merged regions, read from the merge store.

    Merges are stored as FORMULAS, which is not guessable: each region is a
    complete `TSCE.FormulaArchive` whose colon tract carries the range, so this
    reads `merge_owner.formula_store` rather than inferring anything from the
    grid. See findings-03-structure.md.

    Matched by the presence of a colon tract rather than by node type, because
    the tract is the thing being read and asking for it directly cannot drift
    from an enum value.
    """
    if not model.HasField("merge_owner"):
        return []

    merges: list[MergeRange] = []
    for pair in model.merge_owner.formula_store.formulas:
        for node in pair.formula.AST_node_array.AST_node:
            if not node.HasField("AST_colon_tract"):
                continue
            tract = node.AST_colon_tract
            if not tract.absolute_column or not tract.absolute_row:
                continue
            column, row = tract.absolute_column[0], tract.absolute_row[0]
            # `range_end` is omitted for a single row or column rather than
            # repeating the beginning, so its absence means a span of one.
            lastColumn = (
                column.range_end if column.HasField("range_end") else column.range_begin
            )
            lastRow = row.range_end if row.HasField("range_end") else row.range_begin
            merges.append(
                MergeRange(
                    CellRange(
                        row.range_begin + originOffset,
                        column.range_begin + originOffset,
                        lastRow + originOffset,
                        lastColumn + originOffset,
                    )
                )
            )
    return merges


def readTable(index: ArchiveIndex, tableInfo: tst.TableInfoArchive) -> Table:
    """Build one `Table` from its `TST.TableInfoArchive`."""
    model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
    dataStore = model.base_data_store
    strings = readStringTable(index, dataStore)
    richText = readRichTextTable(index, dataStore)
    formulas = readFormulaTable(index, dataStore)

    # The grid size is declared by the table, never inferred from which cells hold
    # something. Seven of the corpus's tables declare more rows or columns than
    # their populated cells reach, so an inferred size is silently short.
    table = Table(
        name=model.table_name,
        rowCount=model.number_of_rows,
        colCount=model.number_of_columns,
        mergeRanges=readMerges(model),
    )
    tileSize = dataStore.tiles.tile_size

    # The tile LIST is authoritative. Its `tileid` gives the row range, and the
    # archive identifiers are not in row order, so nothing here may iterate
    # archives as found. See findings-03-structure.md.
    for entry in dataStore.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        firstRow = entry.tileid * tileSize
        for rowInfo in tile.rowInfos:
            wide = rowInfo.has_wide_offsets or tile.should_use_wide_rows
            records = decodeRow(
                rowInfo.cell_offsets, rowInfo.cell_storage_buffer, wide
            )
            # `tile_row_index` is LOCAL to its tile, so a document row is the
            # tile's own id times the tile size plus the local index. Reading it
            # as a document row gives eight different rows on an eight-tile table
            # and raises nothing. See findings-03-structure.md.
            row = firstRow + rowInfo.tile_row_index
            for record in records:
                cell = table.cell(
                    CellReference(row + originOffset, record.column + originOffset)
                )
                cell.value = resolveValue(record, strings, richText)
                # Each cell is given its own Formula even where the archive is
                # shared, so an edit to one cannot reach another. Frozen, so
                # sharing would be safe anyway; built per cell so that neither
                # guarantee depends on the other holding.
                cell.formula = resolveFormula(record, formulas)
                cell.errored = record.typeByte == formulaErrorType
    return table


def resolveValue(
    record: CellRecord, strings: dict[int, str], richText: dict[int, str]
) -> CellValue:
    """Return a cell's value, following a pooled key when the record holds one.

    `CellRecord.value` is deliberately `object`, because the decoder returns a
    Decimal for one type byte and an integer key for another. The invariant that a
    key-bearing type really did decode to an integer is checked here rather than
    assumed: a decoder that stopped returning one would otherwise index the pool
    with something else and hand back None, which reads as an empty cell.
    """
    if record.typeByte in (stringKeyType, richTextKeyType):
        key = record.value
        if not isinstance(key, int):
            raise ReadError(
                f"A type {record.typeByte} cell holds a key into a pooled list, "
                f"and this one decoded as {type(key).__name__}."
            )
        pool = strings if record.typeByte == stringKeyType else richText
        return pool.get(key)
    # Everything the decoder returns beyond a pooled key is already a CellValue:
    # a Decimal, a datetime, a timedelta, a bool, or None for a type it does not
    # recognize. The two key-bearing types are the only integers, and both are
    # resolved above.
    return cast(CellValue, record.value)


def readSheet(index: ArchiveIndex, sheetArchive: tn.SheetArchive) -> Sheet:
    """Build one `Sheet`, taking its tables in the sheet's own drawable order.

    A table is one kind of drawable among several. Shapes, images and text boxes
    share the list and belong to other tickets, so they are skipped by type here
    rather than parsed.
    """
    sheet = Sheet(name=sheetArchive.name)
    for reference in sheetArchive.drawable_infos:
        if index.typeOf(reference) != tableInfoTypeId:
            continue
        sheet.tables.append(
            readTable(index, index.resolve(reference, tst.TableInfoArchive))
        )
    return sheet


def open(path: Path | str) -> Document:  # noqa: A001
    """Read a `.numbers` file into a `Document`.

    Shadows the builtin deliberately: `pybers.open(path)` is the entry point the
    library is meant to be used through, and it reads as it should at the call
    site. The builtin is still reachable here as `builtins.open`.
    """
    source = Path(path)
    package = readPackage(source)
    index = ArchiveIndex(package)
    root = findRoot(index)

    # The package travels with the document because `Document.save` writes it back.
    document = Document(_package=package, _sourcePath=source)
    for reference in root.sheets:
        document.sheets.append(
            readSheet(index, index.resolve(reference, tn.SheetArchive))
        )
    return document


__all__ = ["ArchiveIndex", "ReadError", "open"]

#!/usr/bin/env python3
"""\
One table out of its archives and into the model: tiles, rows and cell records.

Three traps the documents established, all of which produce a plausible wrong
answer rather than an error, and all of which are handled here rather than left
to a caller:

- **The tile LIST is authoritative, never archive order.** Tile archive
  identifiers are demonstrably not in row order, so iterating archives as found
  scrambles a large table in silence.
- **`tile_row_index` is local to its tile.** A document row is
  `tileid * tile_size + tile_row_index`. Reading it as a document row gives eight
  different rows on an eight-tile table and raises nothing.
- **Strings are pooled.** A text cell holds a key into the table's STRING data
  list rather than the text, so a decode stopping at the record returns an integer
  that looks like a perfectly good number.

Private. The table feature offers `Table` and `Cell`, not the walk that builds one.

UPDATES
2026-10-11  Fixed tables are frozendict, for PYB-189.
2026-10-07  A row that fails to decode names its table by identifier, and a record
            of a type pybers does not recognize keeps that type, for PYB-169.
2026-10-01  A cell is described by the kind its record stores and the format it
            shows with, and a save describes it afresh, for PYB-141.
2026-09-30  A cell notes the text of a rich-text record it read, for PYB-137.
2026-09-23  A cell records where its record sits, and reads the conditions of
            its highlighting rules, for PYB-18.
2026-09-18  Each row and column reads its identity from the UID map, for PYB-17.
2026-09-16  A cell reads whether its format was chosen, for PYB-83.
2026-09-08  Split out of `pybers.document._read` for #58, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from collections.abc import Iterator
from pathlib import Path
from typing import cast

from .._generated import TSTArchives_pb2 as tst
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence import CellDecodeError, chooseOffsetUnit, decodeRow
from .._persistence.cells import (
    CellRecord,
    carriesChosenFormat,
    conditionalSlot,
    countedFormatSlots,
    displayedKindSlot,
    findSlotValue,
)
from .._persistence.index import (
    ArchiveIndex,
    readDataList,
    readUuidValue,
    richTextListType,
    stringListType,
)
from ..addressing import CellRange
from ..addressing.reference import CellAddress, originOffset
from ..errors import ReadError
from ..formula._read import readFormula, readFormulaTable, resolveFormula
from ..formula.nodes import Formula
from .cell import Cell, CellValue
from .cells import Table
from .kinds import CellDescription, CellFormat, CellKind, emptyDescription
from .merges import MergeRange

# Cell record type bytes whose decoded value is a key into a pooled data list
# rather than the value itself. See `pybers._persistence.cells`.
stringKeyType: int = 3
richTextKeyType: int = 9

# The kind each measured type byte stores. Type 8 is a failed formula, which holds no
# value, so its formula key sits where a result would. See findings-01-values.md.
storedKinds: frozendict[int, CellKind] = frozendict({
    0: CellKind.EMPTY,
    2: CellKind.NUMBER,
    3: CellKind.TEXT,
    5: CellKind.DATE_TIME,
    6: CellKind.BOOLEAN,
    7: CellKind.DURATION,
    8: CellKind.ERROR,
    9: CellKind.RICH_TEXT,
    10: CellKind.CURRENCY,
})

# The family each measured `format_type` belongs to, every one the documents carry.
formatFamilies: frozendict[int, CellFormat] = frozendict({
    256: CellFormat.NUMBER,
    257: CellFormat.CURRENCY,
    258: CellFormat.PERCENT,
    259: CellFormat.SCIENTIFIC,
    260: CellFormat.TEXT,
    261: CellFormat.DATE_TIME,
    262: CellFormat.FRACTION,
    263: CellFormat.CHECKBOX,
    267: CellFormat.STAR_RATING,
    268: CellFormat.DURATION,
    269: CellFormat.NUMERAL_SYSTEM,
    270: CellFormat.CUSTOM_NUMBER,
})


def readStringTable(index: ArchiveIndex, dataStore: tst.DataStore) -> dict[int, str]:
    """Return the table's pooled strings, keyed as the cell records address them."""
    if not dataStore.HasField("stringTable"):
        return {}
    entries = readDataList(index, dataStore.stringTable, stringListType)
    return {key: entry.string for key, entry in entries.items()}


def readRichTextTable(index: ArchiveIndex, dataStore: tst.DataStore) -> dict[int, str]:
    """Return the plain text of each rich-text payload, keyed as cells address it.

    A rich-text cell is not in this ticket's acceptance criteria, but every cell
    in every document has to read without failing, and a payload key returned raw
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


def readFormatTypes(index: ArchiveIndex, dataStore: tst.DataStore) -> dict[int, int]:
    """Return each format entry's `format_type`, keyed as the records name it."""
    if not dataStore.format_table.identifier:
        return {}
    dataList = index.resolve(dataStore.format_table, tst.TableDataList)
    return {
        int(entry.key): int(entry.format.format_type)
        for entry in dataList.entries if entry.HasField("format")
    }


def findDisplayedFormat(
    record: CellRecord, formatTypes: dict[int, int]
) -> CellFormat | None:
    """Return the family of the format a record displays with, or None for none.

    The displayed slot holds a kind, 1 to 6, naming the per-kind slot whose key is
    the format. A kind, key or type this cannot follow is unknown, never a guess.
    """
    displayed = findSlotValue(record, displayedKindSlot)
    if displayed is None:
        return None
    if not 1 <= displayed <= len(countedFormatSlots):
        return CellFormat.UNKNOWN
    key = findSlotValue(record, countedFormatSlots[displayed - 1])
    formatType = None if key is None else formatTypes.get(key)
    if formatType is None:
        return CellFormat.UNKNOWN
    return formatFamilies.get(formatType, CellFormat.UNKNOWN)


def readRecordDescription(
    record: CellRecord, formatTypes: dict[int, int]
) -> CellDescription:
    """Return what a record stores beyond its value."""
    kind = storedKinds.get(record.typeByte, CellKind.UNKNOWN)
    return CellDescription(
        kind=kind,
        format=findDisplayedFormat(record, formatTypes),
        formatChosen=carriesChosenFormat(record),
        unrecognizedTypeCode=record.typeByte if kind is CellKind.UNKNOWN else None,
    )


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


def readLineIdentities(
    index: ArchiveIndex, model: tst.TableModelArchive
) -> tuple[list[int], list[int]]:
    """Return each row's and column's identity, in the table's own order.

    `*_uid_for_index` is a permutation into the sorted list, so reading that list
    positionally names the wrong line. See findings-03-structure.md.
    """
    uids = index.resolve(model.base_column_row_uids, tst.ColumnRowUIDMapArchive)
    rows = [readUuidValue(uids.sorted_row_uids[at]) for at in uids.row_uid_for_index]
    columns = [
        readUuidValue(uids.sorted_column_uids[at])
        for at in uids.column_uid_for_index
    ]
    return rows, columns


def readConditionFormulas(
    index: ArchiveIndex, dataStore: tst.DataStore
) -> dict[int, tuple[Formula, ...]]:
    """Return each highlighting rule set's conditions, keyed as records name them.

    One condition per rule, hosted on the cell the rule colors, which is what lets
    a move rewrite them exactly as it rewrites a formula.
    """
    if not dataStore.HasField("conditionalstyletable"):
        return {}
    dataList = index.resolve(dataStore.conditionalstyletable, tst.TableDataList)
    return {
        int(entry.key): tuple(
            readFormula(rule.predicate.formula)
            for rule in index.resolve(
                entry.reference, tst.ConditionalStyleSetArchive
            ).rules.rule
        )
        for entry in dataList.entries
    }


def readTable(
    index: ArchiveIndex,
    tableInfo: tst.TableInfoArchive,
    source: Path,
    identifier: str = "",
) -> Table:
    """Build one `Table` from its `TST.TableInfoArchive`."""
    model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
    dataStore = model.base_data_store
    strings = readStringTable(index, dataStore)
    richText = readRichTextTable(index, dataStore)
    formulas = readFormulaTable(index, dataStore)
    conditions = readConditionFormulas(index, dataStore)
    rowIdentities, columnIdentities = readLineIdentities(index, model)

    # The grid size is declared by the table, never inferred from which cells hold
    # something. Seven of the documents' tables declare more rows or columns than
    # their populated cells reach, so an inferred size is silently short.
    table = Table(
        name=model.table_name,
        rowCount=model.number_of_rows,
        colCount=model.number_of_columns,
        mergeRanges=readMerges(model),
        identifier=identifier,
        _rowIdentities=rowIdentities,
        _columnIdentities=columnIdentities,
    )
    formatTypes = readFormatTypes(index, dataStore)
    for reference, record in iterateCellRecords(index, model, source):
        # A merge imported from Excel keeps a style-only record at every covered
        # position, and the model has no cell there to hold one. The archive
        # carries it through untouched, so nothing is lost.
        if not table.addressable(reference):
            continue
        cell = table.cell(reference)
        value = resolveValue(record, strings, richText)
        setCellDescription(cell, record, value, formatTypes)
        cell._value = value
        # Each cell is given its own Formula even where the archive is shared, so
        # an edit to one cannot reach another. Frozen, so sharing would be safe
        # anyway; built per cell so that neither guarantee depends on the other.
        cell.formula = resolveFormula(record, formulas)
        cell._origin = reference
        key = findSlotValue(record, conditionalSlot)
        if key is not None:
            cell._conditions = conditions.get(key, ())
    return table


def iterateCellRecords(
    index: ArchiveIndex, model: tst.TableModelArchive, source: Path
) -> Iterator[tuple[CellAddress, CellRecord]]:
    """Yield every record a table stores, with the cell it belongs to."""
    dataStore = model.base_data_store
    tileSize = dataStore.tiles.tile_size
    # The tile LIST is authoritative. Its `tileid` gives the row range, and the
    # archive identifiers are not in row order, so nothing here may iterate
    # archives as found. See findings-03-structure.md.
    for entry in dataStore.tiles.tiles:
        tile = index.resolve(entry.tile, tst.Tile)
        firstRow = entry.tileid * tileSize
        for rowInfo in tile.rowInfos:
            # `tile_row_index` is LOCAL to its tile, so a document row is the
            # tile's own id times the tile size plus the local index. Reading it
            # as a document row gives eight different rows on an eight-tile table
            # and raises nothing. See findings-03-structure.md.
            row = firstRow + rowInfo.tile_row_index
            try:
                records = decodeRow(
                    rowInfo.cell_offsets,
                    rowInfo.cell_storage_buffer,
                    chooseOffsetUnit(
                        rowInfo.has_wide_offsets, tile.should_use_wide_rows
                    ),
                )
            except CellDecodeError as exc:
                raise ReadError(
                    # By identifier, never by name, so a check report stays publishable.
                    f"{source}, table {model.table_id}, row "
                    f"{row + originOffset}: {exc}"
                ) from exc
            for record in records:
                column = record.column + originOffset
                yield CellAddress(row + originOffset, column), record


def setCellDescription(
    cell: Cell, record: CellRecord, value: CellValue, formatTypes: dict[int, int]
) -> None:
    """Give a cell the description of its record and the value that record holds."""
    cell._stored = readRecordDescription(record, formatTypes)
    cell._storedValue = value


def updateCellDescriptions(
    index: ArchiveIndex, tableInfo: tst.TableInfoArchive, table: Table, source: Path
) -> None:
    """Describe every cell of a saved table by the record the save left it.

    A cell the save left no record for is empty, as a cell never stored is.
    """
    model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
    dataStore = model.base_data_store
    strings = readStringTable(index, dataStore)
    richText = readRichTextTable(index, dataStore)
    formatTypes = readFormatTypes(index, dataStore)
    described: set[CellAddress] = set()
    for reference, record in iterateCellRecords(index, model, source):
        cell = table.cells.get(reference)
        if cell is None:
            continue
        value = resolveValue(record, strings, richText)
        setCellDescription(cell, record, value, formatTypes)
        described.add(reference)
    for reference, cell in table.cells.items():
        if reference not in described:
            cell._stored, cell._storedValue = emptyDescription, None


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

#!/usr/bin/env python3
"""\
One table out of its archives and into the model: tiles, rows and cell records.

Three traps the fixtures established, all of which produce a plausible wrong
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
2026-09-08  Split out of `pybers.reader` for #58, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from pathlib import Path
from typing import cast

from .._generated import TSTArchives_pb2 as tst
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence import CellDecodeError, decodeRow, offsetUnitFor
from .._persistence.cells import CellRecord
from .._persistence.index import (
    ArchiveIndex,
    originOffset,
    readDataList,
    richTextListType,
    stringListType,
)
from ..addressing import CellRange, CellReference
from ..errors import ReadError
from ..formula._read import readFormulaTable, resolveFormula
from .cells import CellValue, MergeRange, Table

# Cell record type bytes whose decoded value is a key into a pooled data list
# rather than the value itself. See `pybers._persistence.cells`.
stringKeyType: int = 3
richTextKeyType: int = 9

# A cell whose formula failed. It holds no value at all, so byte 12 is where its
# formula key sits rather than a result, and `decodeCellValue` consuming nothing
# for this type is what puts that key in the usual slot.
formulaErrorType: int = 8

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

    # The grid size is declared by the table, never inferred from which cells hold
    # something. Seven of the corpus's tables declare more rows or columns than
    # their populated cells reach, so an inferred size is silently short.
    table = Table(
        name=model.table_name,
        rowCount=model.number_of_rows,
        colCount=model.number_of_columns,
        mergeRanges=readMerges(model),
        identifier=identifier,
    )
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
                    offsetUnitFor(
                        rowInfo.has_wide_offsets, tile.should_use_wide_rows
                    ),
                )
            except CellDecodeError as exc:
                raise ReadError(
                    f"{source}, table {model.table_name!r}, row "
                    f"{row + originOffset}: {exc}"
                ) from exc
            for record in records:
                reference = CellReference(
                    row + originOffset, record.column + originOffset
                )
                # A merge imported from Excel keeps a style-only record at every
                # covered position, and the model has no cell there to hold one.
                # The archive carries it through untouched, so nothing is lost.
                if not table.addressable(reference):
                    continue
                cell = table.cell(reference)
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

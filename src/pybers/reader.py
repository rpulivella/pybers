#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Turn a `.numbers` package into the object model: the read half of the binding.

`pybers.archive` reads the container and decodes cell records; `pybers.model`
holds the dataclasses. Neither knows about the other, and this module is what
joins them. It lives outside `pybers.model` on purpose, so that importing the
model never drags in the archive layer. See CLAUDE.md, "Document is the single
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
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/31"

from pathlib import Path
from typing import TypeVar, cast

from google.protobuf.message import Message

from ._generated import TNArchives_pb2 as tn
from ._generated import TSTArchives_pb2 as tst
from ._generated import TSWPArchives_pb2 as tswp
from .archive import Archive, NumbersPackage, decodeRow, readPackage
from .archive.types import archiveTypeId, parseArchive
from .model import CellValue, Document, MergeRange, Sheet, Table

# The archive counts rows and columns from zero. The model counts from one,
# because that is what Numbers shows and what a caller means by "row 1". The two
# systems meet HERE and nowhere else: an archive coordinate never reaches the
# model, and a model coordinate never reaches a decoder. A design keeping both in
# one object is how a reader comes to be off by one in only some places.
originOffset: int = 1

# Every resolve names the archive class it expects, so the expectation is checked
# rather than assumed. Bound to Message because only a generated class can be the
# target of a reference.
ArchiveT = TypeVar("ArchiveT", bound=Message)

# The registry identifiers this module navigates by. Named rather than written as
# literals at the point of use, because a bare 6000 in a conditional says nothing.
documentTypeId: int = 1
tableInfoTypeId: int = 6000

# Cell record type bytes whose decoded value is a key into a pooled data list
# rather than the value itself. See `pybers.archive.cells`.
stringKeyType: int = 3
richTextKeyType: int = 9

# `TST.TableDataList.ListType` values, restated so that reading this file does not
# require the generated enum in hand.
stringListType: int = 1
richTextListType: int = 8


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

    def resolve(self, reference, expected: type[ArchiveT]) -> ArchiveT:
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

    def typeOf(self, reference) -> int:
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
    index: ArchiveIndex, reference, listType: int
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
                    anchorRow=row.range_begin + originOffset,
                    anchorCol=column.range_begin + originOffset,
                    rowSpan=lastRow - row.range_begin + 1,
                    colSpan=lastColumn - column.range_begin + 1,
                )
            )
    return merges


def readTable(index: ArchiveIndex, tableInfo: tst.TableInfoArchive) -> Table:
    """Build one `Table` from its `TST.TableInfoArchive`."""
    model = index.resolve(tableInfo.tableModel, tst.TableModelArchive)
    dataStore = model.base_data_store
    strings = readStringTable(index, dataStore)
    richText = readRichTextTable(index, dataStore)

    table = Table(name=model.table_name, mergeRanges=readMerges(model))
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
                cell = table.cellAt(
                    row + originOffset, record.column + originOffset
                )
                cell.value = resolveValue(record, strings, richText)
    return table


def resolveValue(
    record, strings: dict[int, str], richText: dict[int, str]
) -> CellValue:
    """Return a cell's value, following a pooled key when the record holds one."""
    if record.typeByte == stringKeyType:
        return strings.get(record.value)
    if record.typeByte == richTextKeyType:
        return richText.get(record.value)
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
    package = readPackage(Path(path))
    index = ArchiveIndex(package)
    root = findRoot(index)

    document = Document()
    for reference in root.sheets:
        document.sheets.append(
            readSheet(index, index.resolve(reference, tn.SheetArchive))
        )
    return document


__all__ = ["ArchiveIndex", "ReadError", "open"]

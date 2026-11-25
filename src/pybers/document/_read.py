#!/usr/bin/env python3
"""\
Turn a `.numbers` package into the object model: the read half of the binding.

`pybers._persistence` reads the container and decodes cell records, and each
feature holds its own dataclasses. Neither knows about the other, and this module
is what joins them at the document level, handing each table to the feature that
owns it.

The archive index and the two lookups every reader needs are in
`pybers.archives`; formulas are in `pybers.readformula` and the calculation
engine in `pybers.readengine`. What is left here is the walk from a document down
to a cell.

Three traps the documents established, all of which produce a plausible wrong
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
2026-11-24  `open` reports each member and each table it reads, for PYB-319.
2026-11-17  The theme's table style, which a table added starts from, for PYB-266.
2026-11-02  A package pybers created becomes a document too, for PYB-261.
2026-10-27  The document's locale identifier is read, for PYB-272.
2026-10-24  The sheets and tables linked by `Document._ownersLink`, for PYB-259.
2026-10-22  The locale's currency symbols and placement are read, for PYB-220.
2026-08-31  Written for #1: document, sheets, tables and cell values.
2026-09-01  The package read here travels with the document, for #2.
2026-09-03  Formulas, for #41. The key slot and the sticky-bits rule were
            measured against the documents, not read off the schema.
2026-09-08  Formulas, the engine and the index moved to modules of their own
            for #45, and a table carries the identity by which formulas select it.
2026-09-14  A sheet carries the identifier of the archive it was read from,
            for PYB-63.
2026-09-22  Type identifiers are asked of the registry by class, for PYB-113.
2026-10-07  A package already read becomes a document through `readDocument`,
            for PYB-169.
2026-10-20  `open` takes the time zone an aware date is written in, for PYB-144.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/31"

import itertools
from collections.abc import Callable
from pathlib import Path

from .._engine import readTableIdentities
from .._generated import TNArchives_pb2 as tn
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence import NumbersPackage, readPackage
from .._persistence.index import ArchiveIndex, findRoot
from .._persistence.types import findArchiveTypeId
from ..errors import ReadError
from ..status import ProgressListener, composeProgressCount, dropProgress
from ..table._read import readTable
from ..table._tablestyle import readDocumentTableStyle
from ..timezone import TimeZoneLike, machineTimeZone, toTimeZone
from .sheets import Document, Sheet


def listTableReferences(
    index: ArchiveIndex, sheetArchive: tn.SheetArchive
) -> list[tsp.Reference]:
    """Return a sheet's tables in its own drawable order.

    A table is one kind of drawable among several. Shapes, images and text boxes
    share the list and belong to other tickets, so they are skipped by type here
    rather than parsed.
    """
    tableTypeId = findArchiveTypeId(tst.TableInfoArchive)
    return [
        reference for reference in sheetArchive.drawable_infos
        if index.typeOf(reference) == tableTypeId
    ]


def readSheet(
    index: ArchiveIndex,
    sheetArchive: tn.SheetArchive,
    identifier: int,
    source: Path | None,
    identities: dict[int, str],
    onTableRead: Callable[[], None],
) -> Sheet:
    """Build one `Sheet`, taking its tables in the sheet's own drawable order."""
    sheet = Sheet(name=sheetArchive.name, _identifier=identifier)
    for reference in listTableReferences(index, sheetArchive):
        table = readTable(
            index,
            index.resolve(reference, tst.TableInfoArchive),
            source,
            identities.get(reference.identifier, ""),
        )
        table._identifier = reference.identifier
        sheet.tables.append(table)
        onTableRead()
    return sheet


def open(  # noqa: A001
    path: Path | str,
    *,
    timeZone: TimeZoneLike = machineTimeZone,
    onProgress: ProgressListener | None = None,
) -> Document:
    """Read a `.numbers` file into a `Document`, writing aware dates in `timeZone`.

    Shadows the builtin deliberately. The zone defaults to the one pybers runs in, and
    specifying one makes a script's result the same wherever it runs. `onProgress`
    hears each member and table read, counted against its total.
    """
    zone = toTimeZone(timeZone)
    source = Path(path)
    report = onProgress or dropProgress
    document = readDocument(readPackage(source, report), source, report)
    document.timeZone = zone
    return document


def readDocument(
    package: NumbersPackage,
    source: Path | None,
    onProgress: ProgressListener = dropProgress,
) -> Document:
    """Build a `Document` from a package read from `source`, or created when None."""
    index = ArchiveIndex(package)
    root = findRoot(index)

    # The package travels with the document because `Document.save` writes it back.
    locale = root.super.super
    symbols = locale.formatting_symbols
    document = Document(
        _package=package,
        _sourcePath=source,
        _currencySymbols=frozendict(
            (each.code, each.symbol) for each in symbols.currency_symbols
        ),
        _currencyPattern=symbols.currency_pattern,
        _localeIdentifier=locale.locale_identifier,
        _tableStyleTheme=readDocumentTableStyle(index),
    )
    identities = readTableIdentities(index)
    sheetArchives = [
        (reference.identifier, index.resolve(reference, tn.SheetArchive))
        for reference in root.sheets
    ]
    total = sum(len(listTableReferences(index, each)) for _, each in sheetArchives)
    tablesRead = itertools.count(1)

    def reportTableRead() -> None:
        onProgress(composeProgressCount("reading the tables", next(tablesRead), total))

    for identifier, sheetArchive in sheetArchives:
        document.sheets.append(readSheet(
            index, sheetArchive, identifier, source, identities, reportTableRead
        ))
    document._ownersLink()
    return document


__all__ = ["ArchiveIndex", "ReadError", "open", "readDocument"]

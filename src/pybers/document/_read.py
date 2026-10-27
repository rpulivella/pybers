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
2026-10-27  The document's locale identifier is read, for PYB-272.
2026-10-24  The sheets and tables linked by `Document._ownersLink`, for PYB-259.
2026-10-22  The locale's currency symbols and placement are read, for PYB-220.
2026-08-31  Written for #1: document, sheets, tables and cell values.
2026-09-01  The package read here travels with the document, for #2.
2026-09-03  Formulas, for #41. The key slot and the sticky-bits rule were
            measured against the documents, not read off the schema.
2026-09-08  Formulas, the engine and the index moved to modules of their own
            for #45, and a table carries the identity formulas name it by.
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

from pathlib import Path

from .._engine import readTableIdentities
from .._generated import TNArchives_pb2 as tn
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._persistence import NumbersPackage, readPackage
from .._persistence.index import ArchiveIndex, findRoot
from .._persistence.types import findArchiveTypeId
from ..errors import ReadError
from ..table._read import readTable
from ..timezone import TimeZoneLike, machineTimeZone, toTimeZone
from .sheets import Document, Sheet


def readSheet(
    index: ArchiveIndex,
    identifier: int,
    source: Path,
    identities: dict[int, str],
) -> Sheet:
    """Build one `Sheet`, taking its tables in the sheet's own drawable order.

    A table is one kind of drawable among several. Shapes, images and text boxes
    share the list and belong to other tickets, so they are skipped by type here
    rather than parsed.
    """
    sheetArchive = index.resolve(tsp.Reference(identifier=identifier), tn.SheetArchive)
    sheet = Sheet(name=sheetArchive.name, _identifier=identifier)
    for reference in sheetArchive.drawable_infos:
        if index.typeOf(reference) != findArchiveTypeId(tst.TableInfoArchive):
            continue
        table = readTable(
            index,
            index.resolve(reference, tst.TableInfoArchive),
            source,
            identities.get(reference.identifier, ""),
        )
        table._identifier = reference.identifier
        sheet.tables.append(table)
    return sheet


def open(  # noqa: A001
    path: Path | str, *, timeZone: TimeZoneLike = machineTimeZone
) -> Document:
    """Read a `.numbers` file into a `Document`, writing aware dates in `timeZone`.

    Shadows the builtin deliberately, so the entry point reads as it should. The
    zone defaults to the one pybers is running in, and naming one makes a script's
    result the same wherever it runs.
    """
    zone = toTimeZone(timeZone)
    source = Path(path)
    document = readDocument(readPackage(source), source)
    document.timeZone = zone
    return document


def readDocument(package: NumbersPackage, source: Path) -> Document:
    """Build a `Document` from a package already read from `source`."""
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
    )
    identities = readTableIdentities(index)
    for reference in root.sheets:
        document.sheets.append(
            readSheet(index, reference.identifier, source, identities)
        )
    document._ownersLink()
    return document


__all__ = ["ArchiveIndex", "ReadError", "open", "readDocument"]

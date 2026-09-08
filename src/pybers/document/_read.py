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
2026-09-08  Formulas, the engine and the index moved to modules of their own
            for #45, and a table carries the identity formulas name it by.
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

from .._engine import tableIdentities
from .._generated import TNArchives_pb2 as tn
from .._generated import TSTArchives_pb2 as tst
from .._persistence import (
    readPackage,
)
from .._persistence.index import (
    ArchiveIndex,
    findRoot,
    tableInfoTypeId,
)
from ..errors import ReadError
from ..table._read import readTable
from .sheets import Document, Sheet


def readSheet(
    index: ArchiveIndex,
    sheetArchive: tn.SheetArchive,
    source: Path,
    identities: dict[int, str],
) -> Sheet:
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
            readTable(
                index,
                index.resolve(reference, tst.TableInfoArchive),
                source,
                identities.get(reference.identifier, ""),
            )
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
    identities = tableIdentities(index)
    for reference in root.sheets:
        document.sheets.append(
            readSheet(
                index,
                index.resolve(reference, tn.SheetArchive),
                source,
                identities,
            )
        )
    # Linked after the sheets are in, so a cell can name another table without the
    # caller passing the names, and so `Table.document` is never half a document.
    for sheet in document.sheets:
        for table in sheet.tables:
            table.document = document
    return document


__all__ = ["ArchiveIndex", "ReadError", "open"]

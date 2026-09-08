#!/usr/bin/env python3
"""\
The archive type registry: which generated protobuf class a `typeId` selects.

`iwa.py` finds message boundaries and stops, keeping every body as raw bytes,
because deciding what a body *is* needs a source of truth that layer does not
own. This is that source of truth, and parsing an archive is the one thing it
does.

**Curated deliberately, and it is meant to stay incomplete.** Apple's registry
runs to hundreds of types; the 46 fixtures here exercise 76 of them; this file
carries only the ones a real read path reaches. An entry earns its place by
being resolved while reading a document, and a ticket that reaches a new type
adds it with the rest of its work. The alternative, shipping a full table
transcribed from elsewhere, would put hundreds of untested entries in the wheel
and quietly make this project a redistributor of someone else's extraction.

Types map to the generated **class**, not to its name as a string. A name would
need `descriptor_pool` and `message_factory` at runtime, and a misspelling in it
would surface as a lookup failure at parse time without saying which entry was
wrong. A misspelled symbol fails at import and names itself.

UPDATES
2026-09-02  The three TSCE types the write path needs to request a recalculation,
            for #25.
2026-08-31  Written for the document read path: root, sheets, tables, tiles,
            data lists and cell styles.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/31"

from google.protobuf.message import Message

from .._generated import TNArchives_pb2 as tn
from .._generated import TSCEArchives_pb2 as tsce
from .._generated import TSSArchives_pb2 as tss
from .._generated import TSTArchives_pb2 as tst
from .._generated import TSWPArchives_pb2 as tswp
from .iwa import Archive

# typeId to generated class, for every type pybers resolves on a read path.
#
# The identifiers are Apple's own and are not carried in the `.proto` schemas,
# which is why this table cannot be derived from them: all 33 were checked for a
# type-id option and none carries one. Each entry below was confirmed against the
# fixture corpus rather than assumed.
archiveTypes: dict[int, type[Message]] = {
    1: tn.DocumentArchive,          # the root: holds the ordered sheet list
    2: tn.SheetArchive,             # a tab: its name and its ordered drawables
    401: tss.StylesheetArchive,     # the shared style registry
    2001: tswp.StorageArchive,      # rich text, reached from a cell payload
    4000: tsce.CalculationEngineArchive,     # the dependency graph and dirty set
    4008: tsce.FormulaOwnerDependenciesArchive,  # one owner's dependencies
    4009: tsce.CellRecordTileArchive,       # which cells of a tile hold formulas
    4011: tsce.ReferencesToDirtyArchive,     # cells to recalculate on next open
    6000: tst.TableInfoArchive,     # the drawable that wraps a table
    6001: tst.TableModelArchive,    # the table proper: geometry, stores, merges
    6002: tst.Tile,                 # one block of rows and their cell records
    6004: tst.CellStyleArchive,     # a cell's resolved appearance
    6005: tst.TableDataList,        # the pooled strings, styles and formulas
    6218: tst.RichTextPayloadArchive,
}


class ArchiveTypeError(RuntimeError):
    """An archive whose type is not in the registry, or which failed to parse."""


def archiveTypeId(archive: Archive) -> int:
    """Return the type identifier that classifies an archive.

    The first message is the archive itself and any others are companions to it.
    Measured across the corpus: of 31,028 archives, 30,706 carry exactly one
    message, and in the 322 that carry more, the untyped companions appear only
    at positions one through three. Position zero is never one of them, so the
    first message is always the one that says what the archive is.
    """
    if not archive.messages:
        raise ArchiveTypeError(
            f"Archive {archive.identifier} carries no messages, so nothing "
            "identifies what it is."
        )
    return archive.messages[0].typeId


def parseArchive(archive: Archive) -> Message:
    """Parse an archive's own message into its generated class.

    Raises on an unregistered type rather than returning `None`. A caller that
    reached this archive did so by following a reference it expected to resolve,
    so an unknown type there means the read path is wrong, and continuing past it
    would build a model with a silent hole in it.
    """
    typeId = archiveTypeId(archive)
    messageClass = archiveTypes.get(typeId)
    if messageClass is None:
        raise ArchiveTypeError(
            f"Archive {archive.identifier} has type {typeId}, which is not in "
            "the registry. Add it to archiveTypes with the ticket that needs it."
        )
    message = messageClass()
    try:
        message.ParseFromString(archive.messages[0].data)
    except Exception as exc:
        raise ArchiveTypeError(
            f"Archive {archive.identifier} declares type {typeId} "
            f"({messageClass.DESCRIPTOR.full_name}) but its "
            f"{len(archive.messages[0].data)} "
            "bytes did not parse as one."
        ) from exc
    return message

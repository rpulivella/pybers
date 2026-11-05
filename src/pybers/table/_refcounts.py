#!/usr/bin/env python3
"""\
The refcounts a table's lists keep: which records claim which entry, and how many.

A format, a style, a pooled string and a rich-text payload each carry a refcount of
the records naming them. A record written moves the counts its slots changed, a
record removed releases what it named, and an entry released to 0 that no record
still names is removed at the end of the save, as Numbers removes it. Each list is
an `EntryPool`, which keys, claims and releases its entries.

Private. Part of the table feature's archive half.

UPDATES
2026-10-29  Every list is an `EntryPool`, for PYB-278.
2026-10-01  The per-kind format slots moved to `_persistence.cells`, for PYB-141.
2026-09-29  A copied record claims its string and style entries, a copied
            rich-text cell gains an entry of its own, and a spent one is removed
            with the archives only it held, for PYB-118.
2026-09-22  Split out of the table writer for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from collections import Counter
from collections.abc import Iterable

from .._generated import TSKArchives_pb2 as tsk
from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from .._generated import TSWPArchives_pb2 as tswp
from .._persistence import decodeRecord
from .._persistence.cells import CellRecord, countedFormatSlots, listReferenceSlots
from .._persistence.index import ArchiveIndex
from .._persistence.metadata import PackageRegistry, createSiblingArchive
from .._persistence.pool import EntryPool, ListEntry
from .._persistence.rows import StoredTiles
from ..errors import WriteError
from ._read import readStringTable

# A pooled string cell holds a four-byte key where a number holds sixteen bytes of
# decimal128, so changing between them moves every trailing reference.
stringTypeByte: int = 3


# A rich-text cell names its payload by key, and an entry's refcount is how many such
# records name it, which reproduces all 16 rich-text lists in the documents.
richTextTypeByte: int = 9


# A style's refcount is how often its key sits in these two slots, which reproduces
# every style list in the documents, measured 2026-09-15 for PYB-92.
countedStyleSlots: tuple[tuple[int, int], ...] = ((8, 0x20), (8, 0x40))


def readStringPool(
    index: ArchiveIndex, store: tst.DataStore
) -> EntryPool[str] | None:
    """Return the table's string pool, or None when it carries no string list.

    A table that has never held text carries no list to write into, which is a
    different state from one whose list is empty.
    """
    if not store.stringTable.identifier:
        return None
    return EntryPool(
        dataList=index.resolve(store.stringTable, tst.TableDataList),
        noun="string",
        write=writeStringEntry,
        stored=readStringTable(index, store),
    )


def writeStringEntry(entry: ListEntry, text: str) -> None:
    """Put a pooled string into its entry."""
    entry.string = text


def readCountedPool(
    index: ArchiveIndex, reference: tsp.Reference, noun: str
) -> EntryPool[object]:
    """Return a list pybers claims and releases entries of but never adds to."""
    return EntryPool(dataList=index.resolve(reference, tst.TableDataList), noun=noun)


def countFormatClaims(raw: bytes) -> Counter[int]:
    """Return how often one record names each format, counted as refcounts count."""
    references = decodeRecord(0, raw).references
    return Counter(
        key
        for slot, key in zip(listReferenceSlots(raw), references, strict=True)
        if slot in countedFormatSlots
    )


def readFormatPool(
    index: ArchiveIndex, store: tst.DataStore
) -> EntryPool[tsk.FormatStructArchive] | None:
    """Return the table's format list, or None when it carries none."""
    if not store.format_table.identifier:
        return None
    dataList = index.resolve(store.format_table, tst.TableDataList)
    return EntryPool(
        dataList=dataList,
        noun="format",
        write=lambda entry, wanted: entry.format.CopyFrom(wanted),
        stored={
            int(entry.key): entry.format
            for entry in dataList.entries if entry.HasField("format")
        },
    )


def moveFormatReferences(
    pool: EntryPool[tsk.FormatStructArchive],
    before: bytes | None,
    after: bytes | None,
    where: str,
) -> None:
    """Move refcounts from the formats a record named to those it names now.

    `before` is None for a record no cell owned, and `after` for one being removed.
    Only a slot that changed moves a count, so an entry no written record touches
    keeps the count Numbers wrote even where that count disagrees with its cells.
    """
    change = countFormatClaims(after) if after is not None else Counter()
    change.subtract(countFormatClaims(before) if before is not None else Counter())
    for key, delta in change.items():
        if delta > 0:
            pool.claim(key, delta, where)
        elif delta < 0:
            pool.release(key, -delta)


def listStringClaims(record: CellRecord) -> Iterable[int]:
    """Return the pooled string key a text record names, if it is one."""
    if record.typeByte == stringTypeByte and isinstance(record.value, int):
        return (record.value,)
    return ()


def listStyleClaims(record: CellRecord) -> Iterable[int]:
    """Return the style keys a record names, once per counted slot."""
    return [
        key
        for slot, key in zip(
            listReferenceSlots(record.raw), record.references, strict=True
        )
        if slot in countedStyleSlots
    ]


def listRichTextClaims(record: CellRecord) -> Iterable[int]:
    """Return the rich-text key a rich-text record names, if it is one."""
    if record.typeByte == richTextTypeByte and isinstance(record.value, int):
        return (record.value,)
    return ()


def copyRichText(registry: PackageRegistry, pool: EntryPool[int], key: int) -> int:
    """Give a copied rich-text cell an entry of its own, and return its key.

    Numbers' fill gave each copy its own payload and storage, beside the original
    and sharing its style sheet and styles, measured 2026-09-29 in `63e`. Sharing
    one entry would turn an edit to one cell into an edit of the other.
    """
    index = registry.index
    source = pool.entryFind(key)
    if source is None:
        raise WriteError(
            f"A copied record would name rich text {key}, which its table does not "
            "hold."
        )
    payload = tst.RichTextPayloadArchive()
    payload.CopyFrom(
        index.resolve(source.rich_text_payload, tst.RichTextPayloadArchive)
    )
    storage = index.resolve(payload.storage, tswp.StorageArchive)
    payload.storage.identifier = createSiblingArchive(
        registry, payload.storage.identifier, storage
    )
    identifier = createSiblingArchive(
        registry, source.rich_text_payload.identifier, payload
    )
    index.archiveWrite(identifier, payload, [payload.storage.identifier])
    return pool.entryAdd(identifier, 1)


def readRichTextPool(index: ArchiveIndex, store: tst.DataStore) -> EntryPool[int]:
    """Return the table's rich-text list, each entry naming its payload archive."""
    return EntryPool(
        dataList=index.resolve(store.rich_text_table, tst.TableDataList),
        noun="rich text",
        write=writeRichTextEntry,
    )


def writeRichTextEntry(entry: ListEntry, identifier: int) -> None:
    """Point an entry at the payload archive it holds."""
    entry.rich_text_payload.identifier = identifier


def isArchiveReferenced(index: ArchiveIndex, target: int) -> bool:
    """Report whether any archive in the package declares a reference to `target`."""
    for archive in index.byIdentifier.values():
        info = tspArchive.ArchiveInfo()
        info.ParseFromString(archive.infoBytes)
        if any(target in message.object_references for message in info.message_infos):
            return True
    return False


def removeSpentRichText(
    registry: PackageRegistry, pool: EntryPool[int], tiles: StoredTiles
) -> None:
    """Remove each spent rich-text entry with every archive only it held.

    Numbers removed the entry, its payload, its storage and the character styles
    only that storage named, keeping styles other cells share, measured 2026-09-29
    in `63b-fill-menu-down`.
    """
    index = registry.index
    storages = {
        int(entry.key): index.resolve(
            entry.rich_text_payload, tst.RichTextPayloadArchive
        ).storage.identifier
        for entry in pool.dataList.entries if entry.key in pool.released
    }
    payloads = {int(entry.key): entry.rich_text_payload.identifier
                for entry in pool.dataList.entries}
    for key in pool.spentRemove(tiles, listRichTextClaims):
        held = registry.strongReferencesOf(storages[key])
        registry.archiveRemove(payloads[key])
        registry.archiveRemove(storages[key])
        for target in held:
            if target in index.byIdentifier and not isArchiveReferenced(index, target):
                registry.archiveRemove(target)


__all__ = [
    "countFormatClaims",
    "countedStyleSlots",
    "copyRichText",
    "listRichTextClaims",
    "listStringClaims",
    "listStyleClaims",
    "moveFormatReferences",
    "readCountedPool",
    "readFormatPool",
    "readRichTextPool",
    "readStringPool",
    "removeSpentRichText",
    "richTextTypeByte",
    "stringTypeByte",
]

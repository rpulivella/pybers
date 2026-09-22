#!/usr/bin/env python3
"""\
Every archive in a package, addressable by the identifier a reference carries.

Named for the `Index/` directory inside a `.numbers` package, which is where the
archives this walks actually live. It sits directly above `types`, which maps a
type identifier to a generated class, and below everything that turns an archive
into a model or back.

Both halves of the binding need it: each has to resolve a reference, find the one
root, and read a pooled data list, and neither owns those.

**A reference carries an identifier and nothing else.** There is no hint of which
member of which file holds the target, so resolving one means having the whole
package indexed up front, which is why the index is built eagerly and in full.

UPDATES
2026-09-22  Every write, addition and removal within one save passes through the
            index, which hands out one parsed message per archive, for PYB-109.
2026-09-18  A UUID's value read and assigned here, for PYB-17.
2026-09-08  Moved into the persistence layer for #58. It was `pybers.archives`,
            which put the word back at the top level after PYB-2 had retired it.
2026-09-08  Split out of `pybers.document._read` for #45, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from google.protobuf.message import Message

from .._generated import TNArchives_pb2 as tn
from .._generated import TSPMessages_pb2 as tsp
from .._generated import TSTArchives_pb2 as tst
from ..errors import ReadError
from .container import NumbersPackage
from .iwa import Archive, IWAFile
from .types import parseArchive, readArchiveTypeId

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
calculationEngineTypeId: int = 4000

# The `owner_kind` a table's dependency entry carries, as against the other owners
# the calculation engine tracks.
tableOwnerKind: int = 1

# A `TSP.UUID` is two 64-bit halves and a formula's table identifier is four 32-bit
# words, so the same value is spelled two ways and has to be converted between them.
wordBits: int = 32
wordMask: int = 0xFFFFFFFF
halfBits: int = 64
halfMask: int = (1 << halfBits) - 1

# `TST.TableDataList.ListType` values, restated so that reading this file does not
# require the generated enum in hand.
stringListType: int = 1
formulaListType: int = 3
richTextListType: int = 8

# A formula-backed cell names its formula in the FIRST of its trailing
# references. Established on 2026-09-03 by reproducing declared refcounts: in all
# nine tables in the documents that declare formulas, counting the cells that name
# each key through slot 0 equals the refcount the table declares, and no other
# slot does so in any table. Value matching alone could not settle it, because
# formula keys and style indices are both small integers and several slots
# coincide by chance. An error cell consumes no value, so byte 12 is at once its
# value slot and this slot, which is why one rule covers both.


class ArchiveIndex:
    """Every archive in a package, addressable by the identifier references use.

    A `TSP.Reference` carries only an identifier, with no hint of which member
    holds the target, so resolving one means having the whole package indexed
    first. Built once per read, and once per save.

    **Within one save the index is the only path to an archive, read or written.**
    Every archive resolves to one parsed message, so a pass that changes it hands
    the change to every later reader, and a write keeps that same message.
    """

    def __init__(self, package: NumbersPackage) -> None:
        """Index every archive in the package by identifier.

        Built eagerly and in full, because a reference gives no hint which member
        holds its target, so a lazy index would have to scan every member on the
        first miss anyway.
        """
        self.package = package
        self.byIdentifier: dict[int, Archive] = {}
        self.owners: dict[int, IWAFile] = {}
        self.parsed: dict[int, Message] = {}
        self.removed: set[int] = set()
        for iwaFile in package.iwaFiles:
            for archive in iwaFile.archives:
                self.byIdentifier[archive.identifier] = archive
                self.owners[archive.identifier] = iwaFile

    def archive(self, identifier: int) -> Archive:
        """Return the archive with this identifier, or raise naming it."""
        found = self.byIdentifier.get(identifier)
        if found is None:
            if identifier in self.removed:
                raise ReadError(
                    f"Reference to archive {identifier}, which this save removed."
                )
            raise ReadError(
                f"Reference to archive {identifier}, which is not in this document."
            )
        return found

    def identifierResolve[ArchiveT: Message](
        self, identifier: int, expected: type[ArchiveT]
    ) -> ArchiveT:
        """Return the one parsed message of an archive, as the class named."""
        message = self.parsed.get(identifier)
        if message is None:
            message = parseArchive(self.archive(identifier))
            self.parsed[identifier] = message
        if not isinstance(message, expected):
            raise ReadError(
                f"Archive {identifier} is a "
                f"{type(message).DESCRIPTOR.full_name}, but a "
                f"{expected.DESCRIPTOR.full_name} was expected here."
            )
        return message

    # Every resolve names the archive class it expects, so the expectation is
    # checked rather than assumed, and Message bounds it because only a generated
    # class can be the target of a reference.
    def resolve[ArchiveT: Message](
        self, reference: tsp.Reference, expected: type[ArchiveT]
    ) -> ArchiveT:
        """Return the archive a `TSP.Reference` points at, as the class named.

        The expected class is required rather than inferred, and it is checked.
        A reference is a bare identifier with no type on it, so following the
        wrong field yields a real archive of the wrong kind, and reading a table
        model as a tile would produce a plausible empty table rather than an
        error. Naming the expectation turns that into a stop.
        """
        return self.identifierResolve(reference.identifier, expected)

    def typeOf(self, reference: tsp.Reference) -> int:
        """Return a reference target's type without parsing it.

        Needed for the drawable list, which mixes tables with shapes, images and
        text boxes. Those have their own tickets and are not in the registry yet,
        so they have to be recognized and skipped rather than parsed and refused.
        """
        return readArchiveTypeId(self.archive(reference.identifier))

    def archiveWrite(
        self, identifier: int, body: Message, references: list[int] | None = None
    ) -> None:
        """Write an archive's own message, which every later read then returns.

        `references` replaces the strong references it declares, which a body
        gaining or losing one has to state.
        """
        self.archive(identifier)
        self.byIdentifier[identifier] = self.owners[identifier].messageReplace(
            identifier, 0, body.SerializeToString(), references
        )
        self.parsed[identifier] = body

    def archiveAdd(
        self, member: IWAFile, archive: Archive, body: Message | None = None
    ) -> None:
        """Place a created archive in a member, `body` being its parsed message."""
        member.archiveAdd(archive)
        self.byIdentifier[archive.identifier] = archive
        self.owners[archive.identifier] = member
        if body is not None:
            self.parsed[archive.identifier] = body

    def archiveRemove(self, identifier: int) -> None:
        """Drop an archive from its member, so a later read raises naming it."""
        self.archive(identifier)
        self.owners.pop(identifier).archiveRemove(identifier)
        del self.byIdentifier[identifier]
        self.parsed.pop(identifier, None)
        self.removed.add(identifier)


def readUuidValue(message: tsp.UUID) -> int:
    """Return a UUID's value from its two halves."""
    return (message.upper << halfBits) | message.lower


def assignUuid(message: tsp.UUID, value: int) -> None:
    """Set a UUID's two halves from a value."""
    message.lower = value & halfMask
    message.upper = value >> halfBits


def findRoot(index: ArchiveIndex) -> tn.DocumentArchive:
    """Return the document's root `TN.DocumentArchive`.

    Found by type rather than by position or by member name. Exactly one archive
    in a document carries this type, verified across every document, so
    a count other than one means the file is not what this library thinks it is
    and is worth stopping on.
    """
    roots = [
        archive for archive in index.byIdentifier.values()
        if readArchiveTypeId(archive) == documentTypeId
    ]
    if len(roots) != 1:
        raise ReadError(
            f"Expected exactly one TN.DocumentArchive, found {len(roots)}."
        )
    return index.identifierResolve(roots[0].identifier, tn.DocumentArchive)


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


__all__ = ["ArchiveIndex", "assignUuid", "findRoot", "readDataList", "readUuidValue"]

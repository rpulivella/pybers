#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
The `.numbers` document container: a zip of IWA members and supporting files.

A `.numbers` file is a zip. `Index/*.iwa` members carry the document itself; the
rest (a preview image, metadata, asset files) are ordinary payloads this layer
carries through untouched.

Every member's storage method is recorded and replayed rather than assumed. In
every file examined so far each member is STORED, because the IWA payload is
already Snappy-compressed and deflating it again buys nothing. That is an
observation about the files seen, though, not a guarantee about the format, and
re-deflating a member Apple chose to store would change bytes for no reason. So
the method travels with the member.

This is the deliberate opposite of how the IWA frame flag is handled one layer
down. There, an unknown value raises, because handling it would mean shipping an
untestable decoder. Here, the variation costs one field to carry and nothing to
support, and carrying it makes the round trip robust to a file this developer has
not seen yet. Record what varies; refuse what cannot be verified.

UPDATES
2026-08-16  Written. Round-trips empty-1/2/3.numbers byte for byte.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .iwa import IWAFile, readIWAFile, writeIWAFile

# Members under this prefix, with this suffix, are the document. Everything else
# is carried through as opaque payload.
indexPrefix: str = "Index/"
iwaSuffix: str = ".iwa"


class ContainerError(RuntimeError):
    """A `.numbers` file whose container could not be read or written."""


@dataclass(frozen=True)
class MemberInfo:
    """The zip-level metadata for one member, carried so the archive rewrites exactly.

    Every field here was found the hard way: the byte-identical round trip failed
    until each one was preserved. Python's own defaults disagree with what Numbers
    writes on three of them, it stamps `createSystem` 3 (Unix) where Numbers
    writes 0 (MS-DOS), `createVersion` 20 where Numbers writes 62, and an epoch
    date of 1980 where the file carries its real timestamp. None of those change
    whether the file opens; all of them change its bytes.
    """

    name: str
    compressType: int
    dateTime: tuple[int, int, int, int, int, int]
    createSystem: int
    createVersion: int
    extractVersion: int
    flagBits: int
    internalAttr: int
    externalAttr: int
    extra: bytes


@dataclass(frozen=True)
class StoredMember:
    """A zip member that is not part of the document, kept exactly as found.

    The preview image and metadata files travel unchanged, so they are held as
    bytes rather than modeled.
    """

    name: str
    data: bytes


@dataclass
class NumbersPackage:
    """One `.numbers` document: its IWA members, its other files, and their order.

    `members` carries every member's zip metadata in the order the archive listed
    them, and is the single source of both ordering and header details. Zip has no
    required ordering, so rewriting alphabetically would still open in Numbers,
    and would still differ byte for byte from the input, which is the property this
    library is built to keep.
    """

    iwaFiles: list[IWAFile] = field(default_factory=list)
    otherMembers: list[StoredMember] = field(default_factory=list)
    members: list[MemberInfo] = field(default_factory=list)

    def iwaFile(self, name: str) -> IWAFile:
        """Return one IWA member by its full member name, or raise."""
        for candidate in self.iwaFiles:
            if candidate.name == name:
                return candidate
        raise ContainerError(f"No IWA member named {name!r} in this document.")


def isDocumentMember(name: str) -> bool:
    """Report whether a zip member is one of the document's IWA files."""
    return name.startswith(indexPrefix) and name.endswith(iwaSuffix)


def readPackage(path: Path) -> NumbersPackage:
    """Read a `.numbers` file into its members.

    Members are read in the order the archive lists them, and that order is kept,
    because reproducing it is part of writing the file back unchanged.
    """
    if not path.is_file():
        raise ContainerError(f"No such file: {path}")

    package = NumbersPackage()
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                data = archive.read(info.filename)
                package.members.append(
                    MemberInfo(
                        name=info.filename,
                        compressType=info.compress_type,
                        dateTime=info.date_time,
                        createSystem=info.create_system,
                        createVersion=info.create_version,
                        extractVersion=info.extract_version,
                        flagBits=info.flag_bits,
                        internalAttr=info.internal_attr,
                        externalAttr=info.external_attr,
                        extra=info.extra,
                    )
                )
                if isDocumentMember(info.filename):
                    package.iwaFiles.append(readIWAFile(info.filename, data))
                else:
                    package.otherMembers.append(
                        StoredMember(name=info.filename, data=data)
                    )
    except zipfile.BadZipFile as exc:
        raise ContainerError(f"{path} is not a readable zip archive.") from exc
    return package


def toZipInfo(member: MemberInfo) -> zipfile.ZipInfo:
    """Rebuild a `ZipInfo` carrying every header field the member was read with.

    Set field by field rather than through the constructor, which accepts only the
    name and date and silently supplies its own values for the rest.
    """
    info = zipfile.ZipInfo(member.name, date_time=member.dateTime)
    info.compress_type = member.compressType
    info.create_system = member.createSystem
    info.create_version = member.createVersion
    info.extract_version = member.extractVersion
    info.flag_bits = member.flagBits
    info.internal_attr = member.internalAttr
    info.external_attr = member.externalAttr
    info.extra = member.extra
    return info


def writePackage(package: NumbersPackage, path: Path) -> None:
    """Write a package back to a `.numbers` file.

    Members go out in their original order, each with the storage method it was
    read with. An IWA member that has not been modified is written from the bytes
    it was read from, so a document read and written with no change is identical
    to its input.
    """
    iwaByName = {iwaFile.name: iwaFile for iwaFile in package.iwaFiles}
    otherByName = {member.name: member for member in package.otherMembers}

    try:
        with zipfile.ZipFile(path, "w") as archive:
            for info in package.members:
                if info.name in iwaByName:
                    data = writeIWAFile(iwaByName[info.name])
                elif info.name in otherByName:
                    data = otherByName[info.name].data
                else:
                    raise ContainerError(
                        f"{info.name!r} is listed among the members but is held as "
                        "neither an IWA file nor a stored member."
                    )
                archive.writestr(toZipInfo(info), data)
    except OSError as exc:
        raise ContainerError(f"Could not write {path}: {exc}") from exc

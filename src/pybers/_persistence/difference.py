#!/usr/bin/env python3
"""\
What two packages hold differently, member by member and archive by archive.

The one owner of package comparison. The round-trip tests assert that nothing
differs, and scripts/golden-confirm.py lists what a copy Numbers saved changed, so
both read the same answer rather than two implementations of it.

An archive differs when any part of it does, every message and its `ArchiveInfo`
included, since a changed object reference is as much a change as a changed body.

UPDATES
2026-09-17  Written for PYB-94.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"

from dataclasses import dataclass

from .container import NumbersPackage
from .iwa import Archive
from .types import archiveTypes


@dataclass(frozen=True)
class PackageDifference:
    """One member or archive that is changed, added or removed in the second package.

    `identifier` and `typeName` are None for a whole member.
    """

    member: str
    identifier: int | None
    typeName: str | None
    change: str

    def __str__(self) -> str:
        """Read as one line of a report."""
        if self.identifier is None:
            return f"{self.member} {self.change}"
        archive = f"archive {self.identifier} ({self.typeName})"
        return f"{self.member} {archive} {self.change}"


def readTypeName(archive: Archive) -> str:
    """Name an archive's message type, or its bare type identifier when unregistered."""
    typeId = archive.messages[0].typeId if archive.messages else -1
    messageClass = archiveTypes.get(typeId)
    return messageClass.DESCRIPTOR.full_name if messageClass else f"type {typeId}"


def classifyChange(before: object, after: object) -> str | None:
    """Return how a keyed item changed between packages, or None when it did not."""
    if before is None:
        return "added"
    if after is None:
        return "removed"
    return None if before == after else "changed"


def listPackageDifferences(
    before: NumbersPackage, after: NumbersPackage
) -> list[PackageDifference]:
    """List every member and archive the second package holds differently."""
    differences: list[PackageDifference] = []
    beforeOther = {member.name: member.data for member in before.otherMembers}
    afterOther = {member.name: member.data for member in after.otherMembers}
    for name in sorted(beforeOther.keys() | afterOther.keys()):
        change = classifyChange(beforeOther.get(name), afterOther.get(name))
        if change is not None:
            differences.append(PackageDifference(name, None, None, change))

    beforeFiles = {iwaFile.name: iwaFile for iwaFile in before.iwaFiles}
    afterFiles = {iwaFile.name: iwaFile for iwaFile in after.iwaFiles}
    for name in sorted(beforeFiles.keys() | afterFiles.keys()):
        if name not in beforeFiles or name not in afterFiles:
            change = "added" if name not in beforeFiles else "removed"
            differences.append(PackageDifference(name, None, None, change))
            continue
        beforeArchives = {a.identifier: a for a in beforeFiles[name].archives}
        afterArchives = {a.identifier: a for a in afterFiles[name].archives}
        for identifier in sorted(beforeArchives.keys() | afterArchives.keys()):
            old, new = beforeArchives.get(identifier), afterArchives.get(identifier)
            change = classifyChange(old, new)
            named = old if old is not None else new
            if change is not None and named is not None:
                differences.append(
                    PackageDifference(name, identifier, readTypeName(named), change)
                )
    return differences

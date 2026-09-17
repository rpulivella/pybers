#!/usr/bin/env python3
"""\
Creating an archive, a member and a component, and registering all three.

The sweep pins the rule the registry is built on against every file Numbers wrote:
a component's strong external references are exactly what its archives reference in
other components. A registry that derived them any other way would agree with itself
and disagree with Numbers, which no round trip through pybers alone could show.

UPDATES
2026-09-14  Written for PYB-63.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/14"

from pathlib import Path

import pytest

from conftest import allDocuments, findDocumentPath, readArchiveBodies
from pybers._generated import TSPArchiveMessages_pb2 as tspArchive
from pybers._persistence import readPackage, writePackage
from pybers._persistence.container import ContainerError
from pybers._persistence.iwa import IWAError, archiveCreate
from pybers._persistence.metadata import (
    MetadataError,
    PackageRegistry,
    memberNameFor,
)

tileTypeId: int = 6002
documentComponent: int = 1


def readRegistry(name: str = "00-baseline") -> PackageRegistry:
    """Return the registry of a freshly read document."""
    return PackageRegistry(readPackage(findDocumentPath(name)))


def buildTileInfo(identifier: int, references: list[int]) -> tspArchive.ArchiveInfo:
    """Return an `ArchiveInfo` for one tile message naming the given references."""
    info = tspArchive.ArchiveInfo(identifier=identifier)
    message = info.message_infos.add(type=tileTypeId, length=0)
    message.version.extend([1, 0, 5])
    message.object_references.extend(references)
    return info


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryStrongExternalReferenceIsWhatTheArchivesReference(path: Path) -> None:
    found = PackageRegistry(readPackage(path))

    for identifier, component in found.components.items():
        stored = {
            (reference.component_identifier, reference.object_identifier)
            for reference in component.external_references
            if not reference.is_weak
        }
        assert found.strongReferencesDerive(identifier) == stored, component.locator


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryArchiveOutsideTheRegistryBelongsToAComponent(path: Path) -> None:
    package = readPackage(path)
    found = PackageRegistry(package)

    unplaced = [
        (iwaFile.name, archive.identifier)
        for iwaFile in package.iwaFiles
        if iwaFile is not found.metadataFile
        for archive in iwaFile.archives
        if archive.identifier not in found.componentOf
    ]
    assert unplaced == []


def testAnAllocatedIdentifierIsNewAndTheNextIsHigher() -> None:
    found = readRegistry()
    used = set(found.componentOf) | {found.metadata.last_object_identifier}

    first = found.identifierAllocate()
    second = found.identifierAllocate()

    assert first > max(used)
    assert second == first + 1


def testACreatedComponentSurvivesBeingWrittenAndRead(tmp_path: Path) -> None:
    found = readRegistry()
    identifier = found.identifierAllocate()
    root = archiveCreate(buildTileInfo(identifier, [documentComponent]), [b""])

    found.componentAdd(root, "Tables/Tile")
    found.save()
    destination = tmp_path / "created.numbers"
    writePackage(found.package, destination)

    reread = PackageRegistry(readPackage(destination))
    component = reread.components[identifier]
    assert component.locator == f"Tables/Tile-{identifier}"
    assert reread.componentOf[identifier] == identifier
    assert reread.metadata.last_object_identifier == identifier
    assert reread.strongReferencesDerive(identifier) == {(documentComponent, 0)}
    assert [
        (reference.component_identifier, reference.object_identifier)
        for reference in component.external_references
    ] == [(documentComponent, 0)]


def testCreatingAComponentLeavesEveryOtherArchiveUnchanged(tmp_path: Path) -> None:
    source = findDocumentPath("00-baseline")
    found = readRegistry()
    root = archiveCreate(buildTileInfo(found.identifierAllocate(), []), [b""])

    found.componentAdd(root, "Tables/Tile")
    found.save()
    destination = tmp_path / "created.numbers"
    writePackage(found.package, destination)

    metadataMember = found.metadataFile.name
    before = [
        body for body in readArchiveBodies(readPackage(source))
        if body[0] != metadataMember
    ]
    after = [
        body for body in readArchiveBodies(readPackage(destination))
        if body[0] != metadataMember and body[1] != root.identifier
    ]
    assert after == before


def testAnArchiveAddedToAnExistingComponentIsRegisteredThere() -> None:
    found = readRegistry()
    engine = next(
        identifier for identifier, component in found.components.items()
        if component.preferred_locator == "CalculationEngine"
    )
    identifier = found.identifierAllocate()
    tile = next(
        identifier for identifier, component in found.components.items()
        if component.preferred_locator == "Tables/Tile"
    )

    found.archiveAdd(engine, archiveCreate(buildTileInfo(identifier, [tile]), [b""]))
    found.save()

    assert found.componentOf[identifier] == engine
    assert (tile, 0) in {
        (reference.component_identifier, reference.object_identifier)
        for reference in found.components[engine].external_references
    }


def testAWeakReferenceIsRecordedWeakAndNamesTheObject() -> None:
    found = readRegistry()
    engine = next(
        identifier for identifier, component in found.components.items()
        if component.preferred_locator == "CalculationEngine"
    )
    sheet = next(
        identifier for identifier, component in found.componentOf.items()
        if component == documentComponent and identifier != documentComponent
    )

    found.weakReferenceAdd(engine, sheet)
    found.weakReferenceAdd(engine, sheet)

    matching = [
        reference for reference in found.components[engine].external_references
        if (reference.component_identifier, reference.object_identifier)
        == (documentComponent, sheet)
    ]
    assert len(matching) == 1
    assert matching[0].is_weak


def testAReferenceToAnObjectNoComponentHoldsIsRefused() -> None:
    found = readRegistry()

    with pytest.raises(MetadataError, match="belongs to no component"):
        found.weakReferenceAdd(documentComponent, 999_999_999)


def testAnArchiveIdentifierAlreadyHeldIsRefused() -> None:
    found = readRegistry()
    held = found.componentMember(documentComponent).archives[0].identifier

    with pytest.raises(IWAError, match="already holds"):
        found.archiveAdd(
            documentComponent, archiveCreate(buildTileInfo(held, []), [b""])
        )


def testAMemberNameAlreadyTakenIsRefused() -> None:
    package = readPackage(findDocumentPath("00-baseline"))

    with pytest.raises(ContainerError, match="already holds"):
        package.iwaFileAdd(memberNameFor("Document"))


def testAnArchiveGivenTheWrongNumberOfBodiesIsRefused() -> None:
    with pytest.raises(IWAError, match="declares 1 messages"):
        archiveCreate(buildTileInfo(1, []), [b"", b""])

#!/usr/bin/env python3
"""\
The package registry: which component holds each archive, and what it references.

`Index/Metadata.iwa` carries one `TSP.PackageMetadata`. Every IWA member is a
component in it, named by its locator, and each component lists the objects its
archives reference in OTHER components. A created archive that is missing from
either list is an object Numbers cannot place, so creating one goes through here.

**A strong external reference is derived, never chosen.** Measured across all 51
fixtures on 2026-09-14: every component's strong external references are exactly
the cross-component targets of its archives' `object_references`, naming the
object as 0 when it is the target component's own root. Only weak references are
stored beyond that, and no schema marks a reference weak, so those are stated by
the caller. See findings-10-creation.md.

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

from .._generated import TSPArchiveMessages_pb2 as tspArchive
from .._generated import TSPMessages_pb2 as tsp
from ..errors import PybersError
from .container import NumbersPackage, indexPrefix, iwaSuffix
from .iwa import Archive, IWAFile
from .types import archiveTypeId

packageMetadataTypeId: int = 11006

# The component every document roots at, whose version and save token a created
# component copies.
documentComponentId: int = 1


class MetadataError(PybersError, RuntimeError):
    """A package registry that is missing, or a registration it cannot make."""


def memberNameFor(locator: str) -> str:
    """Return the zip member a component locator names."""
    return f"{indexPrefix}{locator}{iwaSuffix}"


class PackageRegistry:
    """The one `TSP.PackageMetadata`, and every archive's component found from it.

    Registrations accumulate and are written by `save`, because a created archive
    may reference another created after it, and its external references can only
    be derived once both are placed.
    """

    def __init__(self, package: NumbersPackage) -> None:
        """Find the registry, and map every archive to the component holding it."""
        self.package = package
        found = [
            (iwaFile, archive)
            for iwaFile in package.iwaFiles
            for archive in iwaFile.archives
            if archiveTypeId(archive) == packageMetadataTypeId
        ]
        if len(found) != 1:
            raise MetadataError(
                f"Expected exactly one TSP.PackageMetadata, found {len(found)}, so a "
                "created archive would have no component to belong to."
            )
        self.metadataFile, archive = found[0]
        self.metadataIdentifier = archive.identifier
        self.metadata = tspArchive.PackageMetadata()
        self.metadata.ParseFromString(archive.messages[0].data)
        self.components = {
            component.identifier: component for component in self.metadata.components
        }
        byMember = {
            memberNameFor(component.locator or component.preferred_locator):
                component.identifier
            for component in self.metadata.components
        }
        self.componentOf: dict[int, int] = {
            held.identifier: byMember[iwaFile.name]
            for iwaFile in package.iwaFiles
            if iwaFile.name in byMember
            for held in iwaFile.archives
        }
        self.gained: set[int] = set()
        self.changed = False

    def identifierAllocate(self) -> int:
        """Return an object identifier no archive in this package has used."""
        highest = max(self.metadata.last_object_identifier, *self.componentOf)
        self.metadata.last_object_identifier = highest + 1
        self.changed = True
        return self.metadata.last_object_identifier

    def componentMember(self, identifier: int) -> IWAFile:
        """Return the IWA member holding a component."""
        component = self.components.get(identifier)
        if component is None:
            raise MetadataError(f"No component {identifier} in this package.")
        return self.package.iwaFile(
            memberNameFor(component.locator or component.preferred_locator)
        )

    def componentAdd(self, root: Archive, preferredLocator: str) -> IWAFile:
        """Create a component whose root is an archive, in a member of its own.

        The locator carries the root's identifier, which no other member can, since
        identifiers are never reused.
        """
        document = self.components.get(documentComponentId)
        if document is None:
            raise MetadataError("This package registers no document component.")
        locator = f"{preferredLocator}-{root.identifier}"
        component = self.metadata.components.add()
        component.identifier = root.identifier
        component.preferred_locator = preferredLocator
        component.locator = locator
        component.document_read_version.extend(document.document_read_version)
        component.document_write_version.extend(document.document_write_version)
        component.is_stored_outside_object_archive = False
        component.save_token = document.save_token
        self.components[root.identifier] = component
        member = self.package.iwaFileAdd(memberNameFor(locator))
        self.archiveAdd(root.identifier, root)
        return member

    def archiveAdd(self, componentId: int, archive: Archive) -> None:
        """Place a created archive in a component's member."""
        self.componentMember(componentId).archiveAdd(archive)
        self.componentOf[archive.identifier] = componentId
        self.gained.add(componentId)
        self.changed = True

    def weakReferenceAdd(self, componentId: int, target: int) -> None:
        """Record a weak reference from a component to an object in another."""
        self.referenceRecord(componentId, target, weak=True)

    def objectUuidAdd(self, componentId: int, objectId: int, uuid: tsp.UUID) -> None:
        """Record the UUID an object is known by across saves."""
        entry = self.components[componentId].object_uuid_map_entries.add()
        entry.identifier = objectId
        entry.uuid.CopyFrom(uuid)
        self.changed = True

    def strongReferencesDerive(self, componentId: int) -> set[tuple[int, int]]:
        """Return the external references a component's archives make, as stored.

        Each is (component, object), the object 0 when it is that component's root.
        A target in no component is refused, since nothing could resolve it.
        """
        derived: set[tuple[int, int]] = set()
        for archive in self.componentMember(componentId).archives:
            info = tspArchive.ArchiveInfo()
            info.ParseFromString(archive.infoBytes)
            for target in (
                target for message in info.message_infos
                for target in message.object_references
            ):
                derived.add(self.externalFor(target))
        return {pair for pair in derived if pair[0] != componentId}

    def externalFor(self, target: int) -> tuple[int, int]:
        """Return how another component names an object, as (component, object)."""
        targetComponent = self.componentOf.get(target)
        if targetComponent is None:
            raise MetadataError(
                f"Object {target} belongs to no component, so a reference to it "
                "cannot be registered."
            )
        return (targetComponent, 0 if target == targetComponent else target)

    def referenceRecord(self, componentId: int, target: int, weak: bool) -> None:
        """Add one external reference to a component unless it is already listed."""
        pair = self.externalFor(target)
        if pair[0] != componentId:
            self.referencePairRecord(componentId, pair, weak)

    def referencePairRecord(
        self, componentId: int, pair: tuple[int, int], weak: bool
    ) -> None:
        """Add a (component, object) reference, making a weak one strong if need be."""
        component = self.components[componentId]
        for existing in component.external_references:
            if (existing.component_identifier, existing.object_identifier) == pair:
                if not weak:
                    existing.ClearField("is_weak")
                return
        reference = component.external_references.add()
        reference.component_identifier = pair[0]
        if pair[1]:
            reference.object_identifier = pair[1]
        if weak:
            reference.is_weak = True
        self.changed = True

    def save(self) -> None:
        """Register what every gained component references, and write the registry.

        Writes nothing when nothing was registered, so an unchanged document still
        writes back byte for byte.
        """
        if not self.changed:
            return
        for componentId in sorted(self.gained):
            for pair in sorted(self.strongReferencesDerive(componentId)):
                self.referencePairRecord(componentId, pair, weak=False)
        self.gained.clear()
        self.metadataFile.messageReplace(
            self.metadataIdentifier, 0, self.metadata.SerializeToString()
        )


__all__ = ["MetadataError", "PackageRegistry", "memberNameFor"]

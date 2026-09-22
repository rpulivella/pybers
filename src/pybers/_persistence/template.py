#!/usr/bin/env python3
"""\
Archive templates: archives Numbers wrote, kept as text, and copied under new names.

A template file is one archive in protobuf text format. Its leading `#| ` lines
carry the component it belongs in and its `ArchiveInfo`, which is kept because the
info records which references are strong, and no schema says so. Everything after
them is the archive's message.

A template keeps the identifiers of the file it was taken from. Copying one maps
each of them either to a freshly allocated identifier, when the template set holds
that archive, or to an object the caller binds, such as a stylesheet. An identifier
that is neither is refused, since it names an object the target document may not
have.

UPDATES
2026-09-22  A placed copy reads back as the body it was placed with, for PYB-109.
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

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from google.protobuf import text_format
from google.protobuf.message import Message

from .._generated import TSPArchiveMessages_pb2 as tspArchive
from ..errors import PybersError
from .iwa import createArchive
from .metadata import PackageRegistry
from .types import archiveTypes

templateSuffix: str = ".txtpb"
headerMarker: str = "#| "
componentKey: str = "component: "
newComponentPrefix: str = "new "
referenceTypeName: str = "TSP.Reference"


class TemplateError(PybersError, RuntimeError):
    """A template that cannot be read, or copied into the document at hand."""


@dataclass(frozen=True, slots=True)
class ArchiveTemplate:
    """One archive as Numbers wrote it, under the identifiers it was written with."""

    role: str
    component: str
    info: tspArchive.ArchiveInfo
    body: Message


@dataclass(slots=True)
class ArchiveCopy:
    """A template copied under its new identifier, editable until it is placed."""

    template: ArchiveTemplate
    identifier: int
    body: Message


def readTemplate(path: Path) -> ArchiveTemplate:
    """Return the template one file holds, named by its role after the `NN-` prefix."""
    text = path.read_text(encoding="utf-8")
    header = [
        line[len(headerMarker):]
        for line in text.splitlines()
        if line.startswith(headerMarker)
    ]
    if not header or not header[0].startswith(componentKey):
        raise TemplateError(f"{path.name} does not open by naming its component.")
    info = text_format.Parse("\n".join(header[1:]), tspArchive.ArchiveInfo())
    if len(info.message_infos) != 1:
        raise TemplateError(
            f"{path.name} declares {len(info.message_infos)} messages, and a "
            "template holds exactly one."
        )
    messageClass = archiveTypes.get(info.message_infos[0].type)
    if messageClass is None:
        raise TemplateError(
            f"{path.name} holds type {info.message_infos[0].type}, which is not in "
            "the type registry."
        )
    return ArchiveTemplate(
        role=path.stem.split("-", 1)[1],
        component=header[0][len(componentKey):],
        info=info,
        body=text_format.Parse(text, messageClass()),
    )


def readTemplates(directory: Path) -> list[ArchiveTemplate]:
    """Return every template in a directory, in the order their prefixes give."""
    templates = [
        readTemplate(path) for path in sorted(directory.glob(f"*{templateSuffix}"))
    ]
    if not templates:
        raise TemplateError(f"{directory} holds no templates.")
    return templates


def remapReferences(message: Message, mapping: Mapping[int, int]) -> None:
    """Rewrite every reference a message holds through a mapping, in place."""
    for descriptor, value in message.ListFields():
        if descriptor.message_type is None:
            continue
        if descriptor.message_type.GetOptions().map_entry:
            items = list(value.values())
            if items and not isinstance(items[0], Message):
                continue
        else:
            items = list(value) if descriptor.is_repeated else [value]
        for item in items:
            if descriptor.message_type.full_name == referenceTypeName:
                item.identifier = mapIdentifier(item.identifier, mapping)
            else:
                remapReferences(item, mapping)


def mapIdentifier(identifier: int, mapping: Mapping[int, int]) -> int:
    """Return what a template identifier becomes, or refuse one nothing binds."""
    mapped = mapping.get(identifier)
    if mapped is None:
        raise TemplateError(
            f"A template references object {identifier}, which is neither in the "
            "template set nor bound to an object in this document."
        )
    return mapped


@dataclass(slots=True)
class TemplateCopies:
    """A template set copied under fresh identifiers, keyed by role, not yet placed."""

    copies: dict[str, ArchiveCopy]
    mapping: dict[int, int]

    def __getitem__(self, role: str) -> ArchiveCopy:
        """Return the copy of one role, or refuse naming the roles there are."""
        copy = self.copies.get(role)
        if copy is None:
            raise TemplateError(
                f"No template plays the role {role!r}; the roles are "
                f"{sorted(self.copies)}."
            )
        return copy

    def place(
        self, registry: PackageRegistry, components: Mapping[str, int]
    ) -> None:
        """Create every copy as an archive in the component its template names.

        A template naming `new <locator>` is the root of a component of its own,
        created here in a member of its own.
        """
        for copy in self.copies.values():
            component = copy.template.component
            componentId = components.get(component)
            if componentId is None and not component.startswith(newComponentPrefix):
                raise TemplateError(
                    f"The {copy.template.role!r} template belongs in "
                    f"{component!r}, which was not provided."
                )
            info = tspArchive.ArchiveInfo()
            info.CopyFrom(copy.template.info)
            info.identifier = copy.identifier
            for message in info.message_infos:
                remapped = [
                    mapIdentifier(target, self.mapping)
                    for target in message.object_references
                ]
                del message.object_references[:]
                message.object_references.extend(remapped)
            archive = createArchive(info, [copy.body.SerializeToString()])
            if componentId is None:
                registry.componentAdd(archive, component[len(newComponentPrefix):])
            else:
                registry.archiveAdd(componentId, archive, copy.body)


def copyTemplates(
    registry: PackageRegistry,
    templates: list[ArchiveTemplate],
    bound: Mapping[int, int],
) -> TemplateCopies:
    """Copy a template set under fresh identifiers, for editing before it is placed.

    Every reference is remapped here, and every strong reference is checked, so an
    unbound object is refused before anything is allocated in the file.
    """
    internal = {template.info.identifier for template in templates}
    for template in templates:
        for message in template.info.message_infos:
            for target in message.object_references:
                if target not in internal and target not in bound:
                    mapIdentifier(target, bound)
    mapping = dict(bound)
    for template in templates:
        mapping[template.info.identifier] = registry.identifierAllocate()
    copies: dict[str, ArchiveCopy] = {}
    for template in templates:
        body = type(template.body)()
        body.CopyFrom(template.body)
        remapReferences(body, mapping)
        copies[template.role] = ArchiveCopy(
            template=template,
            identifier=mapping[template.info.identifier],
            body=body,
        )
    return TemplateCopies(copies=copies, mapping=mapping)

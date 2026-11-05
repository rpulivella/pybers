#!/usr/bin/env python3
"""\
The JSON Schema of the JSON form, generated from the types the form is built from.

Built from the same field list and leaf rules the tree walker uses, so the schema
cannot describe a key the writer does not write. Every dataclass and enum is one
entry under `$defs` by its own name, every object refuses a key it does not
describe, and a field a reader may leave out, one with a default or one marked
read-only, is the only kind not required. A field whose type another key decides
states each choice as an `if` and a `then`. `schema.json` beside this module is this
output, committed, and a test fails when the two differ.

Private. Part of the JSON form's mechanism.

UPDATES
2026-10-24  Written for PYB-259.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

import dataclasses
import typing
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any

from pybers._family import findFamilyDiscriminator
from pybers.interchange._envelope import JsonForm
from pybers.interchange._leaves import findLeafRule
from pybers.interchange._tree import (
    JsonFormDefinitionError,
    encodeTree,
    findFieldTypes,
    findJsonFormChoices,
    isRequired,
    jsonFormConst,
    jsonFormReadOnly,
    listFormFields,
    listUnionMembers,
)

schemaPath: Path = Path(__file__).with_name("schema.json")
schemaDialect: str = "https://json-schema.org/draft/2020-12/schema"


def buildJsonFormSchema() -> dict[str, Any]:
    """Return the JSON Schema of every shape the JSON form takes."""
    definitions: dict[str, Any] = {}
    root = buildTypeSchema(JsonForm, definitions)
    return {
        "$schema": schemaDialect,
        "title": "pybers JSON form",
        "description": (
            "A Numbers document, or a sheet, table, range or cell of one, as pybers "
            "writes and reads it. See docs/decisions.md for the rule each value "
            "follows."
        ),
        **root,
        "$defs": dict(sorted(definitions.items())),
    }


def buildTypeSchema(declared: object, definitions: dict[str, Any]) -> dict[str, Any]:
    """Return the schema of one declared type, adding what it names to `definitions`."""
    members = listUnionMembers(declared)
    if len(members) > 1:
        return {"anyOf": [buildTypeSchema(each, definitions) for each in members]}
    declared = members[0]
    if declared is type(None):
        return {"type": "null"}
    if isinstance(declared, sentinel):
        return {"const": repr(declared)}
    origin = typing.get_origin(declared)
    if origin in (tuple, list):
        item = typing.get_args(declared)[0]
        return {"type": "array", "items": buildTypeSchema(item, definitions)}
    if origin in (frozendict, dict, Mapping):
        keyType, valueType = typing.get_args(declared)
        described: dict[str, Any] = {
            "type": "object",
            "additionalProperties": buildTypeSchema(valueType, definitions),
        }
        if keyType is int:
            described["propertyNames"] = {"pattern": "^-?[0-9]+$"}
        return described
    if not isinstance(declared, type):
        raise JsonFormDefinitionError(f"pybers has no JSON schema for {declared!r}.")
    return buildConcreteSchema(declared, definitions)


def buildConcreteSchema(declared: type, definitions: dict[str, Any]) -> dict[str, Any]:
    """Return the schema of one concrete type, a definition for a dataclass or enum."""
    if declared is bool:
        return {"type": "boolean"}
    if declared is int:
        return {"type": "integer"}
    if declared is str:
        return {"type": "string"}
    rule = findLeafRule(declared)
    if rule is not None:
        return dict(rule.schema)
    reference = {"$ref": f"#/$defs/{declared.__name__}"}
    if declared.__name__ in definitions:
        return reference
    if issubclass(declared, Enum):
        definitions[declared.__name__] = {
            "enum": [each.value for each in declared]
        }
        return reference
    if dataclasses.is_dataclass(declared):
        definitions[declared.__name__] = {}
        definitions[declared.__name__] = buildDataclassSchema(declared, definitions)
        return reference
    raise JsonFormDefinitionError(f"pybers has no JSON schema for {declared.__name__}.")


def buildDataclassSchema(form: type, definitions: dict[str, Any]) -> dict[str, Any]:
    """Return an object's schema: its keys in order, refusing any it does not write."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    discriminator = findFamilyDiscriminator(form)
    if discriminator is not None:
        properties[discriminator] = {"const": getattr(form, discriminator).value}
        required.append(discriminator)
    fieldTypes = findFieldTypes(form)
    for each in listFormFields(form):
        declared = fieldTypes[each.name]
        readOnly = each.metadata.get(jsonFormReadOnly, False)
        if readOnly:
            declared = typing.Union[*(  # noqa: UP007
                member for member in listUnionMembers(declared)
                if member is not type(None)
            )]
        described = buildTypeSchema(declared, definitions)
        if jsonFormConst in each.metadata:
            described = {**described, "const": each.metadata[jsonFormConst]}
        if readOnly:
            described = {**described, "readOnly": True}
        properties[each.name] = described
        if isRequired(each) and not readOnly:
            required.append(each.name)
    described = {
        "type": "object",
        "description": (form.__doc__ or "").strip().splitlines()[0],
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    conditions = [
        {
            "if": {"properties": {key: {"const": encodeTree(choice)}}},
            "then": {"properties": {name: buildTypeSchema(chosen | None, definitions)}},
        }
        for name, (key, types) in findJsonFormChoices(form).items()
        for choice, chosen in types.items()
    ]
    return {**described, "allOf": conditions} if conditions else described


__all__ = ["buildJsonFormSchema", "schemaDialect", "schemaPath"]

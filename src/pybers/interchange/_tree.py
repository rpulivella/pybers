#!/usr/bin/env python3
"""\
A model value turned into the plain tree JSON holds, and that tree turned back.

Writing follows the value's own type. Reading follows the type a field declares, so a
union is resolved by what the tree holds: a sentinel by its name, an enum by its
value, a closed family by its discriminator, and any other dataclass by the exact
keys it writes. A union whose members read alike from a string, a date beside text,
is resolved by the enclosing form's `jsonFormChoices`, which names the key whose
value decides the field's type, so the schema states the same choice.

A dataclass writes its public fields that take part in equality, and a field marked
`jsonFormKept` beside them, so a back-pointer or provenance never reaches the form.

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
import types
import typing
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from functools import cache
from typing import Any, TypeAliasType, Union

from pybers._family import findFamilyDiscriminator
from pybers.errors import PybersError
from pybers.interchange._leaves import (
    JsonFormError,
    Tree,
    findLeafRule,
    formatTreeKind,
)

# Field metadata: a field the form writes although equality ignores it, and one
# the form writes for reading only, which a reader may leave out.
jsonFormKept: str = "jsonFormKept"
jsonFormReadOnly: str = "readOnly"
# Field metadata: the one value a field may hold, such as the form's version.
jsonFormConst: str = "const"


class JsonFormDefinitionError(PybersError, RuntimeError):
    """A model type the JSON form cannot express, which is a defect in pybers."""


def unwrapAlias(declared: object) -> object:
    """Return what a `type` alias stands for, or the type itself."""
    while isinstance(declared, TypeAliasType):
        declared = declared.__value__
    return declared


def listUnionMembers(declared: object) -> tuple[object, ...]:
    """Return a declared type's union members, each alias unwrapped, or the type."""
    declared = unwrapAlias(declared)
    if typing.get_origin(declared) in (Union, types.UnionType):
        return tuple(
            member for each in typing.get_args(declared)
            for member in listUnionMembers(each)
        )
    return (declared,)


@cache
def findFieldTypes(form: type) -> dict[str, object]:
    """Return each field's declared type, resolved once per dataclass."""
    return typing.get_type_hints(form)


@cache
def listFormFields(form: type) -> tuple[dataclasses.Field[Any], ...]:
    """Return the fields a dataclass writes to the JSON form, in declared order."""
    return tuple(
        each for each in dataclasses.fields(form)
        if not each.name.startswith("_")
        and (each.compare or each.metadata.get(jsonFormKept, False))
    )


def isRequired(each: dataclasses.Field[Any]) -> bool:
    """Report whether a reader must find a field, which it need not with a default."""
    return (
        each.default is dataclasses.MISSING
        and each.default_factory is dataclasses.MISSING
    )


def encodeTree(value: object) -> Tree:
    """Return the plain tree a value is written as."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        return encodeTree(value.value)
    if isinstance(value, sentinel):
        return repr(value)
    if isinstance(value, str | int):
        return value
    rule = findLeafRule(type(value))
    if rule is not None:
        return rule.encode(value)
    if isinstance(value, Mapping):
        return {str(encodeTree(key)): encodeTree(each) for key, each in value.items()}
    if isinstance(value, tuple | list):
        return [encodeTree(each) for each in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return encodeDataclass(value)
    raise JsonFormDefinitionError(
        f"pybers has no JSON form for {type(value).__name__}."
    )


def encodeDataclass(value: object) -> dict[str, Tree]:
    """Return a dataclass as an object, a family member's discriminator first."""
    form: type = type(value)
    tree: dict[str, Tree] = {}
    discriminator = findFamilyDiscriminator(form)
    if discriminator is not None:
        tree[discriminator] = encodeTree(getattr(form, discriminator))
    for each in listFormFields(form):
        tree[each.name] = encodeTree(getattr(value, each.name))
    return tree


def decodeTree(tree: Tree, declared: object, path: str) -> Any:
    """Return the value a tree holds, read as the type declared for it."""
    members = listUnionMembers(declared)
    if len(members) > 1:
        return decodeUnion(tree, members, path)
    declared = members[0]
    if declared is type(None):
        if tree is not None:
            raise JsonFormError(f"{path} must be null, and is {formatTreeKind(tree)}.")
        return None
    if isinstance(declared, sentinel):
        if tree != repr(declared):
            raise JsonFormError(f"{path} must be {repr(declared)!r}.")
        return declared
    origin = typing.get_origin(declared)
    if origin in (tuple, list):
        return decodeSequence(tree, declared, origin, path)
    if origin in (frozendict, dict, Mapping):
        return decodeMapping(tree, declared, path)
    if not isinstance(declared, type):
        raise JsonFormDefinitionError(f"pybers has no JSON form for {declared!r}.")
    return decodeType(tree, declared, path)


def decodeType(tree: Tree, declared: type, path: str) -> Any:
    """Return the value a tree holds, read as one concrete type."""
    if issubclass(declared, Enum):
        try:
            return declared(tree)
        except ValueError as exc:
            choices = ", ".join(repr(each.value) for each in declared)
            raise JsonFormError(f"{path} must be one of {choices}.") from exc
    if declared is bool:
        if not isinstance(tree, bool):
            raise JsonFormError(
                f"{path} must be a boolean, and is {formatTreeKind(tree)}."
            )
        return tree
    if declared is int:
        number = findLeafRule(Decimal)
        assert number is not None
        whole = number.decode(tree, path)
        if whole != whole.to_integral_value():
            raise JsonFormError(f"{path} must be a whole number, and is {whole}.")
        return int(whole)
    if declared is str:
        if not isinstance(tree, str):
            raise JsonFormError(
                f"{path} must be a string, and is {formatTreeKind(tree)}."
            )
        return tree
    rule = findLeafRule(declared)
    if rule is not None:
        return rule.decode(tree, path)
    if dataclasses.is_dataclass(declared):
        return decodeDataclass(tree, declared, path)
    raise JsonFormDefinitionError(f"pybers has no JSON form for {declared.__name__}.")


def decodeSequence(tree: Tree, declared: object, origin: type, path: str) -> Any:
    """Return an array read as a tuple or a list of the declared item type."""
    if not isinstance(tree, list):
        raise JsonFormError(f"{path} must be an array, and is {formatTreeKind(tree)}.")
    arguments = typing.get_args(declared)
    item = arguments[0]
    items = [decodeTree(each, item, f"{path}[{index}]")
             for index, each in enumerate(tree)]
    return tuple(items) if origin is tuple else items


def decodeMapping(tree: Tree, declared: object, path: str) -> Any:
    """Return an object read as a mapping, its keys read back to the declared type."""
    if not isinstance(tree, dict):
        raise JsonFormError(f"{path} must be an object, and is {formatTreeKind(tree)}.")
    keyType, valueType = typing.get_args(declared)
    read = {
        decodeKey(key, keyType, f"{path}.{key}"):
            decodeTree(each, valueType, f"{path}.{key}")
        for key, each in tree.items()
    }
    return frozendict(read) if typing.get_origin(declared) is frozendict else read


def decodeKey(key: str, keyType: object, path: str) -> Any:
    """Return an object's key as its declared type, an integer read from its text."""
    if keyType is int:
        if not key.lstrip("-").isdigit():
            raise JsonFormError(f"{path} must be keyed by a whole number.")
        return int(key)
    return decodeTree(key, keyType, path)


def decodeDataclass(tree: Tree, form: type, path: str) -> Any:
    """Return an object read as a dataclass, refusing a key it does not write."""
    if not isinstance(tree, dict):
        raise JsonFormError(f"{path} must be an object, and is {formatTreeKind(tree)}.")
    discriminator = findFamilyDiscriminator(form)
    known: set[str | None] = {each.name for each in listFormFields(form)}
    if discriminator is not None:
        expected = encodeTree(getattr(form, discriminator))
        if tree.get(discriminator) != expected:
            raise JsonFormError(f"{path}.{discriminator} must be {expected!r}.")
        known.add(discriminator)
    unknown = sorted(set(tree) - known)
    if unknown:
        raise JsonFormError(f"{path} has no key {unknown[0]!r}.")
    fieldTypes = findFieldTypes(form)
    choices = findJsonFormChoices(form)
    values: dict[str, Any] = {}
    for each in listFormFields(form):
        where = f"{path}.{each.name}"
        if each.name not in tree:
            if isRequired(each):
                raise JsonFormError(f"{where} is missing.")
            continue
        required = each.metadata.get(jsonFormConst)
        if required is not None and tree[each.name] != required:
            raise JsonFormError(f"{where} must be {required!r}.")
        declared = fieldTypes[each.name]
        if each.name in choices:
            declared = chooseFieldType(tree, *choices[each.name], where)
        values[each.name] = decodeTree(tree[each.name], declared, where)
    return form(**values)


def findJsonFormChoices(form: type) -> Mapping[str, tuple[str, Mapping[Any, type]]]:
    """Return the fields whose type another key's value decides, by field name."""
    return getattr(form, "jsonFormChoices", frozendict())


def chooseFieldType(
    tree: dict[str, Tree], key: str, types: Mapping[Any, type], path: str
) -> object:
    """Return the type a field is read as, which another key's value decides."""
    chosen = next((kind for kind in types if encodeTree(kind) == tree.get(key)), None)
    if chosen is None:
        raise JsonFormError(
            f"{path} is read by its {key}, which is missing or unknown."
        )
    return types[chosen] | None


def decodeUnion(tree: Tree, members: tuple[object, ...], path: str) -> Any:
    """Return a tree read as whichever union member it holds, refusing an ambiguity."""
    if tree is None and type(None) in members:
        return None
    if isinstance(tree, str):
        for member in members:
            if isinstance(member, sentinel) and tree == repr(member):
                return member
    candidates = [member for member in members if checkTreeFits(tree, member)]
    if isinstance(tree, dict):
        candidates = selectDataclasses(tree, candidates)
    if len(candidates) == 1:
        return decodeTree(tree, candidates[0], path)
    if not candidates:
        accepted = " or ".join(dict.fromkeys(map(formatMemberKind, members)))
        raise JsonFormError(
            f"{path} must be {accepted}, and is {formatTreeKind(tree)}."
        )
    raise JsonFormDefinitionError(
        f"{path} could be any of {candidates}, and its form names none."
    )


def formatMemberKind(member: object) -> str:
    """Return a union member in the words an error message uses."""
    if member is type(None):
        return "null"
    if isinstance(member, sentinel):
        return repr(repr(member))
    origin = typing.get_origin(member)
    if origin in (tuple, list):
        return "an array"
    if origin in (frozendict, dict, Mapping) or dataclasses.is_dataclass(member):
        return "an object"
    if member is bool:
        return "a boolean"
    if member in (int, Decimal):
        return "a number"
    return "a string"


def checkTreeFits(tree: Tree, member: object) -> bool:
    """Report whether a union member could be read from a tree of this JSON kind."""
    if isinstance(member, sentinel) or member is type(None):
        return False
    origin = typing.get_origin(member)
    if origin in (tuple, list):
        return isinstance(tree, list)
    if origin in (frozendict, dict, Mapping) or dataclasses.is_dataclass(member):
        return isinstance(tree, dict)
    if not isinstance(member, type):
        return False
    if issubclass(member, Enum):
        return tree in {each.value for each in member}
    if member is bool:
        return isinstance(tree, bool)
    if member in (int, Decimal):
        return isinstance(tree, int | Decimal) and not isinstance(tree, bool)
    return isinstance(tree, str)


def selectDataclasses(tree: dict[str, Tree], candidates: list[object]) -> list[object]:
    """Return the dataclass members an object fits, by discriminator or by its keys."""
    narrowed = []
    for member in candidates:
        if not isinstance(member, type) or not dataclasses.is_dataclass(member):
            narrowed.append(member)
            continue
        discriminator = findFamilyDiscriminator(member)
        if discriminator is not None:
            if tree.get(discriminator) == encodeTree(getattr(member, discriminator)):
                narrowed.append(member)
            continue
        names = {each.name for each in listFormFields(member)}
        required = {each.name for each in listFormFields(member) if isRequired(each)}
        if required <= set(tree) <= names:
            narrowed.append(member)
    return narrowed


__all__ = [
    "JsonFormDefinitionError",
    "decodeTree",
    "encodeTree",
    "chooseFieldType",
    "findFieldTypes",
    "findJsonFormChoices",
    "isRequired",
    "jsonFormConst",
    "jsonFormKept",
    "jsonFormReadOnly",
    "listFormFields",
    "listUnionMembers",
    "unwrapAlias",
]

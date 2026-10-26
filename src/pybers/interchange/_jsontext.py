#!/usr/bin/env python3
"""\
A plain tree written as JSON text, and JSON text read back into one.

The standard library cannot write a `Decimal` as a bare JSON number, only as a
string or through a float, and either would lose what decimal128 keeps. This writer
emits each number as its own digits, `str(Decimal)` already being valid JSON for
every finite value, and reads every number back as a `Decimal`. Keys keep the order
the tree gives them, so one document always writes the same bytes.

Private. Part of the JSON form's mechanism, and the only JSON text pybers writes.

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

import json
from decimal import Decimal

from pybers.interchange._leaves import JsonFormError, Tree
from pybers.interchange._tree import JsonFormDefinitionError

indentUnit: str = "  "


def writeJsonText(tree: Tree) -> str:
    """Return a tree as indented JSON text, each number exactly its digits."""
    return "".join(listJsonParts(tree, 0))


def listJsonParts(tree: Tree, depth: int) -> list[str]:
    """Return the pieces of text one tree writes as, nested `depth` levels in."""
    match tree:
        case None:
            return ["null"]
        case bool():
            return ["true" if tree else "false"]
        case str():
            return [json.dumps(tree, ensure_ascii=False)]
        case int():
            return [str(tree)]
        case Decimal():
            if not tree.is_finite():
                raise JsonFormDefinitionError(f"JSON has no number for {tree}.")
            return [str(tree)]
        case list():
            return listContainerParts(
                "[", "]", [listJsonParts(each, depth + 1) for each in tree], depth
            )
        case dict():
            return listContainerParts("{", "}", [
                [json.dumps(key, ensure_ascii=False), ": ",
                 *listJsonParts(each, depth + 1)]
                for key, each in tree.items()
            ], depth)
    raise JsonFormDefinitionError(f"JSON has no form for {type(tree).__name__}.")


def listContainerParts(
    opening: str, closing: str, members: list[list[str]], depth: int
) -> list[str]:
    """Return an array or object's text, one member per line, empty ones on one line."""
    if not members:
        return [opening, closing]
    inner = "\n" + indentUnit * (depth + 1)
    parts = [opening]
    for index, member in enumerate(members):
        parts += [inner, *member, "," if index < len(members) - 1 else ""]
    return [*parts, "\n", indentUnit * depth, closing]


def readJsonText(text: str) -> Tree:
    """Return the tree JSON text holds, every number a Decimal and no key repeated."""
    try:
        tree: Tree = json.loads(
            text, parse_float=Decimal, parse_int=Decimal,
            parse_constant=refuseConstant, object_pairs_hook=refuseRepeatedKeys,
        )
    except json.JSONDecodeError as exc:
        raise JsonFormError(f"The text is not JSON: {exc}") from exc
    return tree


def refuseConstant(name: str) -> Decimal:
    """Refuse NaN and the infinities, which JSON does not define."""
    raise JsonFormError(f"JSON has no number {name}, and the text holds one.")


def refuseRepeatedKeys(pairs: list[tuple[str, Tree]]) -> dict[str, Tree]:
    """Return an object's members, refusing a key given twice."""
    read: dict[str, Tree] = {}
    for key, each in pairs:
        if key in read:
            raise JsonFormError(f"The key {key!r} appears twice in one object.")
        read[key] = each
    return read


__all__ = ["readJsonText", "writeJsonText"]

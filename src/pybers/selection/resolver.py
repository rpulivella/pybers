#!/usr/bin/env python3
"""\
The steps every resolver shares: placing components, comparing names, and meeting
conditions, whatever a selector selects from.

A document's resolver and the fonts' each walk their own parts and call these, so a
wildcard, a `:not()` or an attribute means one thing everywhere.

UPDATES
2026-11-24  Written for PYB-315, from the document resolver in `matching`.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

import operator
import re
from collections.abc import Callable, Sequence
from typing import Any

from pybers.addressing.text import escapeMarker, quoteReferenceText
from pybers.document.sheets import SelectionError
from pybers.errors import composeRefusal, formatChoiceList
from pybers.selection.scheme import (
    SelectorAttributeField,
    SelectorNameMatch,
    SelectorScheme,
)
from pybers.selection.selector import (
    SelectorAttribute,
    SelectorComponent,
    SelectorCondition,
    SelectorError,
    SelectorGroup,
    SelectorNegation,
    SelectorPseudoClass,
)

# What a loose name leaves out, so `AvenirNext` and `Avenir Next` compare equal.
looseIgnored: str = " -"
comparisons: frozendict[str, Callable[[Any, Any], bool]] = frozendict({
    "=": operator.eq, "<": operator.lt, "<=": operator.le, ">": operator.gt,
    ">=": operator.ge,
})


def normalizeName(name: str, nameMatch: SelectorNameMatch) -> str:
    """Return a name as its rule compares it, a loose one without spaces or hyphens."""
    if nameMatch is SelectorNameMatch.LOOSE:
        return name.translate({ord(each): None for each in looseIgnored})
    return name


def buildPattern(pattern: str, nameMatch: SelectorNameMatch) -> re.Pattern[str]:
    """Return a written name pattern as an expression, `*` and `?` its wildcards."""
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        index += 1
        if character == escapeMarker and index < len(pattern):
            character = pattern[index]
            index += 1
            literal = True
        else:
            literal = False
        if normalizeName(character, nameMatch) == "":
            continue
        if not literal and character in "*?":
            parts.append({"*": ".*", "?": "."}[character])
        else:
            parts.append(re.escape(character))
    caseless = nameMatch is not SelectorNameMatch.EXACT
    return re.compile("".join(parts), re.IGNORECASE if caseless else 0)


def matchName(
    component: SelectorComponent | None, name: str, nameMatch: SelectorNameMatch
) -> bool:
    """Report whether a name fits a component and none of its exclusions."""
    if component is None:
        return True
    compared = normalizeName(name, nameMatch)
    if component.pattern and not buildPattern(
        component.pattern, nameMatch
    ).fullmatch(compared):
        return False
    return not any(
        buildPattern(each, nameMatch).fullmatch(compared)
        for each in component.exclusions
    )


def placeComponents(
    group: SelectorGroup, positions: tuple[str, ...], filled: int, kind: str
) -> tuple[list[SelectorComponent | None], int]:
    """Return a component for each position, and the deepest reached.

    `filled` counts the positions an owner's selector reaches, from the last, so a
    selector given to a table fills its cells alone.
    """
    first = len(positions) - filled
    components = group.components
    if len(components) > filled:
        reached = positions[first:]
        raise SelectorError(composeRefusal(
            f"`{group}`", f"fills {len(components)} positions, and a selector given "
            f"to a {kind} fills at most {filled}, {formatChoiceList(reached)}",
            "Select from the document to reach more",
        ))
    placed: list[SelectorComponent | None] = [None] * len(positions)
    last = len(positions) - 1
    if group.fromRight:
        start = len(positions) - len(components)
        depth = last
    else:
        start = first
        depth = last if group.conditions else first + len(components) - 1
    for index, component in enumerate(components):
        placed[start + index] = component
    return placed, depth


def matchAttribute[ItemT](
    attribute: SelectorAttribute, field: SelectorAttributeField[ItemT], item: ItemT,
    nameMatch: SelectorNameMatch,
) -> bool:
    """Report whether an item meets one attribute condition."""
    found = field.read(item)
    if attribute.value is None or found is None:
        return found is not None and attribute.value is None
    wanted = attribute.value if field.parse is None else field.parse(attribute.value)
    if field.text and not attribute.exact:
        return (
            normalizeName(str(found), nameMatch).casefold()
            == normalizeName(str(wanted), nameMatch).casefold()
        )
    return comparisons[attribute.operator](found, wanted)


def matchConditions[ItemT](
    conditions: tuple[SelectorCondition, ...], scheme: SelectorScheme[ItemT],
    item: ItemT, matchPseudoClass: Callable[[str, str | None], bool],
) -> bool:
    """Report whether an item meets every condition, a pseudo-class by its owner."""
    for condition in conditions:
        match condition:
            case SelectorAttribute(name=name):
                met = matchAttribute(
                    condition, scheme.attributes[name], item, scheme.nameMatch
                )
            case SelectorPseudoClass(name=name, argument=argument):
                met = matchPseudoClass(name, argument)
            case SelectorNegation(alternatives=alternatives):
                met = not any(
                    matchConditions(each, scheme, item, matchPseudoClass)
                    for each in alternatives
                )
        if not met:
            return False
    return True


def listPresent(kind: str, names: Sequence[str]) -> str:
    """Return the part of a refusal listing the names present, to ask for one."""
    if not names:
        return f"It holds no {kind}s"
    return f"The {kind}s are {quoteChoices(names)}"


def quoteChoices(names: Sequence[str]) -> str:
    """Return names as prose, each quoted as reference text."""
    return formatChoiceList([quoteReferenceText(each) for each in names])


def refuseExactMiss(
    component: SelectorComponent | None, kind: str, within: str, fix: str
) -> None:
    """Refuse a component naming one thing exactly that nothing searched carries."""
    if component is None or not component.exact:
        return
    raise SelectionError(composeRefusal(
        quoteReferenceText(component.pattern), f"selects no {kind} in {within}", fix,
    ))


__all__ = [
    "buildPattern", "listPresent", "matchAttribute", "matchConditions", "matchName",
    "normalizeName", "placeComponents", "quoteChoices", "refuseExactMiss",
]

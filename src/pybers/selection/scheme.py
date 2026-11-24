#!/usr/bin/env python3
"""\
What a selector selects from: its positions, its conditions, and how it compares names.

One parser and one resolver read every selector, a document's or the typefaces', and a
`SelectorScheme` is all that differs between them, as a CSS selector reads the same
whatever document it is given.

UPDATES
2026-11-24  An attribute's `takes` says what its values are, for PYB-318.
2026-11-24  Written for PYB-315, from the attribute table `conditions` held.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto


class SelectorNameMatch(Enum):
    """How a name and a written pattern compare."""

    EXACT = auto()
    CASELESS = auto()
    # Ignoring case, spaces and hyphens, since a font's name is spelled many ways.
    LOOSE = auto()


@dataclass(frozen=True, slots=True)
class SelectorAttributeField[ItemT]:
    """What one attribute reads from an item, and the values it takes.

    `values` lists its choices, `parse` reads a free value, which `takes` describes in
    words, and neither means the attribute takes no value, `[conditional]`. An
    `ordered` one also compares with `<`, `<=`, `>` and `>=`, and a `text` one compares
    by the scheme's name rule.
    """

    read: Callable[[ItemT], object]
    values: tuple[str, ...] | None = None
    parse: Callable[[str], object] | None = None
    ordered: bool = False
    text: bool = False
    takes: str | None = None


@dataclass(frozen=True, slots=True)
class SelectorScheme[ItemT]:
    """What a selector selects from, and the examples its refusals give.

    The examples, such as `Q3::B3`, `[kind=number]` and `Q*:not(Q4)`, show a person
    the form in the terms of what is selected.
    """

    positions: tuple[str, ...]
    attributes: frozendict[str, SelectorAttributeField[ItemT]]
    pseudoClasses: frozendict[str, bool]
    nameMatch: SelectorNameMatch
    groupExample: str
    conditionExamples: tuple[str, ...]
    exclusionExample: str


__all__ = ["SelectorAttributeField", "SelectorNameMatch", "SelectorScheme"]

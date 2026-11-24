#!/usr/bin/env python3
"""\
A selector, the frozen form of the text every caller selects with, and its parser.

A selector has three positions, sheet, table and cells, joined by `::`. Written
plainly, its components fill them from the left, and after a leading `::` from the
right, as the groups of an IPv6 address do. Conditions follow the components, in
the manner of CSS: `[kind=number]`, `:empty`, `:nth-row(2n)` and `:not(...)`, which
also follows a component to remove names from it. Commas group several selectors.

A backslash makes the next character literal, so a sheet named `Q3, draft` is
written `Q3\\, draft`. A colon begins a condition only when a condition's name
follows it, which is why `B2:D9` stays a range.

UPDATES
2026-11-24  Read against a `SelectorScheme`, a document's unless given, and an
            attribute compares, quotes its value and takes the `s` flag, for PYB-315.
2026-11-23  Every message composed by its shape's composer, for PYB-307.
2026-11-18  A name's escapes are read through `addressing.text`, the one reference
            grammar, for PYB-267.
2026-11-03  Written for PYB-223.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

import re
from dataclasses import dataclass, field
from typing import Any

from pybers.addressing.text import (
    escapeMarker,
    normalizeWrittenText,
    referenceSeparator,
)
from pybers.errors import (
    PybersError,
    composeChoiceRefusal,
    composeRefusal,
    composeTextRefusal,
    formatChoiceList,
)
from pybers.selection.conditions import documentScheme, nthPattern, pseudoNegation
from pybers.selection.scheme import SelectorScheme

groupSeparator: str = ","
wildcards: str = "*?"
pseudoName: re.Pattern[str] = re.compile(r"[a-z][a-z-]*")
# `[name]`, `[name=value]`, `[weight>=600]`, or a quoted value an `s` flag ends.
attributePattern: re.Pattern[str] = re.compile(
    r'(?P<name>[^=<>"]*?)\s*(?:(?P<operator>>=|<=|=|>|<)\s*'
    r'(?:"(?P<quoted>(?:[^"\\]|\\.)*)"\s*(?P<flag>s)?|(?P<bare>[^"]*?)))?\s*'
)
quoteEscape: re.Pattern[str] = re.compile(r'\\(.)')
exactFlag: str = "s"
ordinals: frozendict[int, str] = frozendict({2: "third", 3: "fourth"})


class SelectorError(PybersError, ValueError):
    """A selector that does not parse, saying which part is wrong and where."""


@dataclass(frozen=True, slots=True)
class SelectorComponent:
    """One position's pattern as written, escapes kept, and the patterns it removes.

    An empty pattern, or `*`, means any.
    """

    pattern: str
    exclusions: tuple[str, ...] = ()

    @property
    def exact(self) -> bool:
        """Report whether this selects one thing, with no wildcard and no exclusion."""
        return (
            bool(self.pattern) and not findWildcard(self.pattern)
            and not self.exclusions
        )

    def __str__(self) -> str:
        removed = "".join(f":not({each})" for each in self.exclusions)
        return f"{self.pattern}{removed}"


@dataclass(frozen=True, slots=True)
class SelectorAttribute:
    """A condition on a modeled field, `[kind=number]`, or on its presence, `[kind]`.

    `[weight>=600]` compares, and a quoted value, `[postscript="Avenir-Book" s]`,
    may end in the `s` flag that compares it exactly, as in CSS.
    """

    name: str
    value: str | None = None
    operator: str = "="
    exact: bool = False
    quoted: bool = False

    def __str__(self) -> str:
        if self.value is None:
            return f"[{self.name}]"
        value = self.value.replace("\\", "\\\\").replace('"', '\\"')
        written = f'"{value}"' if self.quoted else self.value
        flag = f" {exactFlag}" if self.exact else ""
        return f"[{self.name}{self.operator}{written}{flag}]"


@dataclass(frozen=True, slots=True)
class SelectorPseudoClass:
    """A condition on a cell's state or position, `:empty` or `:nth-row(2n+1)`."""

    name: str
    argument: str | None = None

    def __str__(self) -> str:
        if self.argument is None:
            return f":{self.name}"
        return f":{self.name}({self.argument})"


@dataclass(frozen=True, slots=True)
class SelectorNegation:
    """A condition met when none of its alternatives is, `:not([kind=text], :empty)`."""

    alternatives: tuple[tuple[SelectorCondition, ...], ...]

    def __str__(self) -> str:
        written = ", ".join(
            "".join(str(each) for each in compound) for compound in self.alternatives
        )
        return f":{pseudoNegation}({written})"


type SelectorCondition = SelectorAttribute | SelectorPseudoClass | SelectorNegation


@dataclass(frozen=True, slots=True)
class SelectorGroup:
    """One selector of a comma-separated list: its components and its conditions."""

    components: tuple[SelectorComponent, ...]
    fromRight: bool = False
    conditions: tuple[SelectorCondition, ...] = ()

    def __str__(self) -> str:
        written = referenceSeparator.join(str(each) for each in self.components)
        lead = referenceSeparator if self.fromRight else ""
        return f"{lead}{written}{''.join(str(each) for each in self.conditions)}"


@dataclass(frozen=True, slots=True)
class Selector:
    """What a caller selects with: one or more groups, each matched on its own.

    The text form is what `parse` reads and `str` writes, so the library, the
    command line and an agent all hold the same thing.
    """

    groups: tuple[SelectorGroup, ...]
    scheme: SelectorScheme[Any] = field(default=documentScheme, repr=False)

    def __post_init__(self) -> None:
        if not self.groups:
            raise SelectorError(composeRefusal(
                "A selector", "holds no group",
                f"Write at least one, such as `{self.scheme.groupExample}`",
            ))

    @classmethod
    def parse(
        cls, text: str, scheme: SelectorScheme[Any] = documentScheme
    ) -> Selector:
        """Return the selector text writes, refusing it with the part and place.

        `scheme` is what it selects from, a document's sheets, tables and cells
        unless given.
        """
        example = scheme.groupExample
        if not isinstance(text, str):
            raise SelectorError(composeRefusal(
                repr(text), "is not a selector, since a selector is text",
                f"Write it as a string, such as '{example}'",
            ))
        if not text.strip():
            raise SelectorError(composeRefusal(
                "The selector", "is empty", f"Write one, such as `{example}`"
            ))
        groups = tuple(
            SelectorParser(text, start, end, scheme).groupParse()
            for start, end in splitTopLevel(text, 0, len(text))
        )
        return cls(groups, scheme)

    def __str__(self) -> str:
        return f"{groupSeparator} ".join(str(each) for each in self.groups)


type SelectorLike = Selector | str


def toSelector(
    selector: SelectorLike, scheme: SelectorScheme[Any] = documentScheme
) -> Selector:
    """Return a `Selector` for whichever of its forms was given.

    One parsed for something else is refused, since its conditions read other fields.
    """
    if not isinstance(selector, Selector):
        return Selector.parse(selector, scheme)
    if selector.scheme is not scheme:
        raise SelectorError(composeRefusal(
            f"`{selector}`", f"was parsed to select {formatChoiceList(
                selector.scheme.positions)}, not {formatChoiceList(scheme.positions)}",
            "Give it as text",
        ))
    return selector


def findWildcard(pattern: str) -> bool:
    """Report whether a written pattern holds an unescaped `*` or `?`."""
    escaped = False
    for character in pattern:
        if escaped:
            escaped = False
        elif character == escapeMarker:
            escaped = True
        elif character in wildcards:
            return True
    return False


def splitTopLevel(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Return the spans of text between commas outside brackets and parentheses."""
    spans: list[tuple[int, int]] = []
    depth = 0
    begin = index = start
    while index < end:
        character = text[index]
        if character == escapeMarker:
            index += 2
            continue
        if character in "[(":
            depth += 1
        elif character in "])":
            depth -= 1
        elif character == groupSeparator and depth == 0:
            spans.append((begin, index))
            begin = index + 1
        index += 1
    spans.append((begin, end))
    return spans


class SelectorParser:
    """Reads one group of a selector's text, keeping where each part sits."""

    def __init__(
        self, text: str, start: int, end: int, scheme: SelectorScheme[Any]
    ) -> None:
        self.text = text
        self.index = start
        self.end = end
        self.scheme = scheme

    def fault(
        self, cause: str, fix: str | None = None, index: int | None = None
    ) -> SelectorError:
        """Return the refusal of the part at an index, here unless given."""
        where = self.index if index is None else index
        return SelectorError(composeTextRefusal(self.text, where, cause, fix))

    def skipSpaces(self) -> None:
        while self.index < self.end and self.text[self.index] == " ":
            self.index += 1

    def startsWith(self, token: str) -> bool:
        return self.text.startswith(token, self.index) and (
            self.index + len(token) <= self.end
        )

    def findPseudoName(self) -> str | None:
        """Return the condition name after a single colon here, or None."""
        if not self.startsWith(":") or self.startsWith(referenceSeparator):
            return None
        found = pseudoName.match(self.text, self.index + 1, self.end)
        if found is None or found.group() not in {
            *self.scheme.pseudoClasses, pseudoNegation
        }:
            return None
        return found.group()

    def groupParse(self) -> SelectorGroup:
        """Return the group between this parser's start and end."""
        self.skipSpaces()
        if self.index >= self.end:
            raise self.fault("is an empty group", "Remove the extra comma")
        fromRight = self.startsWith(referenceSeparator)
        if fromRight:
            self.index += len(referenceSeparator)
        components: list[SelectorComponent] = []
        conditions: tuple[SelectorCondition, ...] = ()
        positions = self.scheme.positions
        while True:
            if len(components) == len(positions):
                raise self.fault(
                    f"begins a {ordinals[len(positions)]} position, and a selector "
                    f"holds only {formatChoiceList(positions)}",
                    f"Write it as `{referenceSeparator.join(positions)}`",
                )
            component = self.componentParse()
            components.append(component)
            if self.startsWith(referenceSeparator):
                self.index += len(referenceSeparator)
                continue
            break
        if self.index < self.end:
            conditions = self.conditionsParse()
        if fromRight and not any(each.pattern for each in components):
            components = []
        if not components and not conditions:
            raise self.fault(
                "selects nothing after its leading `::`",
                "Write a part after it, such as "
                f"`::{self.scheme.groupExample.rsplit(referenceSeparator)[-1]}`",
            )
        return SelectorGroup(tuple(components), fromRight, conditions)

    def componentParse(self) -> SelectorComponent:
        """Return one position's pattern, up to `::`, a condition or the group's end."""
        start = self.index
        written = ""
        exclusions: list[str] = []
        while self.index < self.end:
            character = self.text[self.index]
            if character == escapeMarker:
                if self.index + 1 >= self.end:
                    raise self.fault(
                        "ends in a backslash, which escapes nothing",
                        "Remove it, or write `\\\\` for a backslash",
                    )
                written += self.text[self.index:self.index + 2]
                self.index += 2
                continue
            if self.startsWith(referenceSeparator) or character == "[":
                break
            name = self.findPseudoName()
            if name == pseudoNegation and not self.negatesConditions():
                exclusions += self.exclusionsParse()
                continue
            if name is not None:
                break
            if character in "]()":
                raise self.fault(
                    f"holds `{character}`, which is not part of a name",
                    f"Write it as `\\{character}`",
                )
            written += character
            self.index += 1
        pattern = normalizeWrittenText(written)
        if not pattern and exclusions:
            raise self.fault(
                "holds a `:not()` that follows no name",
                "Write the name it removes from first, such as "
                f"`{self.scheme.exclusionExample}`", start,
            )
        return SelectorComponent(pattern, tuple(exclusions))

    def negatesConditions(self) -> bool:
        """Report whether the `:not(` here holds conditions rather than names."""
        inner = self.index + len(pseudoNegation) + 2
        while inner < self.end and self.text[inner] == " ":
            inner += 1
        return inner < self.end and self.text[inner] in "[:"

    def parenthesesRead(self) -> tuple[int, int]:
        """Return the span inside the parentheses opening here, and move past them."""
        if not self.startsWith("("):
            raise self.fault("lacks the `(` that opens a condition's argument")
        depth = 0
        index = self.index
        while index < self.end:
            character = self.text[index]
            if character == escapeMarker:
                index += 2
                continue
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    span = (self.index + 1, index)
                    self.index = index + 1
                    return span
            index += 1
        raise self.fault("opens a `(` that is never closed", "Close it with `)`")

    def exclusionsParse(self) -> list[str]:
        """Return the patterns a component's `:not(...)` removes."""
        self.index += 1 + len(pseudoNegation)
        start, end = self.parenthesesRead()
        patterns = []
        for begin, finish in splitTopLevel(self.text, start, end):
            pattern = self.text[begin:finish].strip()
            if not pattern:
                raise self.fault(
                    "holds a `:not()` that removes nothing",
                    "Write a name inside it, such as `:not(Q4)`", begin,
                )
            patterns.append(pattern)
        return patterns

    def conditionsParse(self) -> tuple[SelectorCondition, ...]:
        """Return the conditions from here to the group's end."""
        conditions: list[SelectorCondition] = []
        while True:
            self.skipSpaces()
            if self.index >= self.end:
                return tuple(conditions)
            if self.startsWith(referenceSeparator):
                raise self.fault(
                    "holds a `::` after a condition, and conditions follow every "
                    "component",
                    "Move the conditions to the end",
                )
            if self.startsWith("["):
                conditions.append(self.attributeParse())
            elif self.startsWith(":"):
                conditions.append(self.pseudoClassParse())
            else:
                examples = " or ".join(
                    f"`{each}`" for each in self.scheme.conditionExamples
                )
                raise self.fault(
                    "holds text after its components that is not a condition",
                    f"Write a condition as {examples}",
                )

    def attributeEndFind(self) -> int:
        """Return where the `[` here closes, a `]` inside quotes not counting."""
        index = self.index + 1
        quoted = False
        while index < self.end:
            character = self.text[index]
            if quoted and character == escapeMarker:
                index += 2
                continue
            if character == '"':
                quoted = not quoted
            elif character == "]" and not quoted:
                return index
            index += 1
        raise self.fault("opens a `[` that is never closed", "Close it with `]`")

    def attributeParse(self) -> SelectorAttribute:
        """Return the attribute condition here, refusing one its scheme lacks."""
        start = self.index
        close = self.attributeEndFind()
        found = attributePattern.fullmatch(self.text, start + 1, close)
        self.index = close + 1
        if found is None:
            raise self.fault(
                "holds a condition that is not `[name]` or `[name=value]`",
                f"Write one as `{self.scheme.conditionExamples[0]}`", start,
            )
        name, operator = found["name"].strip(), found["operator"]
        attributes = self.scheme.attributes
        attribute = attributes.get(name)
        if attribute is None:
            raise composeChoiceRefusal(
                SelectorError, f"[{name}]", "a selector condition",
                [f"[{each}]" for each in attributes],
            )
        if operator is None:
            return SelectorAttribute(name)
        if attribute.values is None and attribute.parse is None:
            raise self.fault(
                f"gives `[{name}]` a value, and it takes none",
                f"Write it as `[{name}]`", start,
            )
        if operator != "=" and not attribute.ordered:
            raise self.fault(
                f"compares `[{name}]` with `{operator}`, and it takes only `=`",
                f"Write it as `[{name}=...]`", start,
            )
        quoted = found["quoted"] is not None
        value = (
            quoteEscape.sub(r"\1", found["quoted"]) if quoted
            else found["bare"].strip()
        )
        exact = found["flag"] is not None
        if exact and not attribute.text:
            raise self.fault(
                f"gives `[{name}]` the `{exactFlag}` flag, which only a name takes",
                f"Remove the `{exactFlag}`", start,
            )
        if attribute.values is not None and value not in attribute.values:
            raise composeChoiceRefusal(
                SelectorError, value, f"a value of `[{name}]`", attribute.values
            )
        if attribute.parse is not None:
            try:
                attribute.parse(value)
            except ValueError as exc:
                raise self.fault(
                    f"gives `[{name}]` `{value}`, which is not one of its values",
                    None, start,
                ) from exc
        return SelectorAttribute(name, value, operator, exact, quoted)

    def pseudoClassParse(self) -> SelectorCondition:
        """Return the `:name` or `:name(argument)` here."""
        start = self.index
        found = pseudoName.match(self.text, self.index + 1, self.end)
        name = "" if found is None else found.group()
        if name == pseudoNegation:
            assert found is not None
            self.index = found.end()
            begin, finish = self.parenthesesRead()
            alternatives = tuple(
                SelectorParser(self.text, each, last, self.scheme).conditionsParse()
                for each, last in splitTopLevel(self.text, begin, finish)
            )
            if not all(alternatives):
                raise self.fault(
                    "holds a `:not()` with no condition",
                    "Write one inside it, such as "
                    f"`:not({self.scheme.conditionExamples[-1]})`", start,
                )
            return SelectorNegation(alternatives)
        takes = self.scheme.pseudoClasses.get(name)
        pseudoNames = (*self.scheme.pseudoClasses, pseudoNegation)
        if takes is None:
            raise composeChoiceRefusal(
                SelectorError, f":{name}", "a selector condition",
                [f":{each}" for each in pseudoNames],
            )
        self.index = start + 1 + len(name)
        if not takes:
            return SelectorPseudoClass(name)
        begin, finish = self.parenthesesRead()
        argument = self.text[begin:finish].replace(" ", "")
        if nthPattern.fullmatch(argument) is None:
            raise self.fault(
                f"holds `{argument}`, which is not a position pattern",
                f"Give `:{name}` `2n`, `2n+1`, `3`, `odd` or `even`, counted from one",
                begin,
            )
        return SelectorPseudoClass(name, argument)


__all__ = [
    "Selector",
    "SelectorAttribute",
    "SelectorComponent",
    "SelectorCondition",
    "SelectorError",
    "SelectorGroup",
    "SelectorLike",
    "SelectorNegation",
    "SelectorPseudoClass",
    "findWildcard",
    "toSelector",
]

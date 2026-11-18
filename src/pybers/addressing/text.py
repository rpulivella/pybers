#!/usr/bin/env python3
"""\
The text form of a reference: each name escaped, the names joined by `::`.

A backslash makes the next character literal, so a sheet named `Budget, draft*` is
written `Budget\\, draft\\*`, and a name holding `::` cannot be read as two. Every
reference prints in this form and parses from it, and a selector reads its names by
the same rules, so a printed reference is also an exact selector for what it names.

The one owner of the separator and the escapes. `tests/test_reference_text.py` fails
for any other module that writes or splits on `::`.

UPDATES
2026-11-18  Written for PYB-267.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/18"

import re

from pybers.errors import PybersError

referenceSeparator: str = "::"
escapeMarker: str = "\\"
# Every character a name escapes, the selector's included, so any name reads back.
specialCharacters: str = "\\*?[](),:"


class ReferenceError(PybersError, ValueError):
    """An address, a range or a name that is not valid reference text."""


def escapeSelectorName(name: str) -> str:
    """Return a name as a reference or a selector writes it, `Budget\\, draft`."""
    last = len(name) - 1
    return "".join(
        f"{escapeMarker}{character}"
        if character in specialCharacters
        or (character == " " and index in (0, last))
        else character
        for index, character in enumerate(name)
    )


def quoteReferenceText(text: str) -> str:
    """Return reference text as a message quotes it, verbatim, so it pastes back.

    The one place a message quotes reference text, since `repr` doubles a backslash.
    """
    return f"'{text}'"


def findEscaped(text: str, index: int) -> bool:
    """Report whether the character at an index follows an unescaped backslash."""
    markers = len(text[:index]) - len(text[:index].rstrip(escapeMarker))
    return markers % 2 == 1


def normalizeWrittenText(written: str) -> str:
    """Return written text without the spaces around it, keeping escaped ones."""
    trimmed = written.lstrip(" ")
    while trimmed.endswith(" ") and not findEscaped(trimmed, len(trimmed) - 1):
        trimmed = trimmed[:-1]
    return trimmed


def readEscapedText(written: str) -> str:
    """Return written text with its escapes removed, the name it spells."""
    return re.sub(r"\\(.)", r"\1", written)


def splitReferenceText(text: str) -> list[str]:
    """Return the parts between each unescaped `::`, each as written, escapes kept."""
    parts: list[str] = []
    begin = index = 0
    while index < len(text):
        if text[index] == escapeMarker:
            index += 2
            continue
        if text.startswith(referenceSeparator, index):
            parts.append(text[begin:index])
            index += len(referenceSeparator)
            begin = index
            continue
        index += 1
    parts.append(text[begin:])
    return parts


def readReferenceName(written: str, text: str) -> str:
    """Return the name one part of reference text spells, refusing an unescaped special.

    A reference names one thing, so a wildcard or a comma in it is a mistake to
    point at rather than a pattern to honor.
    """
    trimmed = normalizeWrittenText(written)
    if trimmed.endswith(escapeMarker) and not findEscaped(trimmed, len(trimmed) - 1):
        raise ReferenceError(
            f"{quoteReferenceText(text)} ends in a backslash, escaping nothing."
        )
    for index, character in enumerate(trimmed):
        if character in specialCharacters and character != escapeMarker and not (
            findEscaped(trimmed, index)
        ):
            name = readEscapedText(trimmed)
            raise ReferenceError(
                f"{quoteReferenceText(text)} holds `{character}` in a name without "
                f"escaping it. Write {quoteReferenceText(escapeSelectorName(name))}."
            )
    name = readEscapedText(trimmed)
    if not name:
        raise ReferenceError(f"{quoteReferenceText(text)} leaves a name empty.")
    return name


def composeReferenceText(*parts: str) -> str:
    """Return reference text from parts already written, joined by `::`."""
    return referenceSeparator.join(parts)


__all__ = [
    "ReferenceError",
    "escapeMarker",
    "findEscaped",
    "composeReferenceText",
    "escapeSelectorName",
    "quoteReferenceText",
    "readEscapedText",
    "readReferenceName",
    "referenceSeparator",
    "specialCharacters",
    "splitReferenceText",
    "normalizeWrittenText",
]

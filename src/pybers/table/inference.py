#!/usr/bin/env python3
"""\
A cell value read from text, its kind inferred or named, for any caller holding text.

One ordered table of parsers decides the kind: inference tries each in turn and the
first that accepts the text wins, so text, which accepts anything, comes last. A kind
named outright uses its own parser and refuses text that parser cannot read.

UPDATES
2026-10-20  Written for PYB-217.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/20"

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from pybers.errors import WriteError
from pybers.table.cell import CellValue
from pybers.table.kinds import CellKind


def parseNumber(text: str) -> Decimal:
    """Return the exact number text writes, refusing one no cell can hold."""
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(text) from exc
    if not number.is_finite():
        raise ValueError(text)
    return number


def parseText(text: str) -> str:
    """Return text as it is, which every string is."""
    return text


# Tried in this order when no kind is named, text last because it accepts anything.
valueParsers: dict[CellKind, Callable[[str], CellValue]] = {
    CellKind.NUMBER: parseNumber,
    CellKind.TEXT: parseText,
}


def parseCellValue(text: str, kind: CellKind | str | None = None) -> CellValue:
    """Return the value text writes, as the kind named or the first it reads as."""
    if kind is None:
        for parser in valueParsers.values():
            try:
                return parser(text)
            except ValueError:
                continue
        raise WriteError(f"{text!r} reads as no kind of value.")
    named = toValueKind(kind)
    try:
        return valueParsers[named](text)
    except ValueError as exc:
        raise WriteError(f"{text!r} is not a {named.value}.") from exc


def toValueKind(kind: CellKind | str) -> CellKind:
    """Return the kind named, refusing one no parser reads, listing those that do."""
    try:
        named = CellKind(kind)
    except ValueError:
        named = None
    if named not in valueParsers:
        known = ", ".join(each.value for each in valueParsers)
        raise WriteError(
            f"{kind!r} is not a kind read from text. Use {known}."
        )
    return named


__all__ = ["parseCellValue", "valueParsers"]

#!/usr/bin/env python3
"""\
The JSON form of each leaf type, one rule apiece: how it is written, read and described.

A number is a `Decimal` the text writer emits as a bare JSON number, never a string
and never a float. A date is wall-clock ISO 8601 with no offset, since a cell stores
none, and a duration is ISO 8601 in days, hours, minutes and seconds, since a month
or a year has no fixed length. An address is its own text, read back by its own
`parse`. The tree walker and the schema generator both read this table, so a rule
written here holds for writing, reading and validating alike.

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

import base64
import binascii
import datetime
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellAddress, CellReference
from pybers.errors import PybersError

# What the JSON text holds once read: numbers arrive as Decimal, never float.
type Tree = None | bool | str | int | Decimal | list[Tree] | dict[str, Tree]

oneSecond: int = 1_000_000
oneDay: int = 86_400 * oneSecond

durationPattern: re.Pattern[str] = re.compile(
    r"(?P<sign>-)?P(?!$)(?:(?P<days>\d+)D)?"
    r"(?:T(?=\d)(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)(?:\.(?P<fraction>\d{1,6}))?S)?)?"
)
dateTimePattern: str = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?$"
)


class JsonFormError(PybersError, ValueError):
    """Text that is not the JSON form of anything pybers holds, naming where."""


@dataclass(frozen=True, slots=True)
class LeafRule:
    """How one leaf type is written to a tree, read from one, and described."""

    leafType: type
    encode: Callable[[Any], Tree]
    decode: Callable[[Tree, str], Any]
    schema: dict[str, object]


def readString(tree: Tree, path: str, what: str) -> str:
    """Return a tree known to be a string, refusing anything else by its path."""
    if not isinstance(tree, str):
        raise JsonFormError(f"{path} must be {what}, and is {formatTreeKind(tree)}.")
    return tree


def formatTreeKind(tree: Tree) -> str:
    """Return what a tree holds, in the words an error message uses."""
    match tree:
        case None:
            return "null"
        case bool():
            return "a boolean"
        case str():
            return "a string"
        case int() | Decimal():
            return "a number"
        case list():
            return "an array"
        case _:
            return "an object"


def formatDuration(duration: datetime.timedelta) -> str:
    """Return a duration as ISO 8601, `P1DT2H30M` or `-PT0.5S`, to the microsecond."""
    total = duration // datetime.timedelta(microseconds=1)
    sign, total = ("-" if total < 0 else ""), abs(total)
    days, rest = divmod(total, oneDay)
    hours, rest = divmod(rest, 3600 * oneSecond)
    minutes, rest = divmod(rest, 60 * oneSecond)
    seconds, fraction = divmod(rest, oneSecond)
    clock = (f"{hours}H" if hours else "") + (f"{minutes}M" if minutes else "")
    if seconds or fraction:
        shown = f"{seconds}.{fraction:06d}".rstrip("0").rstrip(".")
        clock += f"{shown}S"
    if not days and not clock:
        clock = "0S"
    return f"{sign}P{f'{days}D' if days else ''}{'T' + clock if clock else ''}"


def parseIsoDuration(text: str) -> datetime.timedelta:
    """Return the duration ISO 8601 text gives, `P1DT2H30M`, never years or months."""
    found = durationPattern.fullmatch(text.strip())
    if found is None:
        raise ValueError(text)
    parts = found.groupdict()
    duration = datetime.timedelta(
        days=int(parts["days"] or 0), hours=int(parts["hours"] or 0),
        minutes=int(parts["minutes"] or 0), seconds=int(parts["seconds"] or 0),
        microseconds=int((parts["fraction"] or "").ljust(6, "0")),
    )
    return -duration if parts["sign"] else duration


def parseDuration(tree: Tree, path: str) -> datetime.timedelta:
    """Return the duration a tree's ISO 8601 text gives, refusing it by its path."""
    text = readString(tree, path, "an ISO 8601 duration such as P1DT2H30M")
    try:
        return parseIsoDuration(text)
    except ValueError as exc:
        raise JsonFormError(
            f"{path} must be an ISO 8601 duration in days, hours, minutes and seconds, "
            f"such as P1DT2H30M, and is {text!r}."
        ) from exc


def parseDateTime(tree: Tree, path: str) -> datetime.datetime:
    """Return the wall-clock time an ISO 8601 text gives, refusing an offset."""
    text = readString(tree, path, "an ISO 8601 date and time")
    if re.fullmatch(dateTimePattern, text) is None:
        raise JsonFormError(
            f"{path} must be an ISO 8601 date and time with no offset, such as "
            f"2026-10-24T13:45:00, since a cell stores wall-clock time, and is "
            f"{text!r}."
        )
    return datetime.datetime.fromisoformat(text)


def parseDecimal(tree: Tree, path: str) -> Decimal:
    """Return a JSON number read as a Decimal, refusing every other kind of tree."""
    if isinstance(tree, bool) or not isinstance(tree, Decimal | int):
        raise JsonFormError(f"{path} must be a number, and is {formatTreeKind(tree)}.")
    return Decimal(tree)


def parseBytes(tree: Tree, path: str) -> bytes:
    """Return the bytes a base64 text holds."""
    text = readString(tree, path, "base64 text")
    try:
        return base64.b64decode(text, validate=True)
    except binascii.Error as exc:
        raise JsonFormError(f"{path} must be base64 text: {exc}") from exc


def buildAddressRule(
    addressType: type[CellAddress] | type[CellReference] | type[CellRange], example: str
) -> LeafRule:
    """Return the rule for an address type: its own text, read by its own `parse`."""
    def decode(tree: Tree, path: str) -> CellAddress | CellReference | CellRange:
        text = readString(tree, path, f"an address such as {example}")
        try:
            return addressType.parse(text)
        except PybersError as exc:
            raise JsonFormError(f"{path}: {exc}") from exc

    return LeafRule(addressType, str, decode, {"type": "string", "examples": [example]})


leafRules: tuple[LeafRule, ...] = (
    LeafRule(Decimal, lambda value: value, parseDecimal, {"type": "number"}),
    LeafRule(
        datetime.datetime, lambda value: value.isoformat(), parseDateTime,
        {"type": "string", "pattern": dateTimePattern},
    ),
    LeafRule(
        datetime.timedelta, formatDuration, parseDuration,
        # Without Python's group names, which a JSON Schema pattern cannot carry.
        {"type": "string",
         "pattern": f"^{re.sub(r'\?P<\w+>', '', durationPattern.pattern)}$"},
    ),
    LeafRule(
        bytes, lambda value: base64.b64encode(value).decode("ascii"), parseBytes,
        {"type": "string", "contentEncoding": "base64"},
    ),
    buildAddressRule(CellAddress, "B3"),
    buildAddressRule(CellReference, "Sheet 1::Table 1::$B$3"),
    buildAddressRule(CellRange, "B3:D9"),
)


def findLeafRule(leafType: object) -> LeafRule | None:
    """Return the rule for a leaf type, or None when the type is not a leaf."""
    return next((rule for rule in leafRules if rule.leafType is leafType), None)


__all__ = [
    "JsonFormError",
    "LeafRule",
    "Tree",
    "formatTreeKind",
    "findLeafRule",
    "formatDuration",
    "leafRules",
    "parseDuration",
    "parseIsoDuration",
    "readString",
]

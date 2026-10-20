#!/usr/bin/env python3
"""\
A cell value read from text, its kind inferred or named, and the text it reads from.

One ordered table of parsers decides the kind: inference tries each in turn and the
first that accepts the text wins, so text, which accepts anything, comes last. A kind
named outright uses its own parser and refuses text that parser cannot read.

`formatCellValue` writes the one text form each kind reads back from, so a value
printed by the command line is written again as the same value and kind.

UPDATES
2026-10-20  A date, a duration and a boolean read from text, and each value
            written as the text it reads from, for PYB-144.
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

import datetime
import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from pybers.errors import WriteError
from pybers.table.cell import CellValue
from pybers.table.kinds import CellKind

# The words a boolean is written as, compared without case; Numbers shows the first.
booleanWords: frozendict[str, bool] = frozendict({"true": True, "false": False})

# A duration's units as Numbers abbreviates them, each in microseconds.
durationUnits: frozendict[str, int] = frozendict({
    "w": 604_800_000_000, "d": 86_400_000_000, "h": 3_600_000_000,
    "m": 60_000_000, "s": 1_000_000, "ms": 1_000,
})
durationPart: re.Pattern[str] = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|[wdhms])")
durationWhole: re.Pattern[str] = re.compile(
    r"([+-]?)\s*((?:\d+(?:\.\d+)?\s*(?:ms|[wdhms])\s*)+)"
)
# A clock duration, `1:30` or `1:30:15.5`, read only when a duration is named.
durationClock: re.Pattern[str] = re.compile(
    r"([+-]?)(\d+):([0-5]\d)(?::([0-5]\d(?:\.\d+)?))?"
)
microsecondsPerSecond: int = 1_000_000


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


def parseBoolean(text: str) -> bool:
    """Return the boolean `TRUE` or `FALSE` names, in any case."""
    try:
        return booleanWords[text.strip().casefold()]
    except KeyError as exc:
        raise ValueError(text) from exc


def parseDateTime(text: str) -> datetime.datetime:
    """Return the date and time ISO 8601 text names, a date alone as midnight."""
    return datetime.datetime.fromisoformat(text.strip())


def toMicroseconds(amount: str, unit: int) -> int:
    """Return a count of one unit in microseconds, refusing a finer part."""
    exact = Decimal(amount) * unit
    if exact != exact.to_integral_value():
        raise ValueError(amount)
    return int(exact)


def parseDuration(text: str) -> datetime.timedelta:
    """Return the duration units name, as Numbers writes them: `1h 30m`, `-2d 4h`."""
    found = durationWhole.fullmatch(text.strip())
    if found is None:
        raise ValueError(text)
    sign, body = found.groups()
    parts = durationPart.findall(body)
    units = [unit for _, unit in parts]
    if len(set(units)) != len(units):
        raise ValueError(text)
    total = sum(toMicroseconds(amount, durationUnits[unit]) for amount, unit in parts)
    return datetime.timedelta(microseconds=-total if sign == "-" else total)


def parseDurationNamed(text: str) -> datetime.timedelta:
    """Return the duration units or a clock name, `1h 30m` or `1:30`."""
    found = durationClock.fullmatch(text.strip())
    if found is None:
        return parseDuration(text)
    sign, hours, minutes, seconds = found.groups()
    total = (
        toMicroseconds(hours, durationUnits["h"])
        + toMicroseconds(minutes, durationUnits["m"])
        + toMicroseconds(seconds or "0", durationUnits["s"])
    )
    return datetime.timedelta(microseconds=-total if sign == "-" else total)


# Tried in this order when no kind is named, text last because it accepts anything.
# A clock such as `1:30` is not inferred, since it reads as a time of day as well.
valueParsers: frozendict[CellKind, Callable[[str], CellValue]] = frozendict({
    CellKind.NUMBER: parseNumber,
    CellKind.BOOLEAN: parseBoolean,
    CellKind.DATE_TIME: parseDateTime,
    CellKind.DURATION: parseDuration,
    CellKind.TEXT: parseText,
})
namedParsers: frozendict[CellKind, Callable[[str], CellValue]] = frozendict({
    **valueParsers, CellKind.DURATION: parseDurationNamed,
})
# What `--as` calls each kind; a kind's own value specifies it as well.
kindNames: frozendict[str, CellKind] = frozendict({
    "number": CellKind.NUMBER, "boolean": CellKind.BOOLEAN, "date": CellKind.DATE_TIME,
    "duration": CellKind.DURATION, "text": CellKind.TEXT,
})


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
        return namedParsers[named](text)
    except ValueError as exc:
        raise WriteError(f"{text!r} is not a {named.value}.") from exc


def toValueKind(kind: CellKind | str) -> CellKind:
    """Return the kind named, refusing one no parser reads, listing those that do."""
    named = kind if isinstance(kind, CellKind) else kindNames.get(kind)
    if named is None and kind in CellKind:
        named = CellKind(kind)
    if named not in valueParsers:
        known = ", ".join(kindNames)
        raise WriteError(f"{kind!r} is not a kind read from text. Use {known}.")
    return named


def formatDuration(value: datetime.timedelta) -> str:
    """Return a duration in the units Numbers writes, `1h 30m`, never `-1 day, 8:38`."""
    total = abs(value) // datetime.timedelta(microseconds=1)
    parts = []
    for unit in ("d", "h", "m"):
        count, total = divmod(total, durationUnits[unit])
        if count:
            parts.append(f"{count}{unit}")
    if total or not parts:
        seconds = Decimal(total) / microsecondsPerSecond
        parts.append(f"{seconds.normalize():f}s")
    return ("-" if value < datetime.timedelta(0) else "") + " ".join(parts)


def formatCellValue(value: CellValue) -> str:
    """Return the text `parseCellValue` reads back as this value, `none` for empty."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, datetime.timedelta):
        return formatDuration(value)
    return str(value)


__all__ = ["formatCellValue", "parseCellValue", "valueParsers"]

#!/usr/bin/env python3
"""The series a line of seed values begins, as Numbers continues one when dragged.

Every rule is one findings-03-structure.md measured, in all four directions: a
constant numeric step, dates stepping by days or whole months, weekday and month
names, and text ending in a number. A continuation is a function of the offset from
the first seed, so a negative offset is a drag up or left and needs no rule of its
own. Seeds that begin no series return no continuation, and a fill repeats them.

UPDATES
2026-09-30  Written for PYB-137.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/30"

import calendar
import datetime
import re
from collections.abc import Callable, Sequence
from decimal import Decimal
from itertools import pairwise

type SeedValue = Decimal | str | bool | datetime.datetime | datetime.timedelta | None
type SeriesContinuation = Callable[[int], SeedValue]

weekdayNames: tuple[str, ...] = tuple(calendar.day_name)
monthNames: tuple[str, ...] = tuple(calendar.month_name)[1:]
numberedText = re.compile(r"^(.*?)(\d+)$", re.DOTALL)


def findConstantStep[T](
    values: Sequence[T], measure: Callable[[T, T], int]
) -> int | None:
    """Return the one step between neighbors, or None when the steps differ."""
    steps = {measure(before, after) for before, after in pairwise(values)}
    return steps.pop() if len(steps) == 1 else None


def findNumberContinuation(seeds: Sequence[Decimal]) -> SeriesContinuation | None:
    """Continue a constant step, which may be negative or fractional."""
    steps = {after - before for before, after in pairwise(seeds)}
    if len(steps) != 1:
        return None
    step = steps.pop()
    return lambda offset: seeds[0] + step * offset


def countMonths(before: datetime.datetime, after: datetime.datetime) -> int | None:
    """Return the months between two dates sharing a day and a time, else None."""
    if before.day != after.day or before.timetz() != after.timetz():
        return None
    return (after.year - before.year) * 12 + after.month - before.month


def addMonths(date: datetime.datetime, months: int) -> datetime.datetime:
    """Return a date some months on, its day held to the end of a shorter month."""
    index = date.year * 12 + date.month - 1 + months
    year, month = index // 12, index % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


def findDateContinuation(
    seeds: Sequence[datetime.datetime],
) -> SeriesContinuation | None:
    """Continue whole months when the seeds share a day, else days. One steps a day."""
    if len(seeds) == 1:
        return lambda offset: seeds[0] + datetime.timedelta(days=offset)
    counts = [countMonths(before, after) for before, after in pairwise(seeds)]
    months = counts[0]
    if months and all(count == months for count in counts):
        return lambda offset: addMonths(seeds[0], months * offset)
    steps = {after - before for before, after in pairwise(seeds)}
    if len(steps) != 1:
        return None
    step = steps.pop()
    return lambda offset: seeds[0] + step * offset


def findNameContinuation(
    seeds: Sequence[str], names: tuple[str, ...]
) -> SeriesContinuation | None:
    """Continue names that keep one distance apart, wrapping at either end."""
    positions = [names.index(seed) for seed in seeds]
    step = 1 if len(positions) == 1 else findConstantStep(
        positions, lambda before, after: (after - before) % len(names)
    )
    if step is None:
        return None
    return lambda offset: names[(positions[0] + step * offset) % len(names)]


def findNumberedTextContinuation(seeds: Sequence[str]) -> SeriesContinuation | None:
    """Continue text ending in a number, when the seeds share its text and step."""
    matches = [numberedText.match(seed) for seed in seeds]
    if None in matches:
        return None
    parts = [(match.group(1), match.group(2)) for match in matches if match]
    if len({prefix for prefix, _ in parts}) != 1:
        return None
    numbers = [int(digits) for _, digits in parts]
    step = 1 if len(numbers) == 1 else findConstantStep(numbers, lambda a, b: b - a)
    if step is None:
        return None
    prefix, width = parts[0][0], len(parts[0][1])

    def continueText(offset: int) -> str:
        number = numbers[0] + step * offset
        return f"{prefix}{number:0{width}d}" if number >= 0 else f"{prefix}{number}"

    return continueText


def findTextContinuation(seeds: Sequence[str]) -> SeriesContinuation | None:
    """Continue weekday names, month names or numbered text, as the seeds are."""
    for names in (weekdayNames, monthNames):
        if all(seed in names for seed in seeds):
            return findNameContinuation(seeds, names)
    return findNumberedTextContinuation(seeds)


def findSeriesContinuation(seeds: Sequence[SeedValue]) -> SeriesContinuation | None:
    """Return each value of the series the seeds begin, given its offset from the first.

    None means the seeds begin no series, so a fill repeats them: a mix of kinds, an
    empty seed, or a lone number, which Numbers repeats where it steps a lone date,
    name or numbered text by one.
    """
    kinds = {type(seed) for seed in seeds}
    if len(kinds) != 1:
        return None
    if kinds == {Decimal}:
        if len(seeds) < 2:
            return None
        return findNumberContinuation(seeds)  # type: ignore[arg-type]
    if kinds == {datetime.datetime}:
        return findDateContinuation(seeds)  # type: ignore[arg-type]
    if kinds == {str}:
        return findTextContinuation(seeds)  # type: ignore[arg-type]
    return None


__all__ = ["SeriesContinuation", "findSeriesContinuation"]

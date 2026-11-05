#!/usr/bin/env python3
"""A document's time zone, turning a real moment into the wall-clock time a cell stores.

Numbers stores a date as wall-clock time with no zone, so a zone matters only when a
caller writes a `datetime` that carries one. See findings-01-values.md.

UPDATES
2026-10-20  Written for PYB-144.
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
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pybers.errors import PybersError

unixEpoch: datetime.datetime = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
oneSecond: datetime.timedelta = datetime.timedelta(seconds=1)

# What a caller may name a zone by: a `tzinfo`, or a name for `zoneinfo.ZoneInfo`.
TimeZoneLike = datetime.tzinfo | str


class TimeZoneError(PybersError, ValueError):
    """A time zone that Python cannot find by the name given."""


class MachineTimeZone(datetime.tzinfo):
    """The zone pybers is running in, asked of the system at every call.

    A fixed offset taken once would be wrong for half the year wherever clocks change.
    """

    def fromutc(self, value: datetime.datetime) -> datetime.datetime:
        """Return a UTC moment as this machine's wall-clock time."""
        seconds = (value.replace(tzinfo=datetime.UTC) - unixEpoch) // oneSecond
        return (value.replace(tzinfo=None) + findMachineOffset(seconds)).replace(
            tzinfo=self
        )

    def utcoffset(self, value: datetime.datetime | None) -> datetime.timedelta:
        """Return how far this machine's wall clock stood from UTC at a local time."""
        if value is None:
            return findMachineOffset(int(time.time()))
        return findMachineOffset(findMachineSeconds(value))

    def dst(self, value: datetime.datetime | None) -> datetime.timedelta:
        """Return how much of the offset at a local time is daylight saving."""
        return self.utcoffset(value) - datetime.timedelta(seconds=-time.timezone)

    def tzname(self, value: datetime.datetime | None) -> str:
        """Return the name the system gives this zone at a local time."""
        seconds = int(time.time()) if value is None else findMachineSeconds(value)
        return time.tzname[time.localtime(seconds).tm_isdst > 0]

    def __repr__(self) -> str:
        """Return the zone as the call that builds it."""
        return "MachineTimeZone()"


def findMachineOffset(seconds: int) -> datetime.timedelta:
    """Return this machine's offset from UTC at a moment counted from 1970."""
    return datetime.timedelta(seconds=time.localtime(seconds).tm_gmtoff)


def findMachineSeconds(value: datetime.datetime) -> int:
    """Return the moment a wall-clock time on this machine names, counted from 1970."""
    # Read naive, since an aware value's `timetuple` asks this zone for its `dst`.
    return int(time.mktime((*value.replace(tzinfo=None).timetuple()[:8], -1)))


machineTimeZone: MachineTimeZone = MachineTimeZone()


def toTimeZone(zone: TimeZoneLike) -> datetime.tzinfo:
    """Return a zone given as a `tzinfo`, or by a name `zoneinfo.ZoneInfo` knows."""
    if isinstance(zone, datetime.tzinfo):
        return zone
    try:
        return ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TimeZoneError(
            f"{zone!r} specifies no time zone Python knows. Specify one as "
            "'America/New_York' does."
        ) from exc


def toWallClockTime(
    value: datetime.datetime, zone: datetime.tzinfo
) -> datetime.datetime:
    """Return the wall-clock time a cell stores, an aware time converted to `zone`."""
    if value.tzinfo is None:
        return value
    return value.astimezone(zone).replace(tzinfo=None)


__all__ = [
    "MachineTimeZone",
    "TimeZoneError",
    "TimeZoneLike",
    "machineTimeZone",
    "toTimeZone",
    "toWallClockTime",
]

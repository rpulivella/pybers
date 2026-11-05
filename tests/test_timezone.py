#!/usr/bin/env python3
"""\
The zone a document writes an aware `datetime` in: this machine's, or one named.

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
import zoneinfo

import pytest

import pybers
from pybers.timezone import machineTimeZone, toTimeZone, toWallClockTime

# A moment in each half of the year, so a zone that changes its clocks is seen do it.
moments: tuple[datetime.datetime, ...] = (
    datetime.datetime(2026, 1, 15, 12, tzinfo=datetime.UTC),
    datetime.datetime(2026, 7, 15, 12, tzinfo=datetime.UTC),
)


@pytest.mark.parametrize("moment", moments, ids=str)
def testTheMachineZoneAgreesWithThePlatform(moment: datetime.datetime) -> None:
    local = moment.astimezone(machineTimeZone)
    platform = moment.astimezone()
    assert local.replace(tzinfo=None) == platform.replace(tzinfo=None)
    assert local.utcoffset() == platform.utcoffset()
    assert local.tzname() == platform.tzname()


def testANamedZoneIsTheZoneInfoOfThatName() -> None:
    assert toTimeZone("Europe/Rome") == zoneinfo.ZoneInfo("Europe/Rome")


def testATzinfoIsTakenAsItIs() -> None:
    zone = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    assert toTimeZone(zone) is zone


@pytest.mark.parametrize("name", ["Mars/Olympus", "", "../etc/passwd"])
def testANameNoZoneAnswersToIsRefused(name: str) -> None:
    with pytest.raises(pybers.TimeZoneError):
        toTimeZone(name)


def testANaiveTimeIsWallClockTimeAlready() -> None:
    naive = datetime.datetime(2026, 3, 8, 2, 30)
    assert toWallClockTime(naive, zoneinfo.ZoneInfo("America/New_York")) is naive


def testAnAwareTimeIsTheWallClockOfTheZoneNamed() -> None:
    zone = zoneinfo.ZoneInfo("America/New_York")
    assert toWallClockTime(moments[1], zone) == datetime.datetime(2026, 7, 15, 8)

#!/usr/bin/env python3
"""\
A date is floating wall-clock time: one typed time stores one value in every zone.

`72-date-time-zones` holds `2026-10-20 09:00` typed on a Mac in New York in A1 and in
Los Angeles in B1, and the same time typed with `PST` in C1.
`72b-date-time-zones-region` is that document with its region set to English (Italy).

UPDATES
2026-10-20  A date reads as naive wall-clock time, for PYB-144.
2026-10-20  Written for PYB-218.
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

import pytest

import pybers
from conftest import findDocumentPath

# The wall-clock time both cells were typed as, counted from 2001 as if it were UTC.
typedSeconds: float = 814_179_600.0
appleEpoch: datetime.datetime = datetime.datetime(2001, 1, 1)


def readStoredSeconds(stem: str, reference: str) -> float:
    """Return the seconds a date cell stores, read as the wall-clock time it is."""
    value = pybers.open(findDocumentPath(stem)).cell(reference).value
    assert isinstance(value, datetime.datetime)
    assert value.tzinfo is None
    return (value - appleEpoch).total_seconds()


@pytest.mark.parametrize("stem", ["72-date-time-zones", "72b-date-time-zones-region"])
@pytest.mark.parametrize("reference", ["Table 1::A1", "Table 1::B1"])
def testOneTypedTimeStoresOneValueInEveryZoneAndRegion(
    stem: str, reference: str
) -> None:
    assert readStoredSeconds(stem, reference) == typedSeconds


def testATypedZoneLeavesTheTimeAsText() -> None:
    cell = pybers.open(findDocumentPath("72-date-time-zones")).cell("Table 1::C1")
    assert cell.value == "2026-10-20 09:00 PST"
    assert cell.description.kind is pybers.CellKind.TEXT

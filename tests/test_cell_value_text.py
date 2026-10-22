#!/usr/bin/env python3
"""\
A cell value read from text: inferred from the text, or read as the kind named.

UPDATES
2026-10-22  A currency amount reads and prints, for PYB-220.
2026-10-20  A boolean, a date and a duration read from text, and each value written
            as the text it reads back from, for PYB-144.
2026-10-20  A kind no parser reads is one Numbers stores but text cannot name, for
            PYB-144.
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
from decimal import Decimal

import pytest

import pybers
from pybers import CellKind, formatCellValue, parseCellValue


@pytest.mark.parametrize(("text", "number"), [
    ("42", "42"), ("-3.50", "-3.50"), ("+5", "5"), (".5", "0.5"), ("1e3", "1E+3"),
])
def testTextANumberIsWrittenAsReadsAsThatExactNumber(text: str, number: str) -> None:
    value = parseCellValue(text)
    assert isinstance(value, Decimal)
    assert value.as_tuple() == Decimal(number).as_tuple()


@pytest.mark.parametrize("text", ["hello", "1,000", "0x10", "nan", "Infinity", ""])
def testTextNoNumberReadsAsStaysText(text: str) -> None:
    assert parseCellValue(text) == text


def testANumberNamedAsTextStaysText() -> None:
    assert parseCellValue("42", CellKind.TEXT) == "42"


def testAKindMayBeNamedByItsText() -> None:
    assert parseCellValue("42", "number") == Decimal(42)


def testTextThatIsNotTheKindNamedIsRefused() -> None:
    with pytest.raises(pybers.WriteError, match="'abc' is not a number"):
        parseCellValue("abc", CellKind.NUMBER)


def testAKindNoParserReadsIsRefusedListingThoseThatDo() -> None:
    with pytest.raises(
        pybers.WriteError, match="Use number, currency, boolean, date, duration, text"
    ):
        parseCellValue("x", "rich-text")


@pytest.mark.parametrize("value", [
    Decimal("-3.50"), Decimal("1E+3"), pybers.CurrencyAmount(Decimal("12.50"), "EUR"),
    "hello", True, False,
    datetime.datetime(2026, 10, 20), datetime.datetime(2026, 10, 20, 9, 30, 15, 5),
    datetime.timedelta(minutes=90), datetime.timedelta(seconds=-55320),
    datetime.timedelta(days=71, hours=11, milliseconds=10), datetime.timedelta(0),
])
def testEveryValueReadsBackFromTheTextItIsWrittenAs(value: object) -> None:
    text = formatCellValue(value)  # type: ignore[arg-type]
    read = parseCellValue(text)
    assert (type(read), read) == (type(value), value)


def testANegativeDurationIsWrittenAsNumbersWritesIt() -> None:
    assert formatCellValue(datetime.timedelta(seconds=-55320)) == "-15h 22m"


@pytest.mark.parametrize(("text", "seconds"), [
    ("1w", 604800), ("2d 3h", 183600), ("90m", 5400), ("1.5s", 1.5),
    ("250ms", 0.25), ("-1h 30m", -5400), ("1h30m", 5400),
])
def testADurationIsReadInNumbersOwnUnits(text: str, seconds: float) -> None:
    value = parseCellValue(text)
    assert isinstance(value, datetime.timedelta)
    assert value.total_seconds() == seconds


@pytest.mark.parametrize("text", ["1h 1h", "1.0000001s", "h", "1x"])
def testTextThatNamesNoExactDurationIsRefusedWhenOneIsNamed(text: str) -> None:
    with pytest.raises(pybers.WriteError, match="is not a duration"):
        parseCellValue(text, "duration")


@pytest.mark.parametrize("text", ["TRUE", "true", " False "])
def testABooleanIsReadInAnyCase(text: str) -> None:
    assert parseCellValue(text) is (text.strip().casefold() == "true")


def testADateWithAnOffsetIsReadAsTheMomentItNames() -> None:
    value = parseCellValue("2026-10-20T09:00-04:00")
    assert isinstance(value, datetime.datetime)
    assert value.utcoffset() == datetime.timedelta(hours=-4)

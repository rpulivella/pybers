#!/usr/bin/env python3
"""\
A cell value read from text: inferred from the text, or read as the kind named.

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

from decimal import Decimal

import pytest

import pybers
from pybers import CellKind, parseCellValue


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
    with pytest.raises(pybers.WriteError, match="Use number, text"):
        parseCellValue("2026-10-20", "date")

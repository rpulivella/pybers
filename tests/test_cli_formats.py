#!/usr/bin/env python3
"""\
How the formats every command offers write a library result.

UPDATES
2026-10-12  Written for PYB-187.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/12"

import json
from decimal import Decimal

import pytest

import pybers
from pybers.cli._formats import encodeJsonValue


def writeJson(value: object) -> object:
    """Return a value as JSON writes it and reads it back."""
    return json.loads(json.dumps(value, default=encodeJsonValue))


@pytest.mark.parametrize(
    "found", [pybers.NOT_REQUESTED, pybers.UNDETERMINED, pybers.WITHHELD]
)
def testASentinelIsWrittenAsItsName(found: object) -> None:
    assert writeJson(found) == repr(found)


def testAFrozendictIsWrittenWithItsKeysAsStrings() -> None:
    assert writeJson(frozendict({3008: 2})) == {"3008": 2}


def testADataclassIsWrittenAsTheFieldsItsReprShows() -> None:
    failure = pybers.CheckFailure("KeyError", pybers.WITHHELD, (), error=KeyError())
    assert writeJson(failure) == {
        "errorType": "KeyError", "message": "WITHHELD", "frames": []
    }


def testAValueWithNoJsonFormIsRefusedByName() -> None:
    with pytest.raises(TypeError, match="no JSON form for Decimal"):
        writeJson(Decimal("1.5"))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke tests for the pybers object model, proving the package installs, imports, and
that the model's basic equality behavior holds before any real archive I/O exists. Real
round-trip tests (read a fixture .numbers file, write it back unchanged, assert byte-for-
byte equality) land once pybers.numbersfile exists, see CLAUDE.md.

UPDATES
2026-08-12  Initial scaffold.
"""

import dataclasses
from decimal import Decimal

import pytest

import pybers


def testPackageExposesVersion() -> None:
    """The package's __version__ matches pyproject.toml, so releases cannot drift apart."""
    assert pybers.__version__ == "0.1.0"


def testStyleIsFrozenAndHashable() -> None:
    """Style must be immutable, the fix for the old fork's shared-mutable-Style bug,
    where two cells could hold the exact same Style object by reference."""
    style = pybers.Style(bold=True)
    assert hash(style) is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        style.bold = False  # type: ignore[misc]


def testCellCreatesAndReusesCells() -> None:
    """Table.cell() creates a cell on first access and returns the same one after."""
    table = pybers.Table(name="Table 1", rowCount=1, colCount=1)
    first = table.cell("A1")
    first.value = "hello"
    second = table.cell(pybers.CellReference(1, 1))
    assert second.value == "hello"
    assert first is second


def testDocumentRoundTripsThroughEquality() -> None:
    """A model built twice the same way must compare equal, the baseline every future
    real archive round-trip test (read, write, read again) will build on."""

    def build() -> pybers.Document:
        table = pybers.Table(name="Table 1", rowCount=1, colCount=1)
        table.cell("A1").value = Decimal("42")
        return pybers.Document(sheets=[pybers.Sheet(name="Sheet 1", tables=[table])])

    assert build() == build()

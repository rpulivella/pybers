#!/usr/bin/env python3
"""Smoke tests for the pybers object model, proving the package installs, imports, and
that the model's basic equality behavior holds before any real archive I/O exists. Real
round-trip tests (read a document .numbers file, write it back unchanged, assert
byte-for-byte equality) land once pybers._persistence exists, see CLAUDE.md.

UPDATES
2026-08-12  Initial scaffold.
"""

import dataclasses
import importlib
import pkgutil
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

import pybers


def walkPackage(name: str) -> list[ModuleType]:
    """Return every module in a package, so a check can cover all of them."""
    package = importlib.import_module(name)
    found = [package]
    for info in pkgutil.walk_packages(package.__path__, f"{name}."):
        if "_generated" in info.name:
            continue
        found.append(importlib.import_module(info.name))
    return found


def testPackageExposesVersion() -> None:
    """The package's __version__ matches pyproject.toml, so releases cannot
    drift apart."""
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

    def buildDocument() -> pybers.Document:
        table = pybers.Table(name="Table 1", rowCount=1, colCount=1)
        table.cell("A1").value = Decimal("42")
        return pybers.Document(sheets=[pybers.Sheet(name="Sheet 1", tables=[table])])

    assert buildDocument() == buildDocument()


def testEveryErrorThisLibraryRaisesAnswersToOneName() -> None:
    """One `except` clause can be right, which is why the root exists.

    Measured before it did: `ContainerError` escaped `pybers.open` on a file that
    was not a zip, lived in a private package, and was not exported, so the only
    correct clause was `except Exception`.
    """
    for module in walkPackage("pybers"):
        for name in dir(module):
            found = getattr(module, name)
            if not isinstance(found, type) or not issubclass(found, Exception):
                continue
            if found.__module__.startswith("pybers."):
                assert issubclass(found, pybers.PybersError), (
                    f"{found.__module__}.{name} escapes the root"
                )


def testAnErrorKeepsTheBuiltinItAlreadyAnsweredTo() -> None:
    """Adding the root never took a base away, so an existing `except` still works."""
    assert issubclass(pybers.ReferenceError, ValueError)
    assert issubclass(pybers.SelectionError, LookupError)
    assert issubclass(pybers.ReadError, RuntimeError)
    assert issubclass(pybers.FormulaSyntaxError, pybers.FormulaError)


def testOpeningSomethingThatIsNotADocumentRaisesTheRoot(tmp_path: Path) -> None:
    """The case that found the hole: a file that is not a zip at all."""
    broken = tmp_path / "notadocument.numbers"
    broken.write_bytes(b"this is not a zip")
    with pytest.raises(pybers.PybersError):
        pybers.open(broken)

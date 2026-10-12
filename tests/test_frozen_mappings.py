#!/usr/bin/env python3
"""\
Every mapping pybers hands out, or keeps as a fixed table, refuses a change.

UPDATES
2026-10-11  Written for PYB-189.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/11"

from collections.abc import Callable, Mapping
from typing import Any

import pytest

import pybers
from conftest import findDocumentPath
from pybers._persistence.types import archiveTypeIds, archiveTypes
from pybers.cli._console import themeStyles
from pybers.formula.functions import functionsByIndex, functionsByName
from pybers.formula.syntax import (
    binaryOperators,
    operatorPrecedence,
    operatorSymbols,
    unaryOperators,
)
from pybers.table._read import formatFamilies, storedKinds
from pybers.table._records import kindPhrases


def readCheckMappings() -> tuple[Mapping[Any, Any], Mapping[Any, Any]]:
    """Return both type tables of a real check, the cell table included."""
    check = pybers.checkDocument(findDocumentPath("00-baseline"))
    assert check.unrecognizedCellTypes is not None
    return check.untestedArchiveTypes, check.unrecognizedCellTypes


def readTableIdentities() -> Mapping[Any, Any]:
    """Return the table identities of a document whose formulas name other tables."""
    return pybers.open(findDocumentPath("20-formula-shapes")).tableIdentities


def readCellTableNames() -> Mapping[Any, Any]:
    """Return the table names a cell of that document knows."""
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    return document.sheets[0].tables[0].cell("A1").tableNames


mappingReaders: dict[str, Callable[[], Mapping[Any, Any]]] = {
    "Check.untestedArchiveTypes": lambda: readCheckMappings()[0],
    "Check.unrecognizedCellTypes": lambda: readCheckMappings()[1],
    "archiveTypes": lambda: archiveTypes,
    "archiveTypeIds": lambda: archiveTypeIds,
    "storedKinds": lambda: storedKinds,
    "formatFamilies": lambda: formatFamilies,
    "kindPhrases": lambda: kindPhrases,
    "binaryOperators": lambda: binaryOperators,
    "unaryOperators": lambda: unaryOperators,
    "operatorSymbols": lambda: operatorSymbols,
    "operatorPrecedence": lambda: operatorPrecedence,
    "functionsByName": lambda: functionsByName,
    "functionsByIndex": lambda: functionsByIndex,
    "themeStyles": lambda: themeStyles,
    "Document.tableIdentities": readTableIdentities,
    "Cell.tableNames": readCellTableNames,
}


@pytest.mark.parametrize("name", mappingReaders)
def testMappingIsAFrozendict(name: str) -> None:
    assert type(mappingReaders[name]()) is frozendict


@pytest.mark.parametrize("name", mappingReaders)
def testMappingRefusesAnEntry(name: str) -> None:
    mapping: Any = mappingReaders[name]()
    with pytest.raises(TypeError):
        mapping["added"] = "refused"

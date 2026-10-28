#!/usr/bin/env python3
"""\
The committed locale table against the formatting symbols Numbers wrote.

Each `95` measurement is `95-region-base` with only its Language & Region changed in
Numbers, so its `TSK.FormattingSymbolsArchive` is what Numbers writes for that region,
and every field the table holds for it must be equal.

UPDATES
2026-10-28  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/28"

import pytest

from conftest import findDocumentPath
from pybers._generated.locales import locales
from pybers._generated.TNArchives_pb2 import DocumentArchive
from pybers._persistence import readPackage
from pybers._persistence.index import ArchiveIndex

# The measurement Numbers saved for each region, from `95-region-base`.
measuredRegions: dict[str, str] = {
    "en_US": "95-region-base",
    "de_DE": "95b-region-de-de",
    "en_GB": "95c-region-en-gb",
    "ja_JP": "95e-region-ja-jp",
    "en_ZA": "95f-region-en-za",
    "pt_BR": "95g-region-pt-br",
    "en_AU": "95h-region-en-au",
    "en_IN": "95i-region-en-in",
}


def readStoredSymbols(stem: str) -> dict[str, object]:
    """Return every field of the formatting symbols a measurement stores, by name."""
    index = ArchiveIndex(readPackage(findDocumentPath(stem)))
    root = DocumentArchive()
    root.ParseFromString(index.archive(1).messages[0].data)
    symbols = root.super.super.formatting_symbols
    stored: dict[str, object] = {}
    for field in symbols.DESCRIPTOR.fields:
        value = getattr(symbols, field.name)
        if field.name == "currency_symbols":
            stored[field.name] = tuple((each.code, each.symbol) for each in value)
        elif field.is_repeated:
            stored[field.name] = tuple(value)
        else:
            stored[field.name] = value
    return stored


@pytest.mark.parametrize(("identifier", "stem"), measuredRegions.items())
def testEveryFieldIsTheOneNumbersWrote(identifier: str, stem: str) -> None:
    assert dict(locales[identifier]) == readStoredSymbols(stem)


def testTheTableHoldsEveryMeasuredRegion() -> None:
    assert set(measuredRegions) <= set(locales)

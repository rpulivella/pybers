#!/usr/bin/env python3
"""\
A document's language and region, as the measurements of `95-region-base` record them.

Each `95` measurement is the base with only Language & Region changed in Numbers, and
`72b-date-time-zones-region` is the earlier English (Italy) document.

UPDATES
2026-10-28  A region changed, written as Numbers writes it, for PYB-272.
2026-10-27  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/27"

from pathlib import Path

import pytest

import pybers
from conftest import copyDocument, findDocumentPath
from pybers._engine.owners import findCalculationEngine
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._persistence import readPackage
from pybers._persistence.index import ArchiveIndex, findRoot


def readLocaleArchive(path: Path) -> tn.DocumentArchive:
    """Return a document's root archive, which holds its language and region."""
    return findRoot(ArchiveIndex(readPackage(path)))


def readDirtyCells(path: Path) -> set[tuple[int, int]]:
    """Return every cell a document asks Numbers to recalculate, as row and column."""
    index = ArchiveIndex(readPackage(path))
    engine = findCalculationEngine(index)
    dirty = index.identifierResolve(
        engine.refs_to_dirty.identifier, tsce.ReferencesToDirtyArchive
    )
    return {
        (entry.range_begin, column.column)
        for owner in dirty.to_dirty_cells.owner_entries
        for column in owner.coord_set.column_entries
        for entry in column.row_set.entries
    }


@pytest.mark.parametrize(("stem", "locale"), [
    ("95-region-base", "en_US"),
    ("95b-region-de-de", "de_DE"),
    ("95c-region-en-gb", "en_GB"),
    ("95d-region-language-english", "en_US"),
    ("95e-region-ja-jp", "ja_JP"),
    ("95f-region-en-za", "en_ZA"),
    ("95g-region-pt-br", "pt_BR"),
    ("95h-region-en-au", "en_AU"),
    ("95i-region-en-in", "en_IN"),
    ("72b-date-time-zones-region", "en_IT"),
])
def testADocumentReportsTheLocaleNumbersSavedItUnder(stem: str, locale: str) -> None:
    assert pybers.open(findDocumentPath(stem)).localeIdentifier == locale


def testADocumentBuiltInMemoryHasNoLocale() -> None:
    assert pybers.Document().localeIdentifier is None


def testTheLocaleIsReadOnly() -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    with pytest.raises(AttributeError):
        document.localeIdentifier = "de_DE"  # type: ignore[misc]


@pytest.mark.parametrize(("identifier", "stem"), [
    ("de_DE", "95b-region-de-de"),
    ("en_GB", "95c-region-en-gb"),
    ("ja_JP", "95e-region-ja-jp"),
    ("en_ZA", "95f-region-en-za"),
    ("pt_BR", "95g-region-pt-br"),
    ("en_AU", "95h-region-en-au"),
    ("en_IN", "95i-region-en-in"),
])
def testAChangedRegionIsWrittenAsNumbersWritesIt(
    tmp_path: Path, identifier: str, stem: str
) -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    document.localeSet(identifier)
    document.save(tmp_path / "changed.numbers")
    written = readLocaleArchive(tmp_path / "changed.numbers")
    measured = readLocaleArchive(findDocumentPath(stem))
    assert written.super.super.formatting_symbols == (
        measured.super.super.formatting_symbols
    )
    assert written.super.super.locale_identifier == identifier
    assert written.super.super.has_user_defined_locale
    assert written.super.document_language == measured.super.document_language


def testAScriptChangesADocumentsRegion(tmp_path: Path) -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    change = document.localeSet("de_DE")
    document.save(tmp_path / "german.numbers")
    reopened = pybers.open(tmp_path / "german.numbers")
    assert (change.localeBefore, change.localeAfter) == ("en_US", "de_DE")
    assert reopened.localeIdentifier == "de_DE"
    assert reopened.currencyPattern == "#,##0.00\xa0¤"


def testAChangedRegionMarksEveryFormulaForRecalculation(tmp_path: Path) -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    document.localeSet("de_DE")
    document.save(tmp_path / "german.numbers")
    assert readDirtyCells(tmp_path / "german.numbers") == {
        (0, column) for column in range(5, 11)
    }


def testTheRegionADocumentHoldsIsNoChange(tmp_path: Path) -> None:
    path = copyDocument("95-region-base", tmp_path)
    document = pybers.open(path)
    change = document.localeSet("en_US")
    document.save()
    assert not change.changed
    assert readDirtyCells(path) == set()
    assert readLocaleArchive(path).super.super.formatting_symbols == (
        readLocaleArchive(findDocumentPath("95-region-base")).super.super
        .formatting_symbols
    )


def testAPreviewChangesNothing() -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    change = document.localeSet("de_DE", preview=True)
    assert change.changed
    assert document.localeIdentifier == "en_US"


@pytest.mark.parametrize("identifier", ["de_XX", "", "en-GB", 5])
def testARegionPybersDoesNotOfferIsRefusedNamingTheClosest(identifier: object) -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    with pytest.raises(pybers.LocaleError, match="No region pybers offers is named"):
        document.localeSet(identifier)  # type: ignore[arg-type]
    assert document.localeIdentifier == "en_US"


def testARefusalSuggestsRegionsOfTheLanguageAskedFor() -> None:
    document = pybers.open(findDocumentPath("95-region-base"))
    with pytest.raises(pybers.LocaleError) as raised:
        document.localeSet("de_XX")
    assert "'de_" in str(raised.value)
    assert f"of the {len(pybers.locales)} it offers" in str(raised.value)


def testADocumentBuiltInMemoryTakesARegion() -> None:
    document = pybers.Document()
    assert document.localeSet("en_GB").changed
    assert document.currencySymbolFind("USD") == "US$"

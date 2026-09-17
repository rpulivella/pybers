#!/usr/bin/env python3
"""\
Listing what two packages hold differently, the one owner of package comparison.

UPDATES
2026-09-17  Written for PYB-94.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"

from dataclasses import replace

from conftest import findDocumentPath
from pybers._persistence import NumbersPackage, readPackage
from pybers._persistence.difference import PackageDifference, listPackageDifferences

documentStem: str = "20-formula-shapes"


def readDocument() -> NumbersPackage:
    """Read a fresh package of the document every test here compares."""
    return readPackage(findDocumentPath(documentStem))


def testTwoReadsOfOneDocumentHoldNothingDifferently() -> None:
    assert listPackageDifferences(readDocument(), readDocument()) == []


def testAChangedMessageBodyIsListedWithItsMemberIdentifierAndType() -> None:
    before, after = readDocument(), readDocument()
    iwaFile = next(f for f in after.iwaFiles if f.name == "Index/Document.iwa")
    archive = iwaFile.archives[0]
    iwaFile.messageReplace(archive.identifier, 0, b"")

    assert listPackageDifferences(before, after) == [
        PackageDifference(
            "Index/Document.iwa", archive.identifier, "TN.DocumentArchive", "changed"
        )
    ]


def testAChangedObjectReferenceAloneIsListed() -> None:
    before, after = readDocument(), readDocument()
    iwaFile = next(f for f in after.iwaFiles if f.name == "Index/Document.iwa")
    archive = iwaFile.archives[0]
    iwaFile.archives[0] = replace(archive, infoBytes=archive.infoBytes + b"\x00")

    assert [d.change for d in listPackageDifferences(before, after)] == ["changed"]


def testAnArchiveOnlyOneSideHoldsIsAddedOrRemoved() -> None:
    whole, trimmed = readDocument(), readDocument()
    iwaFile = next(f for f in trimmed.iwaFiles if f.name == "Index/Document.iwa")
    dropped = iwaFile.archives.pop()

    removed = listPackageDifferences(whole, trimmed)
    added = listPackageDifferences(trimmed, whole)

    assert [(d.identifier, d.change) for d in removed] == [
        (dropped.identifier, "removed")
    ]
    assert [(d.identifier, d.change) for d in added] == [(dropped.identifier, "added")]


def testAChangedSupportingFileIsListedAsAWholeMember() -> None:
    before, after = readDocument(), readDocument()
    preview = after.otherMembers[0]
    after.otherMembers[0] = replace(preview, data=preview.data + b"\x00")

    assert listPackageDifferences(before, after) == [
        PackageDifference(preview.name, None, None, "changed")
    ]


def testADifferenceReadsAsOneReportLine() -> None:
    assert str(PackageDifference("preview.jpg", None, None, "changed")) == (
        "preview.jpg changed"
    )
    added = PackageDifference("Index/Document.iwa", 1, "TN.DocumentArchive", "added")
    assert str(added) == "Index/Document.iwa archive 1 (TN.DocumentArchive) added"

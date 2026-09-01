#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Writing a document back out, asserted archive by archive against what was read.

The comparison here is deliberately not a byte compare of the two files. The zip
envelope is known to differ by the local extra fields `zipfile` cannot emit, which
`test_archive_container` pins exactly, and a byte compare at this level would fail
for that reason on every fixture while saying nothing about the document inside.
So this module compares the decoded archive stream: same members in the same
order, same archives in the same order, same messages, same contents.

Where two message bodies differ byte for byte the comparison does not stop there.
Protobuf serialization is not canonical, so a body re-encoded from a parsed
message can differ from the bytes it came from while carrying identical fields.
Those are parsed and compared as messages. A type absent from the registry cannot
be parsed at all, so a byte difference on one is reported as a difference rather
than assumed to be a harmless re-encoding.

UPDATES
2026-09-01  Written for #2, AC 1: the unchanged round trip.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import shutil
from pathlib import Path

import pytest

import pybers
from pybers.archive import NumbersPackage, readPackage
from pybers.archive.types import archiveTypes
from pybers.model import Document
from pybers.writer import WriteError, writeDocument

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

allFixtures: list[Path] = sorted(fixtureDirectory.glob("*.numbers"))


def messagesAreEquivalent(typeId: int, before: bytes, after: bytes) -> bool:
    """Report whether two message bodies of the same type carry the same fields.

    Identical bytes settle it without parsing anything, which is the case for every
    archive of an untouched document. Differing bytes are only equivalent if the
    type is one this library can parse and both sides decode to the same message.
    """
    if before == after:
        return True
    messageClass = archiveTypes.get(typeId)
    if messageClass is None:
        return False
    first, second = messageClass(), messageClass()
    try:
        first.ParseFromString(before)
        second.ParseFromString(after)
    except Exception:
        return False
    return first == second


def archiveDifferences(before: NumbersPackage, after: NumbersPackage) -> list[str]:
    """Return every way two packages differ at the archive level, as readable lines.

    A list rather than a bare boolean, because a round trip that breaks needs to say
    which archive of which member went wrong. This format answers a wrong offset with
    a plausible wrong value rather than an error, and a failure reporting only "not
    equal" leaves the whole package to search by hand.
    """
    differences: list[str] = []

    beforeNames = [iwaFile.name for iwaFile in before.iwaFiles]
    afterNames = [iwaFile.name for iwaFile in after.iwaFiles]
    if beforeNames != afterNames:
        differences.append(
            f"IWA members differ: {beforeNames} became {afterNames}."
        )
        return differences

    for beforeFile, afterFile in zip(before.iwaFiles, after.iwaFiles):
        beforeIds = [archive.identifier for archive in beforeFile.archives]
        afterIds = [archive.identifier for archive in afterFile.archives]
        if beforeIds != afterIds:
            differences.append(
                f"{beforeFile.name}: {len(beforeIds)} archives became "
                f"{len(afterIds)}, or their order changed."
            )
            continue

        for beforeArchive, afterArchive in zip(beforeFile.archives, afterFile.archives):
            beforeShape = [(m.typeId, m.version) for m in beforeArchive.messages]
            afterShape = [(m.typeId, m.version) for m in afterArchive.messages]
            if beforeShape != afterShape:
                differences.append(
                    f"{beforeFile.name} archive {beforeArchive.identifier}: "
                    f"messages {beforeShape} became {afterShape}."
                )
                continue
            for index, (beforeMessage, afterMessage) in enumerate(
                zip(beforeArchive.messages, afterArchive.messages)
            ):
                if not messagesAreEquivalent(
                    beforeMessage.typeId, beforeMessage.data, afterMessage.data
                ):
                    differences.append(
                        f"{beforeFile.name} archive {beforeArchive.identifier} "
                        f"message {index} (type {beforeMessage.typeId}) changed: "
                        f"{len(beforeMessage.data)} bytes became "
                        f"{len(afterMessage.data)}."
                    )
    return differences


# ── AC 1: an unchanged document writes back unchanged ────────────────────────

def test_thereIsACorpusToWriteAtAll() -> None:
    """Guard the parametrization: an empty glob would make every case vacuous."""
    assert len(allFixtures) >= 40


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_everyFixtureWritesBackWithEveryArchiveUnchanged(
    path: Path, tmp_path: Path
) -> None:
    """AC 1 and AC 1.b: open, save with no edit, and every archive is equivalent.

    Numbers opening the result cleanly is the other half of AC 1 and is not
    assertable from pytest. It rests on the container round trip, confirmed by hand
    in Numbers 15.3.1 on 2026-08-16 and pinned by `test_archive_container`, which
    this path writes through unchanged.
    """
    destination = tmp_path / f"{path.stem}-saved.numbers"
    pybers.open(path).save(destination)

    differences = archiveDifferences(readPackage(path), readPackage(destination))
    assert not differences, (
        f"{path.name} did not survive an unchanged save:\n  "
        + "\n  ".join(differences)
    )


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_aSavedFixtureReadsBackAsTheSameDocument(path: Path, tmp_path: Path) -> None:
    """The model is equal across the round trip, which the archive check cannot see.

    Both fields holding archive state are excluded from equality, so this compares
    the sheets, tables and cells a caller actually works with.
    """
    destination = tmp_path / f"{path.stem}-saved.numbers"
    original = pybers.open(path)
    original.save(destination)

    assert original == pybers.open(destination)


def test_savingWithNoPathWritesBackWhereTheDocumentCameFrom(tmp_path: Path) -> None:
    """`doc.save()` is in place, which is what makes the common edit a two-liner."""
    working = tmp_path / "in-place.numbers"
    shutil.copy(fixtureDirectory / "00-baseline.numbers", working)

    document = pybers.open(working)
    document.save()

    assert not archiveDifferences(
        readPackage(fixtureDirectory / "00-baseline.numbers"), readPackage(working)
    )


def test_savingIsRepeatableAndLeavesTheDocumentUsable(tmp_path: Path) -> None:
    """There is no close and no invalidation, so a second save is an ordinary call."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")
    first = tmp_path / "first.numbers"
    second = tmp_path / "second.numbers"

    document.save(first)
    document.save(second)

    assert document.sheets, "the document stopped being usable after saving"
    assert not archiveDifferences(readPackage(first), readPackage(second))


# ── Refusals: a save that cannot be correct raises rather than guessing ──────

def test_savingADocumentThatWasNeverReadIsRefused() -> None:
    """A hand-built Document has no archives, so there is nothing to write back."""
    with pytest.raises(WriteError, match="carries no archives"):
        Document().save()


def test_savingInPlaceWithNoSourcePathIsRefused() -> None:
    """The package is present but the origin is not, so in place has no meaning."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")
    document._sourcePath = None

    with pytest.raises(WriteError, match="nowhere to save"):
        document.save()


def test_savingIntoAMissingDirectoryIsRefused(tmp_path: Path) -> None:
    """Named rather than left to an OSError from deep inside `zipfile`."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")

    with pytest.raises(WriteError, match="is not a directory"):
        document.save(tmp_path / "no-such-folder" / "out.numbers")


def test_aFailedSaveLeavesTheExistingFileIntact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason the write goes to a temporary name and then replaces the target.

    Saving over the document you are editing is the ordinary case, so a write that
    dies part way through must not be able to leave a truncated zip where the file
    used to be.
    """
    working = tmp_path / "precious.numbers"
    shutil.copy(fixtureDirectory / "00-baseline.numbers", working)
    before = working.read_bytes()

    document = pybers.open(working)

    def explode(package: NumbersPackage, path: Path) -> None:
        path.write_bytes(b"half a zip")
        raise OSError("the disk filled up half way through")

    monkeypatch.setattr("pybers.writer.writePackage", explode)

    with pytest.raises(OSError, match="disk filled up"):
        document.save()

    assert working.read_bytes() == before, "a failed save damaged the original"
    leftovers = [item.name for item in tmp_path.iterdir() if item.name != "precious.numbers"]
    assert not leftovers, f"a failed save left {leftovers} behind"


def test_writeDocumentIsTheSameCallAsSave(tmp_path: Path) -> None:
    """The function and the method are one path, so neither can drift from the other."""
    document = pybers.open(fixtureDirectory / "00-baseline.numbers")
    viaFunction = tmp_path / "function.numbers"
    viaMethod = tmp_path / "method.numbers"

    writeDocument(document, viaFunction)
    document.save(viaMethod)

    assert viaFunction.read_bytes() == viaMethod.read_bytes()

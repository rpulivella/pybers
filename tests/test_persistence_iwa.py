#!/usr/bin/env python3
"""\
The IWA write path: rebuilding an archive stream, framing it, and choosing between
replaying a member and rewriting one.

The sweep asserts the strongest property available: every one of the 2,549 IWA
members in the documents re-serializes byte for byte from its decoded archives. That
is what makes a rewrite trustworthy, since the only difference between a member
this library rewrites and the one Numbers wrote is then confined to the message
bodies that were deliberately changed.

The rest guards the two ways this can fail quietly. A member whose archives were
edited must not be written from `originalBytes`, which would discard the edit and
pass every round-trip test. A rewritten archive must keep the `ArchiveInfo`
fields this library does not model, which 40.2% of messages carry.

UPDATES
2026-09-01  Written for #2, alongside the IWA write path.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import zipfile
from pathlib import Path

import pytest

from conftest import allDocuments, findDocumentPath
from pybers._generated import TSPArchiveMessages_pb2 as archiveMessages
from pybers._persistence.iwa import (
    Archive,
    ArchiveMessage,
    IWAError,
    IWAFile,
    compressPayload,
    decompressPayload,
    readArchives,
    readIWAFile,
    splitFrames,
    uncompressedChunkLength,
    writeArchives,
    writeIWAFile,
)
from pybers._persistence.varint import readVarint


def readEveryMember(path: Path) -> list[tuple[str, bytes]]:
    """Return every IWA member of a document as its name and its raw bytes."""
    with zipfile.ZipFile(path) as archive:
        return [
            (info.filename, archive.read(info.filename))
            for info in archive.infolist()
            if info.filename.endswith(".iwa")
        ]


def readFirstMember(name: str = "00-baseline") -> IWAFile:
    """Read the first IWA member of a document, for the single-member cases."""
    memberName, data = readEveryMember(findDocumentPath(name))[0]
    return readIWAFile(memberName, data)


# ── The sweep: an archive stream rebuilds exactly ────────────────────────────

@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def test_everyArchiveStreamReSerializesByteIdentically(path: Path) -> None:
    """`writeArchives` is the exact inverse of `readArchives`, on real data."""
    members = readEveryMember(path)
    assert members, f"{path.name} holds no IWA members"
    for name, data in members:
        payload = decompressPayload(data)
        assert writeArchives(readArchives(payload)) == payload, (
            f"{path.name}/{name} did not rebuild to the same {len(payload)} bytes"
        )


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def test_framingSurvivesTheCompressor(path: Path) -> None:
    """A payload framed and re-read gives back exactly what went in."""
    for name, data in readEveryMember(path):
        payload = decompressPayload(data)
        assert decompressPayload(compressPayload(payload)) == payload, (
            f"{path.name}/{name} did not survive framing"
        )


def test_framingChunksAtSixtyFourKilobytes() -> None:
    """Apple emits a frame every 64 KiB, and a rewrite matches that chunking."""
    payload = bytes(range(256)) * ((uncompressedChunkLength * 2) // 256 + 10)
    frames = splitFrames(compressPayload(payload))

    expected = -(-len(payload) // uncompressedChunkLength)
    assert len(frames) == expected, f"expected {expected} frames, got {len(frames)}"
    assert decompressPayload(compressPayload(payload)) == payload


def test_anEmptyPayloadStillProducesOneFrame() -> None:
    """A member with no archives is a member, not an absent file."""
    assert len(splitFrames(compressPayload(b""))) == 1
    assert decompressPayload(compressPayload(b"")) == b""


# ── The silent-discard guard ─────────────────────────────────────────────────

def test_anUnmodifiedMemberReplaysItsOriginalBytes() -> None:
    """The exactness of the no-change round trip rests on this being a replay."""
    member = readFirstMember()
    assert member.modified is False
    assert writeIWAFile(member) == member.originalBytes


def test_aModifiedMemberIsRebuiltRatherThanReplayed() -> None:
    """The regression this guards: an edit written back as though it never happened.

    Before `modified` existed, `writeIWAFile` returned `originalBytes` whenever they
    were present, so a member whose archives had been edited wrote out unchanged and
    every round-trip assertion still passed. A test that only checks the payload
    decodes correctly cannot see that, which is why this one asserts the bytes
    themselves changed.
    """
    member = readFirstMember()
    target = member.archives[0]
    member.messageReplace(target.identifier, 0, target.messages[0].data + b"")

    rewritten = writeIWAFile(member)
    assert member.modified is True
    assert rewritten != member.originalBytes, "the edit was written back as a replay"
    assert decompressPayload(rewritten) == decompressPayload(member.originalBytes)


def test_anEditedBodyIsWhatComesBackOut() -> None:
    """The edit reaches the file rather than merely setting a flag."""
    member = readFirstMember()
    target = member.archives[0]
    replacement = b"\x08\x2a"
    member.messageReplace(target.identifier, 0, replacement)

    rebuilt = readArchives(decompressPayload(writeIWAFile(member)))
    found = next(a for a in rebuilt if a.identifier == target.identifier)
    assert found.messages[0].data == replacement


def test_aResizedBodyUpdatesTheDeclaredLength() -> None:
    """The stream is length-delimited, so a stale length desynchronizes everything."""
    member = readFirstMember()
    target = member.archives[0]
    replacement = target.messages[0].data + b"\x00" * 32
    member.messageReplace(target.identifier, 0, replacement)

    payload = decompressPayload(writeIWAFile(member))
    infoLength, offset = readVarint(payload, 0)
    info = archiveMessages.ArchiveInfo()
    info.ParseFromString(payload[offset:offset + infoLength])
    assert info.message_infos[0].length == len(replacement)


def test_unmodeledArchiveInfoFieldsSurviveARewrite() -> None:
    """`field_infos` and `object_references` are carried, never rebuilt from scratch.

    Measured on 2026-09-01, 40.2% of messages carry `field_infos` and 22.3% carry
    `object_references`. This library models neither, so a rewrite that reconstructed
    an `ArchiveInfo` from the identifier and the message shapes would erase them
    without any error.
    """
    member, carrier = None, None
    for path in allDocuments:
        for name, data in readEveryMember(path):
            candidate = readIWAFile(name, data)
            for archive in candidate.archives:
                info = archiveMessages.ArchiveInfo()
                info.ParseFromString(archive.infoBytes)
                if info.message_infos and info.message_infos[0].field_infos:
                    member, carrier = candidate, archive
                    break
            if carrier is not None:
                break
        if carrier is not None:
            break

    assert carrier is not None and member is not None, (
        "no archive in the documents carries field_infos"
    )
    before = archiveMessages.ArchiveInfo()
    before.ParseFromString(carrier.infoBytes)

    member.messageReplace(carrier.identifier, 0, carrier.messages[0].data + b"\x00")
    rebuilt = readArchives(decompressPayload(writeIWAFile(member)))
    found = next(a for a in rebuilt if a.identifier == carrier.identifier)

    after = archiveMessages.ArchiveInfo()
    after.ParseFromString(found.infoBytes)
    assert list(after.message_infos[0].field_infos) == list(
        before.message_infos[0].field_infos
    )
    assert list(after.message_infos[0].object_references) == list(
        before.message_infos[0].object_references
    )


# ── Refusals ─────────────────────────────────────────────────────────────────

def test_replacingAMessageOfAnUnknownArchiveIsRefused() -> None:
    member = readFirstMember()
    with pytest.raises(IWAError, match="no archive with identifier"):
        member.messageReplace(999_999_999, 0, b"")


def test_replacingAMessageIndexOutOfRangeIsRefused() -> None:
    member = readFirstMember()
    with pytest.raises(IWAError, match="out of range"):
        member.messageReplace(member.archives[0].identifier, 7, b"")


def test_aMemberWithNeitherBytesNorEditsIsRefused() -> None:
    """Building a member from scratch is not supported, and says so."""
    with pytest.raises(IWAError, match="nothing to write"):
        writeIWAFile(IWAFile(name="Index/Invented.iwa"))


def test_anArchiveWithNoStoredInfoIsRefused() -> None:
    """An archive that was never read cannot be written, because its info is gone."""
    invented = Archive(
        identifier=1,
        messages=(ArchiveMessage(typeId=1, version=(), data=b""),),
    )
    with pytest.raises(IWAError, match="carries no ArchiveInfo"):
        writeArchives([invented])

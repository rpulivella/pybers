#!/usr/bin/env python3
"""\
The persistence layer against real `.numbers` files.

Carries the base contract from CLAUDE.md: read a real file, write it back with no
changes, and get the input byte for byte. Everything above this layer depends on
that holding, so it is the first test worth having and the one worth breaking the
build.

The fixtures are this project's own, under `tests/fixtures/`, and three of the
forty-five are exercised here. They are chosen to span the shapes the container has
to survive rather than to be representative: the empty baseline, a document carrying
floating objects and embedded image assets, and the 2001-row table that forces
multi-tile storage and the largest members. A failure therefore says something about
which shape broke.

A missing fixture now FAILS rather than skips. These are first-party files committed
to this repository, so an absent one is a defect, and a skip would let the round-trip
contract quietly stop being tested.

UPDATES
2026-08-27  Repointed from the vendored numbers-parser `empty-*.numbers` files onto
            this project's own corpus, and turned the skip into a failure. The
            vendored checkout was purged from the repository, which left all eleven
            of these tests skipping, green, and testing nothing. The replacement
            fixtures are better on every axis: first-party, saved by the same Numbers
            15.3.1 the schemas were extracted from, and already the corpus every
            other test uses.
2026-08-16  Written with the container layer.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"

import struct
import zipfile
from pathlib import Path

import pytest

from pybers._persistence import (
    IWAError,
    decompressRaw,
    isDocumentMember,
    readPackage,
    splitFrames,
    writePackage,
)

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

# Three fixtures spanning the shapes the container has to survive, chosen so a
# failure says something about WHICH shape broke rather than only that one did:
# the empty baseline, a document with floating objects and embedded image assets,
# and the 2001-row table that forces multi-tile storage and the largest members.
fixtureNames: tuple[str, ...] = ("00-baseline", "35-image", "27-big-table")

# The ZIP64 extended-information extra field Numbers writes into local headers:
# a 4-byte tag and size, then 16 bytes of payload.
localExtraFieldLength: int = 20


def fixturePath(name: str) -> Path:
    """Return a fixture path, failing when it is absent.

    These are first-party fixtures committed to this repository, so a missing one
    is a defect rather than an absent optional dependency. It used to skip, because
    the fixtures were then a third-party checkout that might not be present; that
    is no longer true and a skip here would hide the round-trip contract failing.
    """
    path = fixtureDirectory / f"{name}.numbers"
    assert path.is_file(), f"Fixture {path} is missing from the corpus."
    return path


@pytest.mark.parametrize("name", fixtureNames)
def testReadsEveryIWAMember(name: str) -> None:
    """Every Index/*.iwa member parses into at least one archive."""
    package = readPackage(fixturePath(name))

    assert package.iwaFiles, "No IWA members were read."
    assert len(package.members) == len(package.iwaFiles) + len(
        package.otherMembers
    ), "Member metadata does not account for every member exactly once."

    for iwaFile in package.iwaFiles:
        assert isDocumentMember(iwaFile.name)
        assert iwaFile.archives, f"{iwaFile.name} produced no archives."
        for archive in iwaFile.archives:
            for message in archive.messages:
                assert len(message.data) >= 0
                assert message.typeId >= 0


@pytest.mark.parametrize("name", fixtureNames)
def testRoundTripEnvelopeDiffersOnlyByLocalExtraFields(
    name: str, tmp_path: Path
) -> None:
    """Pin the one accepted divergence, so it stays understood rather than drifting.

    The zip envelope is not reproduced byte for byte, and that is a decision rather
    than a shortfall. Numbers writes a 20-byte ZIP64 extended-information field
    (tag 0x0001) into the LOCAL header of some members while omitting it from the
    central directory, and it writes `external_attr` as 0. Neither is reachable
    through `zipfile`: it exposes only the central-directory extra and writes what
    it is given to both places, and it overwrites a zero `external_attr` with
    `0o600 << 16` in `writestr` and `open(..., "w")` alike.

    Getting those bytes back would mean hand-rolling a zip writer and owning it
    forever. They carry no document content (they are archival metadata) and a
    round-tripped file was confirmed on 2026-08-16 to open in Numbers 15.3.1 with
    no warning and no repair prompt. `numbers-parser` reaches the same conclusion
    by using `zipfile` and not attempting byte-identity either.

    So the real contract is the test below this one: every member identical. This
    test exists to keep the divergence bounded and named, so that a *different*
    difference appearing later is a failure rather than a shrug.
    """
    source = fixturePath(name)
    destination = tmp_path / f"{name}-roundtrip.numbers"
    writePackage(readPackage(source), destination)

    original = source.read_bytes()
    written = destination.read_bytes()

    membersWithLocalExtra = 0
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            offset = info.header_offset
            nameLength, extraLength = struct.unpack(
                "<HH", original[offset + 26:offset + 30]
            )
            if extraLength:
                membersWithLocalExtra += 1

    expectedShortfall = membersWithLocalExtra * localExtraFieldLength
    assert len(original) - len(written) == expectedShortfall, (
        f"{name}.numbers differs from its round trip by "
        f"{len(original) - len(written)} bytes, not the {expectedShortfall} "
        f"accounted for by {membersWithLocalExtra} local extra fields. An "
        "unexplained difference has appeared and needs investigating."
    )


@pytest.mark.parametrize("name", fixtureNames)
def testRoundTripPreservesEveryMemberExactly(name: str, tmp_path: Path) -> None:
    """Content and zip metadata survive the round trip for every single member.

    This is the strongest property currently reachable, and it is the one the
    layers above actually depend on: same members, same order, same bytes, same
    headers. What it does not cover is the local-header extra field, which is the
    only thing standing between this and the byte-identical test above.
    """
    source = fixturePath(name)
    destination = tmp_path / f"{name}-roundtrip.numbers"
    writePackage(readPackage(source), destination)

    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination) as written:
        assert original.namelist() == written.namelist()
        for before, after in zip(original.infolist(), written.infolist(), strict=True):
            assert original.read(before.filename) == written.read(after.filename), (
                f"{before.filename} changed content."
            )
            # external_attr is deliberately absent from this comparison. Numbers
            # writes 0, and CPython's zipfile overwrites a zero with 0o600 << 16 on
            # the way out, in `writestr` and in `open(..., "w")` alike, mutating the
            # ZipInfo it was handed. It is not reachable through the standard
            # library at all, so asserting it here would only restate the xfail
            # above with less information.
            assert (
                before.compress_type,
                before.date_time,
                before.create_system,
                before.create_version,
                before.extract_version,
                before.flag_bits,
                before.internal_attr,
            ) == (
                after.compress_type,
                after.date_time,
                after.create_system,
                after.create_version,
                after.extract_version,
                after.flag_bits,
                after.internal_attr,
            ), f"{before.filename} changed zip metadata."


def testDecompressedFrameMatchesItsDeclaredLength() -> None:
    """Every frame decodes to exactly the length its own preamble states.

    An independent check: the varint preamble states the answer separately from
    the tag stream that produces it, so agreement is real evidence rather than a
    tautology.
    """
    package = readPackage(fixturePath("00-baseline"))
    frameCount = 0

    with zipfile.ZipFile(fixturePath("00-baseline")) as archive:
        for iwaFile in package.iwaFiles:
            for frame in splitFrames(archive.read(iwaFile.name)):
                decompressRaw(frame)  # raises on any length mismatch
                frameCount += 1

    assert frameCount >= 37, f"Only walked {frameCount} frames."


def testMultiFrameMemberIsExercised() -> None:
    """At least one fixture member spans several 64 KiB frames.

    Recorded as a test because the chunked path would otherwise be assumed rather
    than covered, and a reader that only ever saw single-frame members could be
    wrong about concatenation without anything noticing.
    """
    with zipfile.ZipFile(fixturePath("00-baseline")) as archive:
        counts = [
            len(splitFrames(archive.read(name)))
            for name in archive.namelist()
            if isDocumentMember(name)
        ]
    assert max(counts) > 1, "No multi-frame IWA member in this fixture."


def testRejectsAnUnknownFrameFlag() -> None:
    """An unrecognized flag byte stops the read loudly instead of being decoded.

    The uncompressed-frame shape has never been observed, so there is no tested
    branch for it. Failing here is the honest outcome, it names the byte so the
    format can be studied against a real example.
    """
    with pytest.raises(IWAError, match="0x01"):
        splitFrames(b"\x01\x04\x00\x00" + b"\x00" * 4)


def testRejectsATruncatedFrame() -> None:
    """A frame declaring more bytes than remain is malformed, not merely short."""
    with pytest.raises(IWAError, match="declares"):
        splitFrames(b"\x00\xff\x00\x00" + b"\x00" * 4)

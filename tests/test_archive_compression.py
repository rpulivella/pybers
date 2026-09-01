#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
The Snappy encoder, checked against the decoder that has to read what it writes.

Every assertion here is an identity: whatever goes in comes back out. That is the
only property the format promises, because Snappy has no canonical encoding and
Apple's output is one valid answer among many. Matching Apple byte for byte is
therefore not a goal and is not tested for.

The corpus sweep is the real test. It runs the encoder over all 2,811 frames of
all 46 fixtures, which is around 20 MB of real protobuf, and demands the decoder
return each one exactly. Synthetic inputs cover the shapes real data does not
reach: empty, shorter than a match, a single repeated byte, and lengths sitting on
each tag boundary.

UPDATES
2026-09-01  Written for #2, alongside the encoder.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import random
import zipfile
from pathlib import Path

import pytest

from pybers.archive.compression import (
    SnappyError,
    compressRaw,
    decompressRaw,
    readVarint,
    writeVarint,
)
from pybers.archive.iwa import splitFrames

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

allFixtures: list[Path] = sorted(fixtureDirectory.glob("*.numbers"))


def everyFrameOf(path: Path) -> list[bytes]:
    """Return every IWA frame of a fixture, already decompressed."""
    payloads: list[bytes] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.filename.endswith(".iwa"):
                continue
            for frame in splitFrames(archive.read(info.filename)):
                payloads.append(decompressRaw(frame))
    return payloads


# ── Varints: the encoder is the stated inverse of the decoder ────────────────

@pytest.mark.parametrize(
    "value", [0, 1, 127, 128, 129, 300, 16383, 16384, 65535, 2**31, 2**63 - 1]
)
def test_aVarintRoundTripsThroughBothHalves(value: int) -> None:
    encoded = writeVarint(value)
    decoded, offset = readVarint(encoded, 0)
    assert decoded == value
    assert offset == len(encoded), "the decoder consumed a different span"


def test_aNegativeVarintIsRefusedRatherThanTruncated() -> None:
    """There is no negative varint, and a silent wrap would encode a huge length."""
    with pytest.raises(SnappyError, match="negative"):
        writeVarint(-1)


# ── The identity that matters: whatever is encoded decodes back ──────────────

@pytest.mark.parametrize(
    "length", [0, 1, 2, 3, 4, 5, 11, 12, 59, 60, 61, 63, 64, 67, 68, 255, 256, 65536]
)
def test_incompressibleInputOfEveryTagBoundaryLengthSurvives(length: int) -> None:
    """Random bytes cannot be matched, so this exercises the literal tags alone.

    The lengths are the boundaries of the literal encoding: 59 is the largest that
    fits inline, and each power-of-two crossing adds a length byte.
    """
    blob = random.Random(length).randbytes(length)
    assert decompressRaw(compressRaw(blob)) == blob


@pytest.mark.parametrize(
    "length", [4, 5, 11, 12, 63, 64, 67, 68, 69, 128, 1000, 70000]
)
def test_aSingleRepeatedByteSurvives(length: int) -> None:
    """The maximally compressible input, and the one that splits a long copy.

    A run this uniform is encoded as one literal and then copies that overlap
    themselves, so it exercises both the run splitting in `emitCopy` and the
    overlapping path in the decoder.
    """
    blob = b"\xa5" * length
    assert decompressRaw(compressRaw(blob)) == blob


def test_aRepeatingPatternLongerThanOneCopyTagSurvives() -> None:
    """Lengths past 64 must split into several tags without losing a byte."""
    blob = (b"pybers-" * 5000)[:35000]
    assert decompressRaw(compressRaw(blob)) == blob


def test_matchesReachingBackPastTheShortCopyWindowSurvive() -> None:
    """A copy offset above 2047 cannot use the one-byte form and must widen."""
    blob = random.Random(7).randbytes(9000)
    doubled = blob + blob
    assert decompressRaw(compressRaw(doubled)) == doubled


@pytest.mark.parametrize("path", allFixtures, ids=lambda path: path.stem)
def test_everyFrameOfEveryFixtureReEncodesToItself(path: Path) -> None:
    """The sweep: real protobuf payloads, encoded by us, decoded by us."""
    payloads = everyFrameOf(path)
    assert payloads, f"{path.name} yielded no frames to encode"
    for index, payload in enumerate(payloads):
        assert decompressRaw(compressRaw(payload)) == payload, (
            f"{path.name} frame {index} of {len(payloads)} did not survive"
        )


# ── Size: the reason this is a matcher and not a literal emitter ─────────────

def test_theEncoderKeepsEmittingBackReferences() -> None:
    """Guard the ratio, so a regression to literals is caught rather than shipped.

    Measured across the whole corpus on 2026-09-01: Apple 0.183x, pybers 0.182x.
    An all-literal encoder measures 1.001x, which is what this exists to exclude.
    The bound is deliberately loose, because the encoder is free to change how it
    matches and is not free to stop matching.
    """
    original = 0
    encoded = 0
    for path in allFixtures:
        for payload in everyFrameOf(path):
            original += len(payload)
            encoded += len(compressRaw(payload))

    assert original > 10_000_000, "the corpus shrank; this bound means nothing now"
    assert encoded / original < 0.30, (
        f"the encoder reached {encoded / original:.3f}x, well above the 0.182x "
        "measured when it was written. It has stopped emitting back-references."
    )

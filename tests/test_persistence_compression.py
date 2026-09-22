#!/usr/bin/env python3
"""\
The Snappy encoder, checked against the decoder that has to read what it writes.

Every assertion here is an identity: whatever goes in comes back out. That is the
only property the format promises, because Snappy has no canonical encoding and
Apple's output is one valid answer among many. Matching Apple byte for byte is
therefore not a goal and is not tested for.

The sweep across every document is the real test. It runs the encoder over all 2,811
frames of all 46 documents, which is around 20 MB of real protobuf, and demands the
decoder return each one exactly. Synthetic inputs cover the shapes real data does not
reach: empty, shorter than a match, a single repeated byte, and lengths sitting on each
tag boundary.

UPDATES
2026-09-01  Written for #2, alongside the encoder.
2026-09-01  Varints moved to test_varint.py with the code they cover.
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

from conftest import allDocuments
from pybers._persistence.compression import compressRaw, decompressRaw
from pybers._persistence.iwa import splitFrames


def readEveryCompressedFrame(path: Path) -> list[bytes]:
    """Return every IWA frame of a document as Apple compressed it."""
    frames: list[bytes] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.filename.endswith(".iwa"):
                frames.extend(splitFrames(archive.read(info.filename)))
    return frames


def readEveryFrame(path: Path) -> list[bytes]:
    """Return every IWA frame of a document, already decompressed."""
    payloads: list[bytes] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.filename.endswith(".iwa"):
                continue
            for frame in splitFrames(archive.read(info.filename)):
                payloads.append(decompressRaw(frame))
    return payloads


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


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def test_everyFrameOfEveryDocumentReEncodesToItself(path: Path) -> None:
    """The sweep: real protobuf payloads, encoded by us, decoded by us."""
    payloads = readEveryFrame(path)
    assert payloads, f"{path.name} yielded no frames to encode"
    for index, payload in enumerate(payloads):
        assert decompressRaw(compressRaw(payload)) == payload, (
            f"{path.name} frame {index} of {len(payloads)} did not survive"
        )


# ── Size: the reason this is a matcher and not a literal emitter ─────────────

def test_theEncoderKeepsEmittingBackReferences() -> None:
    """Guard the ratio against Apple's own, so a regression to literals is caught.

    Measured against Apple on the same payloads rather than a fixed bound, because
    the ratio depends on what the documents hold: a table of 100,000 rows carries
    as many random row identities, which compress to 0.59x for both encoders. On
    2026-09-21 Apple reached 0.318x across every document and pybers 0.316x. An
    all-literal encoder measures 1.001x, which is what this exists to exclude.
    """
    original = 0
    apple = 0
    encoded = 0
    for path in allDocuments:
        for frame in readEveryCompressedFrame(path):
            payload = decompressRaw(frame)
            original += len(payload)
            apple += len(frame)
            encoded += len(compressRaw(payload))

    assert original > 10_000_000, "the documents shrank; this bound means nothing now"
    assert encoded / original < apple / original * 1.10, (
        f"the encoder reached {encoded / original:.3f}x where Apple reaches "
        f"{apple / original:.3f}x on the same payloads. It has stopped emitting "
        "back-references."
    )

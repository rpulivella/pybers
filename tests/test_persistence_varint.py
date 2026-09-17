#!/usr/bin/env python3
"""\
Base-128 varints, checked as an exact inverse pair and against real archive streams.

The synthetic cases sit on the boundaries where the encoding grows a byte, which is
where an off-by-one in the shift arithmetic would show. The sweep across every document
is the one that matters most: every archive in every document is reached by reading a
varint, so a bad decode desynchronizes the whole stream rather than raising.

UPDATES
2026-09-01  Split out of the Snappy codec's tests with the code they cover.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import pytest

from pybers._persistence.varint import VarintError, readVarint, writeVarint


@pytest.mark.parametrize(
    "value",
    [0, 1, 127, 128, 129, 300, 16383, 16384, 65535, 2**21 - 1, 2**21, 2**31, 2**63 - 1],
)
def test_aVarintRoundTripsThroughBothHalves(value: int) -> None:
    """The boundaries are where the encoding grows a byte: 127, 16383 and so on."""
    encoded = writeVarint(value)
    decoded, offset = readVarint(encoded, 0)
    assert decoded == value
    assert offset == len(encoded), "the decoder consumed a different span"


def test_theEncodingIsSevenBitsPerByteWithAContinuationFlag() -> None:
    """Pinned against the wire format rather than against our own decoder."""
    assert writeVarint(0) == b"\x00"
    assert writeVarint(1) == b"\x01"
    assert writeVarint(127) == b"\x7f"
    assert writeVarint(128) == b"\x80\x01"
    assert writeVarint(300) == b"\xac\x02"


def test_aVarintIsReadFromAnOffsetAndReportsWhereItEnded() -> None:
    """Callers read a varint out of the middle of a buffer, never from byte zero."""
    buffer = b"\xff\xff" + writeVarint(300) + b"tail"
    value, offset = readVarint(buffer, 2)
    assert value == 300
    assert buffer[offset:] == b"tail"


def test_aNegativeValueIsRefusedRatherThanWrapped() -> None:
    """There is no negative varint, and a silent wrap would encode a huge length."""
    with pytest.raises(VarintError, match="negative"):
        writeVarint(-1)


def test_aVarintRunningPastTheBufferIsRefused() -> None:
    """Every byte sets the continuation flag, so the value never terminates."""
    with pytest.raises(VarintError, match="ran past the end"):
        readVarint(b"\x80\x80\x80", 0)


def test_anOverlongVarintIsRefused() -> None:
    """Past 64 bits it is a misread rather than a large number, so it stops."""
    with pytest.raises(VarintError, match="longer than 64 bits"):
        readVarint(b"\x80" * 12 + b"\x01", 0)


def test_theErrorNamesVarintsRatherThanSnappy() -> None:
    """The reason for the split. These sat in the Snappy codec and reported one.

    An `ArchiveInfo` length prefix that fails to read has nothing to do with Snappy,
    and naming the wrong subsystem in the one message someone reads while debugging
    is a real cost.
    """
    with pytest.raises(VarintError) as failure:
        readVarint(b"\x80", 0)
    assert "Snappy" not in str(failure.value)

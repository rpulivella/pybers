#!/usr/bin/env python3
"""\
Base-128 varints, the length prefix two unrelated layers of this format both use.

A raw Snappy block opens with one stating its uncompressed length, and an IWA
archive stream prefixes every `ArchiveInfo` with one. The two have nothing else in
common, which is exactly why this lives in its own module: it belonged to neither,
and it sat in the Snappy codec only because that was the first layer to need it.
A varint that ran past the end of an archive stream reported a Snappy error, which
named the wrong subsystem in the one message someone would be reading to find out
what went wrong.

The encoding is protobuf's own, seven bits of payload per byte with the top bit
marking continuation, little-endian.

UPDATES
2026-09-01  Split out of pybers._persistence.compression, for #2.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

from ..errors import PybersError

# A varint carrying more than this many value bits is a misread rather than a large
# number, since nothing in this format needs a 64-bit length.
maximumShift: int = 63


class VarintError(PybersError, RuntimeError):
    """A varint that could not be read, or a value that cannot be written as one."""


def readVarint(data: bytes, offset: int) -> tuple[int, int]:
    """Read one base-128 varint, returning its value and the offset after it.

    The offset comes back because a varint has no fixed width, so the caller cannot
    know where the next field starts without being told.
    """
    value = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise VarintError("Varint ran past the end of the buffer.")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > maximumShift:
            raise VarintError("Varint is longer than 64 bits.")


def writeVarint(value: int) -> bytes:
    """Encode a non-negative integer as a base-128 varint.

    The inverse of `readVarint`, and kept beside it so the two cannot drift.
    """
    if value < 0:
        raise VarintError(f"A varint cannot carry the negative value {value}.")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
            continue
        out.append(byte)
        return bytes(out)

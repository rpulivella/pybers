#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
Snappy raw-block codec for IWA payloads.

Apple stores each IWA frame as a **raw** Snappy block: a varint stating the
uncompressed length, then a stream of literal and copy tags. This is not the
Snappy *framing* format (no stream header, no per-chunk CRC), so a library that
only implements framing cannot read it.

Implemented here rather than taken from `python-snappy` on purpose. That package
binds to libsnappy through a C extension, which means anyone running
`pip install pybers` needs a compiler and the library present, a heavy price for
a format whose decoder is this small. The decoder is also self-checking: the
varint preamble states the uncompressed length independently of the tag stream,
so a decode that drifts is caught rather than returning plausible garbage.

Only decompression lives here. Writing a file back does not need a compressor,
because an unmodified frame is written from the bytes it was read from, see
`pybers.archive.iwa`. A compressor is needed only once a frame is genuinely
rewritten, and a correct one is a separate piece of work.

UPDATES
2026-08-16  Written. Validated against all 213 frames of empty-1/2/3.numbers:
            every frame decoded to exactly its declared uncompressed length.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"


class SnappyError(RuntimeError):
    """A raw Snappy block that could not be decoded."""


def readVarint(data: bytes, offset: int) -> tuple[int, int]:
    """Read one base-128 varint, returning its value and the offset after it.

    Shared with the IWA message reader, which length-prefixes every archive the
    same way, so the two formats are decoded by one implementation rather than
    two that could disagree.
    """
    value = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise SnappyError("Varint ran past the end of the buffer.")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            raise SnappyError("Varint is longer than 64 bits.")


def decompressRaw(block: bytes) -> bytes:
    """Decode one raw Snappy block.

    The declared length is verified against what the tag stream actually produced.
    They are two independent statements of the same fact, so a mismatch means the
    block was misframed or truncated, worth raising over, because the alternative
    is handing a protobuf parser bytes that are subtly wrong.
    """
    expectedLength, offset = readVarint(block, 0)
    out = bytearray()

    while offset < len(block):
        tag = block[offset]
        kind = tag & 0x03

        if kind == 0:
            length = tag >> 2
            offset += 1
            # 60 and above is an escape: the value says how many little-endian
            # bytes follow that carry the real length, rather than being it.
            if length >= 60:
                extraBytes = length - 59
                length = int.from_bytes(block[offset:offset + extraBytes], "little")
                offset += extraBytes
            length += 1
            out += block[offset:offset + length]
            offset += length
            continue

        if kind == 1:
            length = 4 + ((tag >> 2) & 0x07)
            copyOffset = ((tag >> 5) << 8) | block[offset + 1]
            offset += 2
        elif kind == 2:
            length = (tag >> 2) + 1
            copyOffset = int.from_bytes(block[offset + 1:offset + 3], "little")
            offset += 3
        else:
            length = (tag >> 2) + 1
            copyOffset = int.from_bytes(block[offset + 1:offset + 5], "little")
            offset += 5

        if copyOffset == 0 or copyOffset > len(out):
            raise SnappyError(
                f"Copy offset {copyOffset} reaches outside the {len(out)} bytes "
                "decoded so far."
            )

        start = len(out) - copyOffset
        if copyOffset >= length:
            # Non-overlapping, so the whole run can be taken in one slice.
            out += out[start:start + length]
        else:
            # Overlapping copies are legal and are how Snappy encodes a repeating
            # run, so this must read bytes it is in the middle of writing. A slice
            # would capture the pre-copy state and repeat the wrong thing.
            for index in range(length):
                out.append(out[start + index])

    if len(out) != expectedLength:
        raise SnappyError(
            f"Block declared {expectedLength} bytes but decoded to {len(out)}."
        )
    return bytes(out)

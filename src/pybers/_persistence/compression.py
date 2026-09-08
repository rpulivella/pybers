#!/usr/bin/env python3
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

An unmodified frame is still written from the bytes it was read from, see
`pybers._persistence.iwa`, so the encoder here runs only on a frame that was genuinely
rewritten. It emits back-references rather than a stream of literals because the
difference is large: measured across the 2,811 frames of the fixture corpus on
2026-09-01, Apple's own encoder reaches 0.183x and an all-literal encoding measures
1.001x, so a rewritten member would arrive 5.5 times larger than Numbers writes it.

The encoder is not required to reproduce Apple's byte-for-byte output and does not
try to. Snappy has many valid encodings of the same input, the format carries no
canonical form, and the unchanged round trip never reaches this code.

UPDATES
2026-08-16  Written. Validated against all 213 frames of empty-1/2/3.numbers:
            every frame decoded to exactly its declared uncompressed length.
2026-09-01  Added the encoder for #2, so a rewritten frame can be stored.
2026-09-01  Varints moved to pybers._persistence.varint, which the IWA archive
            stream needs as much as this codec does.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"

from ..errors import PybersError
from .varint import readVarint, writeVarint


class SnappyError(PybersError, RuntimeError):
    """A raw Snappy block that could not be decoded."""


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


# A copy tag carries its offset in one, two or four bytes. Every block written here
# stays inside one 64 KB frame, so a two-byte offset always reaches and the
# four-byte form is never needed.
shortCopyMaximumOffset: int = 2047
shortCopyMinimumLength: int = 4
shortCopyMaximumLength: int = 11

# `kind 2` states its length in six bits, biased by one, so 64 is the longest run
# a single copy tag can express.
copyMaximumLength: int = 64

# A literal tag states its length in six bits, biased by one. From 60 upward the
# value is an escape saying how many little-endian length bytes follow instead.
literalInlineMaximum: int = 59

# The shortest run worth a copy tag. Snappy matches on four bytes because a
# shorter one cannot beat the literal it would replace.
minimumMatchLength: int = 4

# Match extension walks in blocks before it walks in bytes. Pure Python pays per
# iteration rather than per byte, and the corpus is full of long runs, so
# comparing a slice at a time is what keeps a rewrite off the critical path.
matchStrideLength: int = 16


def emitLiteral(out: bytearray, data: bytes, start: int, end: int) -> None:
    """Append the bytes from `start` to `end` as one literal run.

    Taken as offsets rather than as a slice because the caller already holds the
    whole buffer, and slicing it on every run copies the input a second time.
    """
    length = end - start
    if length <= 0:
        return
    encoded = length - 1
    if encoded <= literalInlineMaximum:
        out.append(encoded << 2)
    else:
        extraBytes = (encoded.bit_length() + 7) // 8
        out.append((literalInlineMaximum + extraBytes) << 2)
        out += encoded.to_bytes(extraBytes, "little")
    out += data[start:end]


def emitCopy(out: bytearray, offset: int, length: int) -> None:
    """Append one back-reference of `length` bytes reaching `offset` bytes back.

    A run longer than a single tag can state is split rather than truncated. The
    60-byte step exists so the remainder can never land on one, two or three
    bytes, which no copy tag can express.
    """
    while length >= copyMaximumLength + shortCopyMinimumLength:
        out.append(((copyMaximumLength - 1) << 2) | 0x02)
        out += offset.to_bytes(2, "little")
        length -= copyMaximumLength
    if length > copyMaximumLength:
        out.append(((60 - 1) << 2) | 0x02)
        out += offset.to_bytes(2, "little")
        length -= 60
    if (
        shortCopyMinimumLength <= length <= shortCopyMaximumLength
        and offset <= shortCopyMaximumOffset
    ):
        out.append(
            ((offset >> 8) << 5) | ((length - shortCopyMinimumLength) << 2) | 0x01
        )
        out.append(offset & 0xFF)
        return
    out.append(((length - 1) << 2) | 0x02)
    out += offset.to_bytes(2, "little")


def matchLength(data: bytes, candidate: int, current: int, limit: int) -> int:
    """Return how many bytes agree from `candidate` and `current` up to `limit`.

    Both positions are known to share their first four bytes, so the walk starts
    past them.
    """
    length = minimumMatchLength
    while current + length + matchStrideLength <= limit and (
        data[candidate + length:candidate + length + matchStrideLength]
        == data[current + length:current + length + matchStrideLength]
    ):
        length += matchStrideLength
    while (
        current + length < limit
        and data[candidate + length] == data[current + length]
    ):
        length += 1
    return length


def compressRaw(data: bytes) -> bytes:
    """Encode one raw Snappy block: a length varint, then literal and copy tags.

    A greedy matcher over a table of four-byte sequences, which is the shape the
    reference encoder uses. Only the position a scan lands on is recorded, never
    the positions swallowed by a match, so a long run costs one table write rather
    than hundreds. That gives up some ratio for a large reduction in work, and the
    ratio it gives up is small on this data.

    Correctness does not rest on the table at all. Every emitted copy is verified
    against the input before it is written, so a table that returns a stale or
    useless position produces a literal rather than a wrong byte.
    """
    out = bytearray(writeVarint(len(data)))
    limit = len(data)
    # A match needs four bytes to key on, so the scan stops that far from the end
    # and the tail leaves as a literal.
    scanLimit = limit - minimumMatchLength
    table: dict[bytes, int] = {}
    position = 0
    literalStart = 0

    while position <= scanLimit:
        key = data[position:position + minimumMatchLength]
        candidate = table.get(key, -1)
        table[key] = position
        # A block is at most one 64 KB frame, so any hit is already within reach
        # of a two-byte offset. The equality check is what makes a stale entry
        # harmless rather than corrupting.
        if candidate < 0 or data[candidate:candidate + minimumMatchLength] != key:
            position += 1
            continue
        length = matchLength(data, candidate, position, limit)
        emitLiteral(out, data, literalStart, position)
        emitCopy(out, position - candidate, length)
        position += length
        literalStart = position

    emitLiteral(out, data, literalStart, limit)
    return bytes(out)

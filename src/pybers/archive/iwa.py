#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
IWA files: compressed frames wrapping a stream of length-prefixed archives.

One `.iwa` member is a sequence of frames. Each frame is a four-byte header, a
flag byte, then a three-byte little-endian compressed length, followed by that
many bytes of raw Snappy. Concatenating every decompressed frame gives the
payload, which is a stream of archives, each one a varint-prefixed `ArchiveInfo`
followed by the message bodies its `message_infos` describe.

Message bodies are kept as **raw bytes**, deliberately, and are not parsed here.
Two reasons. Deciding which protobuf class a `type` identifier maps to is a
separate concern with its own source of truth, and it does not belong in the
layer that finds message boundaries. More importantly, protobuf re-serialization
is not guaranteed to reproduce the input byte for byte, field ordering and
varint encoding both have latitude, so a reader that parsed eagerly could not
promise the round trip this library is built around.

For the same reason an unmodified file writes back from `originalBytes` rather
than being re-encoded. That makes the no-change round trip exact by construction
rather than by hoping a compressor matches Apple's, and it is why this module
needs no Snappy compressor at all.

UPDATES
2026-08-16  Written. Verified against empty-1/2/3.numbers: every archive stream
            ends exactly on the final byte of its payload.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"

from dataclasses import dataclass, field

from .._generated import TSPArchiveMessages_pb2 as archiveMessages
from .compression import decompressRaw, readVarint

# The frame header is one flag byte plus a three-byte little-endian length.
frameHeaderLength: int = 4

# The only flag byte ever observed. Snappy's own framing format uses a similar
# leading byte to mark a chunk as stored rather than compressed, so an uncompressed
# IWA frame is conceivable: but none exists in any file examined here, and the
# reference implementation raises on this too rather than handling it.
#
# Deliberately an assertion and not a second code path. Writing a stored-frame
# branch would mean shipping a decoder for a shape nothing can test, which is how
# untested code comes to be trusted. A file that carries one should stop this
# library loudly and name the byte, so the format can be studied and the branch
# written against a real example.
compressedFrameFlag: int = 0x00

# Apple emits a fresh frame every 64 KiB of uncompressed payload. Recorded because
# a rewriter has to reproduce the same chunking to stand any chance of matching.
uncompressedChunkLength: int = 65536


class IWAError(RuntimeError):
    """An IWA member whose framing or archive stream could not be read."""


@dataclass(frozen=True)
class ArchiveMessage:
    """One protobuf message body, with the type identifier that selects its class.

    `data` stays raw. Resolving `typeId` to a generated message class belongs to
    the layer that owns the type registry, not to this one.
    """

    typeId: int
    version: tuple[int, ...]
    data: bytes


@dataclass(frozen=True)
class Archive:
    """One addressable object: its identifier and the messages that describe it.

    The identifier is what cross-references elsewhere in the document point at,
    which is what makes this the unit worth modeling rather than the frame.
    """

    identifier: int
    messages: tuple[ArchiveMessage, ...]


@dataclass
class IWAFile:
    """One `.iwa` member, holding both its archives and the bytes it came from.

    `originalBytes` is kept so an untouched file serializes back exactly. Not an
    optimization: it is the only way to guarantee byte-identical output without a
    Snappy compressor that matches Apple's own choices tag for tag.
    """

    name: str
    archives: list[Archive] = field(default_factory=list)
    originalBytes: bytes = b""


def splitFrames(data: bytes) -> list[bytes]:
    """Split an IWA member into its raw compressed frames.

    A member that does not end exactly on a frame boundary is malformed rather
    than merely surprising, so this raises instead of returning what it managed
    to read.
    """
    frames: list[bytes] = []
    offset = 0
    while offset < len(data):
        if offset + frameHeaderLength > len(data):
            raise IWAError(
                f"Truncated frame header at byte {offset} of {len(data)}."
            )
        flag = data[offset]
        if flag != compressedFrameFlag:
            raise IWAError(
                f"Frame at byte {offset} has flag 0x{flag:02x}, not "
                f"0x{compressedFrameFlag:02x}. No file examined has ever carried "
                "another value, so this one is worth studying rather than guessing at."
            )
        compressedLength = int.from_bytes(data[offset + 1:offset + 4], "little")
        start = offset + frameHeaderLength
        end = start + compressedLength
        if end > len(data):
            raise IWAError(
                f"Frame at byte {offset} declares {compressedLength} bytes but only "
                f"{len(data) - start} remain."
            )
        frames.append(data[start:end])
        offset = end
    return frames


def decompressPayload(data: bytes) -> bytes:
    """Return the full uncompressed payload of an IWA member."""
    return b"".join(decompressRaw(frame) for frame in splitFrames(data))


def readArchives(payload: bytes) -> list[Archive]:
    """Parse a decompressed payload into its archives.

    Each archive is a varint-prefixed `ArchiveInfo` followed by one body per
    entry in its `message_infos`, laid end to end with no padding, so the
    lengths are the only thing separating them, and a wrong one desynchronizes
    everything after it. Ending anywhere but exactly on the final byte therefore
    means the parse went wrong earlier, and is raised rather than ignored.
    """
    archives: list[Archive] = []
    offset = 0

    while offset < len(payload):
        infoLength, offset = readVarint(payload, offset)
        info = archiveMessages.ArchiveInfo()
        try:
            info.ParseFromString(payload[offset:offset + infoLength])
        except Exception as exc:
            raise IWAError(
                f"Could not parse ArchiveInfo of {infoLength} bytes at {offset}."
            ) from exc
        offset += infoLength

        messages: list[ArchiveMessage] = []
        for messageInfo in info.message_infos:
            body = payload[offset:offset + messageInfo.length]
            if len(body) != messageInfo.length:
                raise IWAError(
                    f"Archive {info.identifier} declares a {messageInfo.length}-byte "
                    f"message but only {len(body)} bytes remain."
                )
            messages.append(
                ArchiveMessage(
                    typeId=messageInfo.type,
                    version=tuple(messageInfo.version),
                    data=body,
                )
            )
            offset += messageInfo.length

        archives.append(
            Archive(identifier=info.identifier, messages=tuple(messages))
        )

    if offset != len(payload):
        raise IWAError(
            f"Archive stream ended at {offset} of {len(payload)} bytes."
        )
    return archives


def readIWAFile(name: str, data: bytes) -> IWAFile:
    """Read one `.iwa` member into archives, keeping its original bytes."""
    return IWAFile(
        name=name,
        archives=readArchives(decompressPayload(data)),
        originalBytes=data,
    )


def writeIWAFile(iwaFile: IWAFile) -> bytes:
    """Serialize an IWA member back to bytes.

    An unmodified file returns the bytes it was read from, which is what makes
    the no-change round trip exact. Rewriting a modified one needs a Snappy
    compressor, which does not exist yet, so this raises rather than silently
    emitting a file that would differ from what Numbers wrote.
    """
    if not iwaFile.originalBytes:
        raise IWAError(
            f"{iwaFile.name} has no original bytes to write back, and encoding a "
            "rewritten IWA member is not implemented yet."
        )
    return iwaFile.originalBytes

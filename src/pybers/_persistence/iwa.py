#!/usr/bin/env python3
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
layer that finds message boundaries. The second is that protobuf re-serialization
is not guaranteed to reproduce the input byte for byte, field ordering and
varint encoding both have latitude, so a reader that parsed eagerly could not
promise the round trip this library is built around.

For the same reason an unmodified file writes back from `originalBytes` rather
than being re-encoded. That makes the no-change round trip exact by construction
rather than by hoping a compressor matches Apple's.

A member that was genuinely edited takes the other path and is rebuilt from its
archives. Those two paths are chosen by `IWAFile.modified`, which only
`messageReplace` sets, so an edit cannot reach `originalBytes` and be written back
as though it had never happened.

UPDATES
2026-09-14  An archive can be created and added to a member, for PYB-63.
2026-08-16  Written. Verified against empty-1/2/3.numbers: every archive stream
            ends exactly on the final byte of its payload.
2026-09-01  Added the write path for #2: archive stream, framing, and the
            modified flag that decides between rewriting and replaying.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"

from dataclasses import dataclass, field, replace

from .._generated import TSPArchiveMessages_pb2 as archiveMessages
from ..errors import PybersError
from .compression import compressRaw, decompressRaw
from .varint import readVarint, writeVarint

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


class IWAError(PybersError, RuntimeError):
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

    `infoBytes` is the archive's own `ArchiveInfo`, kept serialized. Rebuilding one
    from the identifier and the message shapes would discard the rest of what it
    holds, and the rest is not rare: measured across the documents on 2026-09-01,
    40.2% of messages carry `field_infos` and 22.3% carry `object_references`,
    neither of which this library models. Keeping the bytes is what preserves them
    through a rewrite.
    """

    identifier: int
    messages: tuple[ArchiveMessage, ...]
    infoBytes: bytes = b""


@dataclass
class IWAFile:
    """One `.iwa` member, holding both its archives and the bytes it came from.

    `originalBytes` is kept so an untouched file serializes back exactly. Not an
    optimization: Snappy has no canonical encoding, so re-compressing an unchanged
    payload would produce a valid member that differs byte for byte from the one
    Numbers wrote, and the unchanged round trip is the property this library exists
    to keep.

    `modified` is what decides between the two paths, and it is set only by
    `messageReplace`. Writing through that method rather than reaching into
    `archives` is what keeps an edit from being silently dropped at save time.
    """

    name: str
    archives: list[Archive] = field(default_factory=list)
    originalBytes: bytes = b""
    modified: bool = False

    def messageReplace(
        self,
        identifier: int,
        index: int,
        data: bytes,
        references: list[int] | None = None,
    ) -> None:
        """Swap the body of one message of one archive, and mark the member rewritten.

        The only sanctioned way to change an IWA member. `references` replaces the
        message's strong object references, which a body gaining one has to declare.
        `Archive` is frozen, so the replacement is a new archive in the old one's place.
        """
        for position, archive in enumerate(self.archives):
            if archive.identifier != identifier:
                continue
            if not 0 <= index < len(archive.messages):
                raise IWAError(
                    f"Archive {identifier} in {self.name} has "
                    f"{len(archive.messages)} messages, so index {index} is out "
                    "of range."
                )
            messages = list(archive.messages)
            messages[index] = replace(messages[index], data=data)
            infoBytes = archive.infoBytes
            if references is not None:
                info = archiveMessages.ArchiveInfo()
                info.ParseFromString(infoBytes)
                del info.message_infos[index].object_references[:]
                info.message_infos[index].object_references.extend(references)
                infoBytes = info.SerializeToString()
            self.archives[position] = replace(
                archive, messages=tuple(messages), infoBytes=infoBytes
            )
            self.modified = True
            return
        raise IWAError(f"{self.name} holds no archive with identifier {identifier}.")

    def archiveAdd(self, archive: Archive) -> None:
        """Append an archive this member did not hold, and mark the member rewritten.

        Appended rather than placed, because Numbers itself appends: an inserted
        table's archives follow every existing one in `CalculationEngine.iwa`.
        """
        if any(held.identifier == archive.identifier for held in self.archives):
            raise IWAError(
                f"{self.name} already holds archive {archive.identifier}, and two "
                "archives cannot share an identifier."
            )
        self.archives.append(archive)
        self.modified = True


def createArchive(
    info: archiveMessages.ArchiveInfo, bodies: list[bytes]
) -> Archive:
    """Return a new archive from its `ArchiveInfo` and one body per message.

    The info comes from the caller whole, because its field infos and object
    references record which references are weak, and no schema says so.
    """
    if len(info.message_infos) != len(bodies):
        raise IWAError(
            f"Archive {info.identifier} declares {len(info.message_infos)} messages "
            f"and was given {len(bodies)} bodies."
        )
    for declared, body in zip(info.message_infos, bodies, strict=True):
        declared.length = len(body)
    return Archive(
        identifier=info.identifier,
        messages=tuple(
            ArchiveMessage(
                typeId=declared.type, version=tuple(declared.version), data=body
            )
            for declared, body in zip(info.message_infos, bodies, strict=True)
        ),
        infoBytes=info.SerializeToString(),
    )


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
        infoBytes = payload[offset:offset + infoLength]
        info = archiveMessages.ArchiveInfo()
        try:
            info.ParseFromString(infoBytes)
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
            Archive(
                identifier=info.identifier,
                messages=tuple(messages),
                infoBytes=infoBytes,
            )
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


def writeArchiveInfo(archive: Archive) -> bytes:
    """Return an archive's `ArchiveInfo`, re-encoded only if a message body resized.

    The stored bytes are returned untouched in the common case, which is what
    preserves the `field_infos` and `object_references` this library does not
    model. They are re-serialized only when a body actually changed length, and
    then only the `length` fields are altered.
    """
    if not archive.infoBytes:
        raise IWAError(
            f"Archive {archive.identifier} carries no ArchiveInfo, so it cannot be "
            "written. Only an archive read from a file or built by `createArchive` "
            "carries one."
        )
    info = archiveMessages.ArchiveInfo()
    info.ParseFromString(archive.infoBytes)
    if len(info.message_infos) != len(archive.messages):
        raise IWAError(
            f"Archive {archive.identifier} declares {len(info.message_infos)} "
            f"messages but holds {len(archive.messages)}. Adding or removing a "
            "message is not supported."
        )
    lengths = [len(message.data) for message in archive.messages]
    if all(
        declared.length == actual
        # strict is safe rather than merely tidy: the count is checked above.
        for declared, actual in zip(info.message_infos, lengths, strict=True)
    ):
        return archive.infoBytes
    for declared, actual in zip(info.message_infos, lengths, strict=True):
        declared.length = actual
    return info.SerializeToString()


def writeArchives(archives: list[Archive]) -> bytes:
    """Serialize archives back into an uncompressed IWA payload.

    The exact inverse of `readArchives`: a varint-prefixed `ArchiveInfo` followed
    by its message bodies laid end to end, with no padding between archives.
    """
    out = bytearray()
    for archive in archives:
        infoBytes = writeArchiveInfo(archive)
        out += writeVarint(len(infoBytes))
        out += infoBytes
        for message in archive.messages:
            out += message.data
    return bytes(out)


def compressPayload(payload: bytes) -> bytes:
    """Frame a payload into Snappy blocks the way Numbers does.

    Chunked at 64 KiB of uncompressed input, which is what Apple emits and what
    every non-final frame in the documents measures. An empty payload still produces
    one frame, because a member with no archives is a member, not an absent file.
    """
    out = bytearray()
    for start in range(0, max(len(payload), 1), uncompressedChunkLength):
        block = compressRaw(payload[start:start + uncompressedChunkLength])
        if len(block) >= 1 << 24:
            raise IWAError(
                f"A frame compressed to {len(block)} bytes, which will not fit the "
                "three-byte length in its header."
            )
        out.append(compressedFrameFlag)
        out += len(block).to_bytes(3, "little")
        out += block
    return bytes(out)


def writeIWAFile(iwaFile: IWAFile) -> bytes:
    """Serialize an IWA member back to bytes.

    An unmodified member replays the bytes it was read from, which is what makes
    the no-change round trip exact. A modified one is rebuilt from its archives
    and re-compressed, which produces a valid member that is not the one Numbers
    would have written, because Snappy has no canonical encoding.
    """
    if not iwaFile.modified:
        if not iwaFile.originalBytes:
            raise IWAError(
                f"{iwaFile.name} has neither original bytes nor any recorded edit, "
                "so there is nothing to write."
            )
        return iwaFile.originalBytes
    return compressPayload(writeArchives(iwaFile.archives))

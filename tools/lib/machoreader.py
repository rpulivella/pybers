#!/usr/bin/env python3
"""\
Read a Mach-O binary as data: sections, symbols, Objective-C metadata, and
AArch64 immediates.

Written for the function-table extractor, which needs four things out of the
Numbers frameworks and finds none of them in a published table. Nothing here
loads, links or executes anything; a binary is opened read-only and parsed.

**Pointers stored in data are encoded, not absolute.** Modern Mach-O uses dyld
chained fixups, so an eight-byte slot in `__DATA` holds the target in its low 36
bits alongside the chain's own bookkeeping. A raw search for an address
therefore finds nothing, which is the trap this module exists to hide: read
every data pointer through `pointerAt`.

**Method lists come in two shapes.** The older one stores three absolute
pointers per entry; the current one stores three 32-bit offsets relative to the
fields holding them, flagged by the high bit of the list's entry size. Reading a
relative list as absolute yields offsets in the gigabytes and an exception.

UPDATES
2026-09-04  Written for #44.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"
__usage__ = "imported, never run: tools/lib holds no commands"

import bisect
import struct
from dataclasses import dataclass, field
from pathlib import Path

machO64Magic: int = 0xFEEDFACF
fatMagic: int = 0xCAFEBABE
fatMagic64: int = 0xCAFEBABF
cpuTypeArm64: int = 0x0100000C

segment64Command: int = 0x19
symbolTableCommand: int = 0x02
functionStartsCommand: int = 0x26

nlistSize: int = 16
sectionRecordSize: int = 80

# A chained-fixup rebase carries its target in the low 36 bits and the chain's
# own bookkeeping above them, so every pointer read out of data is masked.
chainedTargetMask: int = (1 << 36) - 1

# The high bit of a method list's entry size marks the relative form.
relativeMethodListFlag: int = 0x80000000
methodListStrideMask: int = 0xFFFC


class MachOError(RuntimeError):
    """A binary that could not be read, or carries nothing recognizable."""


@dataclass(frozen=True)
class Section:
    """One section's address, size and file offset."""

    address: int
    size: int
    offset: int


@dataclass(frozen=True)
class ObjectiveCClass:
    """One Objective-C class, and the two method lists hanging off it."""

    name: str
    address: int
    instanceMethods: dict[str, int] = field(default_factory=dict)
    classMethods: dict[str, int] = field(default_factory=dict)


def arm64Slice(binary: Path) -> bytes:
    """Return the arm64 slice of a Mach-O file, which may be universal or thin.

    A universal header is big-endian, which is the one place in this module
    where byte order is not native.
    """
    data = binary.read_bytes()
    if len(data) < 8:
        raise MachOError(f"{binary} is too short to be a Mach-O file.")
    if struct.unpack_from("<I", data, 0)[0] == machO64Magic:
        return data

    magic = struct.unpack_from(">I", data, 0)[0]
    if magic not in (fatMagic, fatMagic64):
        raise MachOError(f"{binary} is not a Mach-O file (magic {magic:#x}).")

    wide = magic == fatMagic64
    entrySize = 32 if wide else 20
    for index in range(struct.unpack_from(">I", data, 4)[0]):
        base = 8 + index * entrySize
        if struct.unpack_from(">i", data, base)[0] != cpuTypeArm64:
            continue
        offset, size = struct.unpack_from(">2Q" if wide else ">2I", data, base + 8)
        return data[offset:offset + size]

    raise MachOError(f"{binary} carries no arm64 slice.")


class Image:
    """One architecture slice, read lazily into the tables a caller asks for."""

    def __init__(self, binary: Path) -> None:
        """Parse the load commands, the symbol table and the function starts."""
        self.data = arm64Slice(binary)
        if struct.unpack_from("<I", self.data, 0)[0] != machO64Magic:
            raise MachOError(f"{binary} is not a 64-bit Mach-O image.")

        self.segments: list[tuple[int, int, int]] = []
        self.sections: dict[str, Section] = {}
        self.symbols: dict[int, str] = {}
        self.functionStarts: list[int] = []

        offset = 32
        symbolTable: tuple[int, int, int, int] | None = None
        starts: tuple[int, int] | None = None
        for _ in range(struct.unpack_from("<I", self.data, 16)[0]):
            command, size = struct.unpack_from("<2I", self.data, offset)
            if command == segment64Command:
                self._readSegment(offset)
            elif command == symbolTableCommand:
                symbolTable = struct.unpack_from("<4I", self.data, offset + 8)
            elif command == functionStartsCommand:
                starts = struct.unpack_from("<2I", self.data, offset + 8)
            offset += size

        if symbolTable is not None:
            self._readSymbols(*symbolTable)
        if starts is not None:
            self._readFunctionStarts(*starts)
        if "__TEXT,__text" not in self.sections:
            raise MachOError(f"{binary} carries no __TEXT,__text section.")

    def _readSegment(self, offset: int) -> None:
        """Record one segment and each of its sections."""
        name = self.data[offset + 8:offset + 24].rstrip(b"\0").decode()
        address, size, fileOffset, fileSize = struct.unpack_from(
            "<4Q", self.data, offset + 24
        )
        if fileSize:
            self.segments.append((address, size, fileOffset))
        cursor = offset + 72
        for _ in range(struct.unpack_from("<I", self.data, offset + 64)[0]):
            sectionName = self.data[cursor:cursor + 16].rstrip(b"\0").decode()
            sectionAddress, sectionSize = struct.unpack_from(
                "<2Q", self.data, cursor + 32
            )
            self.sections[f"{name},{sectionName}"] = Section(
                sectionAddress,
                sectionSize,
                struct.unpack_from("<I", self.data, cursor + 48)[0],
            )
            cursor += sectionRecordSize

    def _readSymbols(
        self, symbolOffset: int, count: int, stringOffset: int, stringSize: int
    ) -> None:
        """Record every symbol by address, which is how call targets are named."""
        table = self.data[stringOffset:stringOffset + stringSize]
        for index in range(count):
            nameIndex, _type, _section, _description, value = struct.unpack_from(
                "<IBBHQ", self.data, symbolOffset + index * nlistSize
            )
            end = table.find(b"\0", nameIndex)
            self.symbols[value] = table[nameIndex:end].decode("ascii", "replace")

    def _readFunctionStarts(self, offset: int, size: int) -> None:
        """Decode the ULEB128 deltas that give every function's exact extent.

        Needed because most of the interesting functions here carry no symbol,
        so the next symbol is not the end of the current function.
        """
        address, cursor, end = 0, offset, offset + size
        while cursor < end:
            value, shift = 0, 0
            while True:
                byte = self.data[cursor]
                cursor += 1
                value |= (byte & 0x7F) << shift
                shift += 7
                if not byte & 0x80:
                    break
            if value == 0:
                break
            address += value
            self.functionStarts.append(address)

    def fileOffset(self, address: int) -> int | None:
        """Return the file offset an address maps to, or None when unmapped."""
        for start, size, offset in self.segments:
            if start <= address < start + size:
                return offset + (address - start)
        return None

    def pointerAt(self, address: int) -> int:
        """Return the pointer stored at an address, chained fixups decoded."""
        offset = self.fileOffset(address)
        if offset is None or offset + 8 > len(self.data):
            return 0
        return struct.unpack_from("<Q", self.data, offset)[0] & chainedTargetMask

    def stringAt(self, address: int) -> str | None:
        """Return the C string at an address, or None when it is not one."""
        offset = self.fileOffset(address)
        if offset is None:
            return None
        end = self.data.find(b"\0", offset)
        try:
            return self.data[offset:end].decode("ascii")
        except UnicodeDecodeError:
            return None

    def constantStringAt(self, address: int) -> str | None:
        """Return the text of a compiled `@"..."` literal, or None.

        The four fields are a class pointer, flags, the bytes, and the length.
        The length is checked against the text so that a wrong guess at an
        address fails here rather than returning a plausible neighbor.
        """
        offset = self.fileOffset(address)
        if offset is None or offset + 32 > len(self.data):
            return None
        _isa, _flags, pointer, length = struct.unpack_from("<4Q", self.data, offset)
        text = self.stringAt(pointer & chainedTargetMask)
        return text if text is not None and len(text) == length else None

    def functionBounds(self, address: int) -> tuple[int, int] | None:
        """Return the start and end of the function containing an address."""
        index = bisect.bisect_right(self.functionStarts, address) - 1
        if index < 0:
            return None
        start = self.functionStarts[index]
        text = self.sections["__TEXT,__text"]
        end = (
            self.functionStarts[index + 1]
            if index + 1 < len(self.functionStarts)
            else text.address + text.size
        )
        return start, end

    def objectiveCClasses(self) -> dict[str, ObjectiveCClass]:
        """Return every Objective-C class in the image, by name.

        Both method lists are decoded, since a class method such as
        `+functionIndex` lives on the metaclass rather than on the class.
        """
        listing = self.sections.get("__DATA_CONST,__objc_classlist")
        if listing is None:
            raise MachOError("No __objc_classlist section; this is not ObjC code.")
        classes: dict[str, ObjectiveCClass] = {}
        for slot in range(0, listing.size, 8):
            raw = struct.unpack_from("<Q", self.data, listing.offset + slot)[0]
            if raw >> 63:
                continue
            address = raw & chainedTargetMask
            name = self._className(address)
            if name is None:
                continue
            classes[name] = ObjectiveCClass(
                name=name,
                address=address,
                instanceMethods=self._methods(address),
                classMethods=self._methods(self.pointerAt(address)),
            )
        return classes

    def _readOnlyData(self, classAddress: int) -> int | None:
        """Return the file offset of one class's read-only data block."""
        offset = self.fileOffset(classAddress + 32)
        if offset is None:
            return None
        return self.fileOffset(self.pointerAt(classAddress + 32) & ~0x7)

    def _className(self, classAddress: int) -> str | None:
        """Return one class's name, or None when the address is not a class."""
        base = self._readOnlyData(classAddress)
        if base is None or base + 32 > len(self.data):
            return None
        return self.stringAt(
            struct.unpack_from("<Q", self.data, base + 24)[0] & chainedTargetMask
        )

    def _methods(self, classAddress: int) -> dict[str, int]:
        """Return one method list as selector to implementation address."""
        base = self._readOnlyData(classAddress)
        if base is None or base + 40 > len(self.data):
            return {}
        listAddress = (
            struct.unpack_from("<Q", self.data, base + 32)[0] & chainedTargetMask
        )
        listOffset = self.fileOffset(listAddress)
        if not listAddress or listOffset is None:
            return {}
        entrySize, count = struct.unpack_from("<2I", self.data, listOffset)
        stride = entrySize & methodListStrideMask
        if not stride or count > 0xFFFF:
            return {}

        relative = bool(entrySize & relativeMethodListFlag)
        methods: dict[str, int] = {}
        for index in range(count):
            entryAddress = listAddress + 8 + index * stride
            entryOffset = listOffset + 8 + index * stride
            if entryOffset + stride > len(self.data):
                break
            if relative:
                nameDelta, _typesDelta, implementationDelta = struct.unpack_from(
                    "<3i", self.data, entryOffset
                )
                # The name field points at a pointer to the selector, not at
                # the selector itself, which is the one asymmetry in this form.
                selector = self.stringAt(self.pointerAt(entryAddress + nameDelta))
                implementation = entryAddress + 8 + implementationDelta
            else:
                selectorAddress, _types, implementation = (
                    value & chainedTargetMask
                    for value in struct.unpack_from("<3Q", self.data, entryOffset)
                )
                selector = self.stringAt(selectorAddress)
            if selector:
                methods[selector] = implementation
        return methods

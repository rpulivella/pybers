#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
The archive layer: reading and writing the `.numbers` container.

Split by feature area, matching `pybers.model`: `compression` decodes raw Snappy
blocks, `iwa` turns a compressed member into archives of raw protobuf messages,
and `container` handles the zip that holds them. Everything re-exports through
here so that `pybers.archive.readPackage` stays stable regardless of which module
a name lives in.

`compression`, `iwa` and `container` stop at message boundaries on purpose. They
find every archive and every message body and parse none of them, because mapping
a type identifier to a generated protobuf class needs a source of truth none of
them owns. `types` is that source of truth, and parsing an archive is the one
thing it does, which keeps the boundary a module apart rather than absent.

UPDATES
2026-08-31  Added `types`, and corrected this docstring, which claimed the whole
            layer parses nothing. That was true until `types` arrived and would
            have read as a rule the package was breaking.
2026-08-16  Written alongside the container layer.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/16"

from .cells import (
    CellDecodeError,
    CellRecord,
    decodeCellValue,
    decodeDecimal128,
    decodeRecord,
    decodeRow,
)
from .compression import SnappyError, decompressRaw, readVarint
from .container import (
    ContainerError,
    MemberInfo,
    NumbersPackage,
    StoredMember,
    isDocumentMember,
    readPackage,
    toZipInfo,
    writePackage,
)
from .iwa import (
    Archive,
    ArchiveMessage,
    IWAError,
    IWAFile,
    decompressPayload,
    readArchives,
    readIWAFile,
    splitFrames,
    writeIWAFile,
)

__all__ = [
    "Archive",
    "ArchiveMessage",
    "CellDecodeError",
    "CellRecord",
    "ContainerError",
    "IWAError",
    "IWAFile",
    "MemberInfo",
    "NumbersPackage",
    "SnappyError",
    "StoredMember",
    "decodeCellValue",
    "decodeDecimal128",
    "decodeRecord",
    "decodeRow",
    "decompressPayload",
    "decompressRaw",
    "isDocumentMember",
    "readArchives",
    "readIWAFile",
    "readPackage",
    "readVarint",
    "splitFrames",
    "toZipInfo",
    "writeIWAFile",
    "writePackage",
]

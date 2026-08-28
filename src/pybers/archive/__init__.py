#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
The archive layer: reading and writing the `.numbers` container.

Split by feature area, matching `pybers.model`: `compression` decodes raw Snappy
blocks, `iwa` turns a compressed member into archives of raw protobuf messages,
and `container` handles the zip that holds them. Everything re-exports through
here so that `pybers.archive.readPackage` stays stable regardless of which module
a name lives in.

This layer stops at message boundaries on purpose. It finds every archive and
every message body but parses none of them, because mapping a type identifier to
a generated protobuf class is a separate concern with its own source of truth.

UPDATES
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

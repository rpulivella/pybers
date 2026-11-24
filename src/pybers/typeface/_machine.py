#!/usr/bin/env python3
"""\
The font files the machine running pybers offers, found as its system finds them.

A Mac's are the ones CoreText offers, which is what Numbers offers: a folder scan on
24 November 2026 missed 284 fonts a font manager had activated and included 198 that
Font Book had turned off, and it never reaches Adobe Fonts or the fonts macOS
downloads on demand. CoreText is reached through `ctypes`, so no dependency is added.
Elsewhere the files are those in the system's own font folders.

Private. Part of the font feature's read half.

UPDATES
2026-11-24  Moved to the typeface feature, for PYB-318.
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

import ctypes
import os
import platform
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pybers.errors import PybersError, composeFault
from pybers.typeface.fonts import fontSuffixes

coreFoundationPath: str = (
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)
coreTextPath: str = "/System/Library/Frameworks/CoreText.framework/CoreText"
# A file path longer than this is not one macOS creates.
pathBufferSize: int = 4096


class FontMachineError(PybersError, RuntimeError):
    """CoreText answered in a way pybers did not expect."""


def findMacFontFiles() -> tuple[Path, ...]:
    """Return every font file CoreText offers, in its order, each once."""
    pointer = ctypes.c_void_p
    coreFoundation = ctypes.CDLL(coreFoundationPath)
    coreText = ctypes.CDLL(coreTextPath)
    # Each function's result and argument types, which ctypes cannot read itself.
    signatures: tuple[tuple[Any, Any, list[Any]], ...] = (
        (coreText.CTFontCollectionCreateFromAvailableFonts, pointer, [pointer]),
        (coreText.CTFontCollectionCreateMatchingFontDescriptors, pointer, [pointer]),
        (coreText.CTFontDescriptorCopyAttribute, pointer, [pointer, pointer]),
        (coreFoundation.CFArrayGetCount, ctypes.c_long, [pointer]),
        (coreFoundation.CFArrayGetValueAtIndex, pointer, [pointer, ctypes.c_long]),
        (coreFoundation.CFURLGetFileSystemRepresentation, ctypes.c_bool,
         [pointer, ctypes.c_bool, ctypes.c_char_p, ctypes.c_long]),
        (coreFoundation.CFRelease, None, [pointer]),
    )
    for function, result, arguments in signatures:
        function.restype, function.argtypes = result, arguments
    urlKey = pointer.in_dll(coreText, "kCTFontURLAttribute")
    collection = coreText.CTFontCollectionCreateFromAvailableFonts(None)
    if not collection:
        raise FontMachineError(composeFault(
            "CoreText", "returned no collection of the available fonts"
        ))
    found: dict[Path, None] = {}
    buffer = ctypes.create_string_buffer(pathBufferSize)
    descriptors = coreText.CTFontCollectionCreateMatchingFontDescriptors(collection)
    try:
        count = coreFoundation.CFArrayGetCount(descriptors) if descriptors else 0
        for index in range(count):
            descriptor = coreFoundation.CFArrayGetValueAtIndex(descriptors, index)
            url = coreText.CTFontDescriptorCopyAttribute(descriptor, urlKey)
            if not url:
                continue
            if coreFoundation.CFURLGetFileSystemRepresentation(
                url, True, buffer, pathBufferSize
            ):
                found[Path(os.fsdecode(buffer.value))] = None
            coreFoundation.CFRelease(url)
    finally:
        if descriptors:
            coreFoundation.CFRelease(descriptors)
        coreFoundation.CFRelease(collection)
    return tuple(found)


def listSystemFontFolders(system: str) -> tuple[Path, ...]:
    """Return the folders Linux or Windows installs fonts in, the user's last."""
    home = Path.home()
    if system == "Windows":
        windows = Path(os.environ.get("WINDIR", "C:/Windows"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return windows / "Fonts", local / "Microsoft" / "Windows" / "Fonts"
    dataHome = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return (
        Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
        dataHome / "fonts", home / ".fonts",
    )


def findFolderFontFiles(folders: Iterable[Path]) -> tuple[Path, ...]:
    """Return every font file beneath the folders, each once, sorted within a folder."""
    found: dict[Path, None] = {}
    for folder in folders:
        if folder.is_dir():
            for path in sorted(folder.rglob("*")):
                if path.suffix.lower() in fontSuffixes and path.is_file():
                    found[path] = None
    return tuple(found)


def findMachineFontFiles() -> tuple[Path, ...]:
    """Return the font files the machine running pybers offers."""
    system = platform.system()
    if system == "Darwin":
        return findMacFontFiles()
    return findFolderFontFiles(listSystemFontFolders(system))


__all__ = [
    "FontMachineError", "findFolderFontFiles", "findMacFontFiles",
    "findMachineFontFiles", "listSystemFontFolders",
]

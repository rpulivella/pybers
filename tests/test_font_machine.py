#!/usr/bin/env python3
"""\
The font files the machine offers: CoreText's on a Mac, the font folders elsewhere.

UPDATES
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
import platform
from pathlib import Path

import pytest
from fontbuilders import buildFont, saveFont

from pybers.font._files import readFileFaces
from pybers.font._machine import (
    coreFoundationPath,
    coreTextPath,
    findFolderFontFiles,
    findMacFontFiles,
    listSystemFontFolders,
)
from pybers.font.faces import FontSource

onMac = platform.system() == "Darwin"


def listCoreTextNames() -> set[str]:
    """Return every PostScript name CoreText offers, the oracle a Mac's fonts meet."""
    pointer = ctypes.c_void_p
    coreFoundation = ctypes.CDLL(coreFoundationPath)
    coreText = ctypes.CDLL(coreTextPath)
    coreText.CTFontManagerCopyAvailablePostScriptNames.restype = pointer
    coreFoundation.CFArrayGetCount.restype = ctypes.c_long
    coreFoundation.CFArrayGetCount.argtypes = [pointer]
    coreFoundation.CFArrayGetValueAtIndex.restype = pointer
    coreFoundation.CFArrayGetValueAtIndex.argtypes = [pointer, ctypes.c_long]
    coreFoundation.CFStringGetCString.restype = ctypes.c_bool
    coreFoundation.CFStringGetCString.argtypes = [
        pointer, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32,
    ]
    names = coreText.CTFontManagerCopyAvailablePostScriptNames()
    buffer = ctypes.create_string_buffer(512)
    found: set[str] = set()
    for index in range(coreFoundation.CFArrayGetCount(names)):
        coreFoundation.CFStringGetCString(
            coreFoundation.CFArrayGetValueAtIndex(names, index), buffer, 512,
            0x08000100,
        )
        found.add(buffer.value.decode())
    return found


@pytest.mark.skipif(not onMac, reason="CoreText exists only on a Mac")
def testEveryFaceCoreTextOffersIsReadFromItsFile() -> None:
    read = {
        face.postScriptName for path in findMacFontFiles()
        for face in readFileFaces(path, FontSource.MACHINE)
    }
    offered = {name for name in listCoreTextNames() if not name.startswith(".")}
    assert sorted(offered - read) == []


@pytest.mark.skipif(not onMac, reason="CoreText exists only on a Mac")
def testMacFilesAreEachListedOnceAndExist() -> None:
    files = findMacFontFiles()
    assert len(files) == len(set(files))
    assert all(path.is_file() for path in files)


def testFolderFilesAreEveryFontBeneathEachFolderOnce(tmp_path: Path) -> None:
    first, second = tmp_path / "system", tmp_path / "user"
    (first / "nested").mkdir(parents=True)
    second.mkdir()
    font = buildFont("Brand Sans", "Regular", "BrandSans-Regular")
    saveFont(font, first / "nested" / "brand.ttf")
    saveFont(font, second / "brand.OTF")
    (second / "notes.txt").write_text("not a font")
    found = findFolderFontFiles([first, second, first, tmp_path / "absent"])
    assert found == (first / "nested" / "brand.ttf", second / "brand.OTF")


def testLinuxFoldersFollowXdgDataHome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    folders = listSystemFontFolders("Linux")
    assert Path("/usr/share/fonts") in folders and tmp_path / "fonts" in folders


def testWindowsFoldersFollowItsEnvironment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WINDIR", str(tmp_path / "Windows"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert listSystemFontFolders("Windows") == (
        tmp_path / "Windows" / "Fonts",
        tmp_path / "Local" / "Microsoft" / "Windows" / "Fonts",
    )

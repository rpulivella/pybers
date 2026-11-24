#!/usr/bin/env python3
"""\
The committed font catalog: every face macOS installs, current with the Mac running it.

On a Mac the catalog is read again from the fonts macOS installs, so a macOS release
that adds or changes a face fails here until `tools/local/fonts_extract.py` is run.

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

import platform

import pytest

from pybers._generated.fonts import fonts
from pybers.font.faces import FontSlant
from tools.local.lib.fonttable import readSystemRows

onMac = bool(platform.mac_ver()[0])


@pytest.mark.skipif(not onMac, reason="the catalog is read from macOS")
def testCatalogIsCurrentWithThisMac() -> None:
    assert readSystemRows() == list(fonts), (
        "The font catalog differs from the fonts this Mac installs. Run "
        "`.venv/bin/python3 -m tools.local.fonts_extract --write`."
    )


def testCatalogNamesEachFaceOnce() -> None:
    names = [row[0] for row in fonts]
    assert len(names) == len(set(names))


def testCatalogHoldsNoHiddenFace() -> None:
    assert not [
        row for row in fonts if row[0].startswith(".") or row[1].startswith(".")
    ]


def testCatalogWeightsAndSlantsAreOnTheCssScale() -> None:
    slants = {each.value for each in FontSlant}
    assert all(100 <= row[3] <= 1000 and row[4] in slants for row in fonts)

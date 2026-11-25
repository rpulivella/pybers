#!/usr/bin/env python3
"""\
The committed font catalog: every font macOS installs, each named once and on scale.

`/release-tag` reads the catalog again on the Mac cutting a release, so it matches the
macOS of the release that ships it rather than of whichever Mac runs the suite.

UPDATES
2026-11-24  Its currency checked at a release rather than on every run, for PYB-319.
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

from pybers._generated.typefaces import fonts
from pybers.typeface.fonts import TypefaceSlant


def testCatalogNamesEachFaceOnce() -> None:
    names = [row[0] for row in fonts]
    assert len(names) == len(set(names))


def testCatalogHoldsNoHiddenFace() -> None:
    assert not [
        row for row in fonts if row[0].startswith(".") or row[1].startswith(".")
    ]


def testCatalogWeightsAndSlantsAreOnTheCssScale() -> None:
    slants = {each.value for each in TypefaceSlant}
    assert all(100 <= row[3] <= 1000 and row[4] in slants for row in fonts)

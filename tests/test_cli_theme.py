#!/usr/bin/env python3
"""\
`themeStyles` is the one theme: the design's color table and the logo's caret agree
with it.

UPDATES
2026-11-23  Written for PYB-304.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/23"

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from pybers.cli._console import themeStyles

repositoryRoot: Path = Path(__file__).resolve().parent.parent
designPath: Path = repositoryRoot / "docs" / "cli-design.md"
logoPath: Path = repositoryRoot / "docs" / "logo" / "pybers-logo-dark.svg"
tableRow: re.Pattern[str] = re.compile(r"^\| `([^`]+)` \| `([^`]+)` \|")


def readDesignStyles() -> dict[str, str]:
    """Return each style and its Rich style, as the design's color table lists them."""
    lines = designPath.read_text().splitlines()
    start = lines.index("| Style | Rich style | Meaning | Example |") + 2
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    return {
        found.group(1): found.group(2)
        for found in map(tableRow.match, rows) if found is not None
    }


def readLogoCaretColor() -> str:
    """Return the caret's fill in the dark logo, the one a terminal draws."""
    caret = next(
        element for element in ElementTree.parse(logoPath).iter()
        if element.get("id") == "caret-bar"
    )
    return caret.get("fill", "").lower()


def testTheDesignsColorTableIsTheTheme() -> None:
    assert readDesignStyles() == dict(themeStyles)


def testTheLogosCaretIsTheDarkLogosOrange() -> None:
    assert themeStyles["logo.caret"].split()[-1] == readLogoCaretColor()

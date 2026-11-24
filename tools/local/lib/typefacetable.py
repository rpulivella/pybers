#!/usr/bin/env python3
"""\
The typeface catalog's rows: read from the fonts macOS installs, written as a module,
and read back from the one committed.

The fonts are read by `pybers.typeface._files`, the reader pybers uses everywhere, so
the catalog and a machine's own fonts never disagree about the same file.

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

import importlib.util
from pathlib import Path

from pybers.typeface._files import readFileFonts
from pybers.typeface.fonts import TypefaceSource, fontSuffixes

# What macOS installs, which is every Mac's whatever Font Book has turned off.
systemFonts: Path = Path("/System/Library/Fonts")

# PostScript name, typeface, font, weight, slant and file under `systemFonts`.
type FontRow = tuple[str, str, str, int, str, str]


def readSystemRows() -> list[FontRow]:
    """Return a row for every font macOS installs, in the order the catalog keeps."""
    rows = [
        (
            font.postScriptName, font.typeface, font.name, font.weight,
            font.slant.value, path.relative_to(systemFonts).as_posix(),
        )
        for path in sorted(systemFonts.rglob("*"))
        if path.suffix.lower() in fontSuffixes
        for font in readFileFonts(path, TypefaceSource.CATALOG)
    ]
    return sorted(rows, key=lambda row: (row[1].casefold(), row[3], row[4], row[0]))


def formatModule(rows: list[FontRow], macOS: str) -> str:
    """Return the module holding the catalog."""
    lines = [
        "#!/usr/bin/env python3",
        '"""\\',
        "Every font macOS installs, by typeface. Machine output, do not edit.",
        "",
        f"Written by tools/local/typefaces_extract.py from macOS {macOS}.",
        "A correction made here is destroyed by the next extraction; correct the",
        "extractor instead.",
        "",
        "Each row is a font's PostScript name, typeface, name, weight, slant, and",
        "its file under /System/Library/Fonts.",
        "",
        f"{len(rows)} fonts.",
        '"""',
        "",
        "fonts: tuple[tuple[str, str, str, int, str, str], ...] = (",
        *(f"    {row!r}," for row in rows),
        ")",
    ]
    return "\n".join(lines) + "\n"


def readCommitted(path: Path) -> list[FontRow] | None:
    """Return the committed catalog's rows, or None when there is none yet."""
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("committedTypefaces", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.fonts)

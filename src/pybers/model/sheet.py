#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A sheet holds tables (row/column grids) and graphical objects (things that float on
the sheet at an absolute position, text boxes, images, shapes) side by side, since
Numbers places both on the same sheet independently. A document is a list of sheets.

`Document` is the only handle a caller ever holds. It is what `pybers.open` returns,
what every edit reaches through, and what `save` writes back. See CLAUDE.md, "Document
is the single handle".

UPDATES
2026-08-12  Initial scaffold.
2026-09-01  Document carries the package it was read from, and gained save, for #2.
"""

from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pybers.model.shapes import GraphicalObject
from pybers.model.table import Table

if TYPE_CHECKING:
    # Guarded so that importing the model never drags in the persistence layer.
    from pybers.numbersfile import NumbersPackage


@dataclass(slots=True)
class Sheet:
    """One sheet (tab) in a document: its tables and its floating graphical objects."""

    name: str
    tables: list[Table] = field(default_factory=list)
    graphicalObjects: list[GraphicalObject] = field(default_factory=list)


@dataclass(slots=True)
class Document:
    """The root of the pybers object model, matching Apple's own TN.DocumentArchive.

    Named for the format rather than for the spreadsheet convention: Numbers has no
    workbook, and calling it one would invent a concept the format does not carry.

    The two private fields hold the archives this document was read from and its
    origin on disk. Both are excluded from equality and from `repr`, so a Document
    still reads as an ordinary dataclass to a caller. `pybers.writer` explains why a
    save needs them.
    """

    sheets: list[Sheet] = field(default_factory=list)
    _package: NumbersPackage | None = field(default=None, repr=False, compare=False)
    _sourcePath: Path | None = field(default=None, repr=False, compare=False)

    def save(self, path: Path | str | None = None) -> None:
        """Write this document back to a `.numbers` package, in place by default.

        Nothing is closed and nothing is invalidated. A Document holds no file handle,
        so saving is repeatable and the object stays usable afterward, which is why
        there is no `close` and no context manager to pair with `pybers.open`.
        """
        # Imported here rather than at module scope, because the writer reaches into
        # `pybers.numbersfile` and the model layer must stay importable without it.
        from pybers.writer import writeDocument

        writeDocument(self, path)

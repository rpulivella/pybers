#!/usr/bin/env python3
"""\
The document: what `pybers.open` returns, and the walk that reads and writes one.

One feature, whole. `sheets` holds `Document` and `Sheet`, and `_read` and
`_write` are the archive halves, private because a caller opens a document rather
than walking a package.

**`Document` is the single handle.** Every edit is reached through it and `save`
writes it back, which is why it carries the archives it was read from as private
fields, excluded from equality and `repr`.

**Saving mutates the archives that were read rather than building new ones.** A
document holds far more than this model represents, and every one of those parts
survives only because nothing touched it. Constructing a fresh package from the
model would drop all of it, and the loss would show up as a document Numbers opens
with its charts, conditional formats and print settings quietly gone, rather than
as an error.

UPDATES
2026-09-08  Made a package of its own for #58, gathering `model.sheet`, `reader`
            and `writer`, which is what was left once the features took theirs.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from pybers.document._read import open
from pybers.document.references import ReferenceLocation
from pybers.document.sheets import Document, SelectionError, Sheet

__all__ = ["Document", "ReferenceLocation", "SelectionError", "Sheet", "open"]

#!/usr/bin/env python3
"""\
The calculation engine: what it knows that a table does not, and what it is told.

Writing back, there are three registers and none of them is optional. Each one is
silent when it is wrong, which is why they live together rather than beside
whichever feature trips over one first. One module per concern: `owners` finds
which owner is which table, `registration` and `ranges` tell the engine what each
formula reads, `remapping` moves what a structural edit moves, and
`recalculation` names the cells that changed.

Private, and named so. Nothing here belongs to the surface `import pybers` offers,
and nothing here knows a model type.

UPDATES
2026-09-22  A package of one module per concern, for PYB-113.
2026-09-22  Every archive it writes is written through the save's index, and the
            table owner kind lives here, for PYB-109.
2026-09-21  The engine's cell-keyed records follow a structural edit, for PYB-17.
2026-09-16  A formula declares the cells, rectangles and whole lines it reads, in
            three registers kept twice each, for PYB-86.
2026-09-15  An owner with no dependency tile gains its first, for PYB-86.
2026-09-08  The two halves joined for #58, and the merge formula left for the
            feature that owns it, which took the last model type out.
2026-09-08  Split out of the reader and the writer for #45, unchanged.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from .dependencies import (
    CellEdge,
    FormulaDependencies,
    RangeEdge,
    SpanEdge,
)
from .owners import (
    TableOwner,
    findCalculationEngine,
    findOwnerEntry,
    readTableIdentities,
    readTableOwnerEntries,
    readTableOwnerIds,
)
from .recalculation import (
    requestRecalculation,
)
from .registration import (
    listRegisteredCells,
    registerFormulaCells,
)
from .remapping import (
    LineMapping,
    moveOwnerCoordinates,
    remapOwnerCoordinates,
)

__all__ = [
    "CellEdge",
    "FormulaDependencies",
    "LineMapping",
    "RangeEdge",
    "SpanEdge",
    "TableOwner",
    "findCalculationEngine",
    "findOwnerEntry",
    "listRegisteredCells",
    "readTableIdentities",
    "readTableOwnerEntries",
    "readTableOwnerIds",
    "registerFormulaCells",
    "moveOwnerCoordinates",
    "remapOwnerCoordinates",
    "requestRecalculation",
]

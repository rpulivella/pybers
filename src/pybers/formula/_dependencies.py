#!/usr/bin/env python3
"""\
What a formula reads, translated into the calculation engine's terms.

Private. Part of the formula feature's archive half, reached by the table save
that registers each formula with the engine.

UPDATES
2026-09-23  A range is clamped to the table it reads, for PYB-18.
2026-09-22  Moved out of the document writer for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from collections.abc import Mapping

from .._engine import CellEdge, FormulaDependencies, RangeEdge, SpanEdge
from ..addressing.reference import CellReference
from ..errors import WriteError
from .nodes import Formula
from .precedents import resolveFormulaPrecedents


def resolveFormulaDependencies(
    formula: Formula,
    host: CellReference,
    hostOwner: int,
    ownerIds: Mapping[str, int],
    tableName: str,
    extents: Mapping[str | None, tuple[int, int]],
) -> FormulaDependencies:
    """Return what one formula reads, in the engine's own terms.

    The formula says which table by identity and where by offset; the engine wants
    an internal owner id and an absolute coordinate, so this is where the two meet.
    `extents` holds each table's row and column count, the host's under None.

    **A range reaching past its table is registered up to the table's edge**,
    measured 2026-09-23 in `60b-move-cut-pasted`, where `SUM(E7:E18)` in a table of
    twelve rows was registered as reading rows 7 to 12.
    """

    def owner(identity: str | None) -> int:
        if identity is None:
            return hostOwner
        found = ownerIds.get(identity)
        if found is None:
            raise WriteError(
                f"A formula in {tableName!r} reads table {identity}, which this "
                "document's calculation engine does not register, so what the "
                "formula depends on cannot be recorded."
            )
        return found

    def size(identity: str | None) -> tuple[int, int]:
        owner(identity)
        found = extents.get(identity)
        if found is None:
            raise WriteError(
                f"A formula in {tableName!r} reads table {identity}, whose size this "
                "save does not know, so the range it reads cannot be bounded."
            )
        return found

    reads = resolveFormulaPrecedents(formula, host)
    return FormulaDependencies(
        cells=tuple(
            CellEdge(
                row=precedent.row,
                column=precedent.column,
                owner=None if precedent.tableId is None else owner(precedent.tableId),
            )
            for precedent in reads.cells
        ),
        ranges=tuple(
            RangeEdge(
                top=extent.top,
                left=extent.left,
                bottom=min(extent.bottom, size(extent.tableId)[0] - 1),
                right=min(extent.right, size(extent.tableId)[1] - 1),
                owner=owner(extent.tableId),
            )
            for extent in reads.ranges
        ),
        spans=tuple(
            SpanEdge(
                begin=span.begin,
                end=span.end,
                columns=span.columns,
                owner=owner(span.tableId),
            )
            for span in reads.spans
        ),
    )


__all__ = [
    "resolveFormulaDependencies",
]

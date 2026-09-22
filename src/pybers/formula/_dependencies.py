#!/usr/bin/env python3
"""\
What a formula reads, translated into the calculation engine's terms.

Private. Part of the formula feature's archive half, reached by the table save
that registers each formula with the engine.

UPDATES
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
) -> FormulaDependencies:
    """Return what one formula reads, in the engine's own terms.

    The formula says which table by identity and where by offset; the engine wants
    an internal owner id and an absolute coordinate, so this is where the two meet.
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
                bottom=extent.bottom,
                right=extent.right,
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

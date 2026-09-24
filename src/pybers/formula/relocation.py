#!/usr/bin/env python3
"""The rule a caller names for what every reference keeps when cells change address.

**Numbers performs both rules**, measured 2026-09-23 in `60-move-*`. Dragging a
block keeps each reference on the cell it named, and cut and paste keeps each
reference's offset from its formula. Neither is a default, so every operation
relocating cells takes one from its caller.

**A moved range reaching past its table ends at the table's edge**, the one rewrite
cut and paste makes: `SUM(A1:A12)` pasted six rows lower in a table of twelve rows
was stored as `SUM(E7:E12)`, not `SUM(E7:E18)`. A single reference past the edge is
kept, and shows an error.

UPDATES
2026-09-23  Written for PYB-18.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/23"

from enum import StrEnum

from pybers.addressing.reference import CellReference
from pybers.formula.nodes import Formula, FormulaNode, FormulaRange, Span


class FormulaReferenceRelocation(StrEnum):
    """What each reference a relocation touches keeps: its named cell or its offset."""

    PRESERVE_NAMED_CELL = "named-cell"
    PRESERVE_RELATIVE_POSITION = "relative-position"


def clampSpan(span: Span | None, host: int, count: int) -> Span | None:
    """Return one axis of a range ending no further than the table's last line."""
    if span is None:
        return None
    begin, end = span.resolve(host)
    if end <= count or begin > count:
        return span
    shift = 0 if span.absolute else host
    return Span(begin - shift, None if begin == count else count - shift, span.absolute)


def clampFormulaRanges(
    formula: Formula, host: CellReference, rowCount: int, columnCount: int
) -> Formula:
    """Return a formula whose ranges in its own table stop at that table's edge."""
    nodes = []
    for node in formula.nodes:
        content = node.content
        if isinstance(content, FormulaRange) and content.tableId is None:
            clamped = FormulaRange(
                clampSpan(content.columns, host.col, columnCount),
                clampSpan(content.rows, host.row, rowCount),
                content.tableId,
            )
            if clamped != content:
                node = FormulaNode(node.nodeType, clamped, node.raw)
        nodes.append(node)
    if all(new is old for new, old in zip(nodes, formula.nodes, strict=True)):
        return formula
    return Formula(tuple(nodes))


__all__ = ["FormulaReferenceRelocation", "clampFormulaRanges"]

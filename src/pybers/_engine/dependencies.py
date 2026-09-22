#!/usr/bin/env python3
"""\
What a formula reads, in the engine's own terms: an owner id and a stored coordinate.

UPDATES
2026-09-22  Split out of the engine module for PYB-113.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/22"

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CellEdge:
    """One cell a formula reads, its owner named only when it is another table."""

    row: int
    column: int
    owner: int | None = None


@dataclass(frozen=True, slots=True)
class RangeEdge:
    """One bounded rectangle a formula reads, in the owner that holds it."""

    top: int
    left: int
    bottom: int
    right: int
    owner: int


@dataclass(frozen=True, slots=True)
class SpanEdge:
    """Whole columns or whole rows a formula reads, in the owner that holds them."""

    begin: int
    end: int
    columns: bool
    owner: int


@dataclass(frozen=True, slots=True)
class FormulaDependencies:
    """Everything one formula reads, which is what makes it recompute again.

    Numbers evaluates an undeclared formula once, on open, in an order of its own,
    so a formula reading a cell computed after it caches that cell's stale state.
    See findings-02-formulas.md.
    """

    cells: tuple[CellEdge, ...] = ()
    ranges: tuple[RangeEdge, ...] = ()
    spans: tuple[SpanEdge, ...] = ()


__all__ = [
    "CellEdge",
    "FormulaDependencies",
    "RangeEdge",
    "SpanEdge",
]

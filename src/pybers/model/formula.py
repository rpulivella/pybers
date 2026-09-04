#!/usr/bin/env python3
"""\
A formula as the tree the file actually stores, rather than as text.

There is no formula text anywhere in a `.numbers` package. `TSCE.FormulaArchive`
carries one field of content, a flat array of nodes in postfix order, and Numbers
renders the text you see from that tree every time. Confirmed against the
extracted schemas: the archive has no string field to put a formula in, and the
only strings near one are a literal inside it and the spelling of a function
Numbers could not resolve.

Two consequences shape everything here. A formula cannot be modeled as a string
without inventing a language to parse, losing the per-axis locking flags on the
way through. And a walk over nodes is all that a reader or a rewriter needs,
which is why no parser appears in this library.

**A reference is a distance, not a position.** An unlocked reference stores a
signed offset from the cell holding the formula, which is why Numbers can share
one archive between a formula and every cell it was dragged into, and why moving
a formula needs no rewriting at all. Locking an axis switches the number to a
fixed line. `Coordinate` is the only thing that knows which of the two a given
number is, and `resolve` is the only way to turn one into a real coordinate.

**Anchoring is recorded in two different places depending on the node**, measured
across the whole fixture corpus on 2026-09-03. A single-cell reference carries it
only as `absolute` on each coordinate: not one of the 21 such nodes in the corpus
carries `ASTStickyBits`. A range carries both, the field variant it sits in and
the sticky bits beside it. Reading the sticky bits as authoritative for a
single-cell reference therefore finds nothing and reports everything unlocked.

**Unboundedness is absence.** `SUM(A)` stores a column and no row at all, so a
row of `None` means the whole column rather than row zero. The same rule
`pybers.model.ranges` already follows.

UPDATES
2026-09-03  Written for #41. Node types, the key slot and the sticky-bits rule
            were all measured against the corpus rather than read off the schema,
            which permits far more than Numbers writes.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/03"

from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal

from pybers.model.ranges import CellRange
from pybers.model.reference import CellReference

# The node types this model gives meaning to. Every other type is carried through
# untouched: the node message has 45 fields and the corpus uses 16, so a model
# claiming to understand the rest would be describing the schema rather than the
# documents. Operators are deliberately absent, since naming them is cosmetic and
# a formula rewriter never needs to know that 1 is addition.
functionNodeType: int = 16
numberNodeType: int = 17
stringNodeType: int = 19
unknownFunctionNodeType: int = 31
referenceNodeType: int = 36
brokenReferenceNodeType: int = 46
rangeNodeType: int = 67

# A deleted reference is node type 46 carrying coordinates deliberately pointing
# nowhere. Read as ordinary numbers they name a cell far outside any table and
# raise nothing, which is why they are recognized here rather than at a caller.
brokenColumnSentinel: int = 32767
brokenRowSentinel: int = 2147483647


class FormulaError(ValueError):
    """A formula that could not be read, or an edit that would corrupt one."""


@dataclass(frozen=True, slots=True)
class Coordinate:
    """One axis of a reference, and the only thing that knows what its number is.

    `value` is a signed distance when relative and a line counted from one when
    absolute. The two are not interchangeable, so read it through `resolve`.
    """

    value: int
    absolute: bool = False

    def resolve(self, host: int) -> int:
        """Return the row or column this axis names, for a formula living at `host`.

        `host` is the corresponding axis of the cell holding the formula, counted
        from one. An absolute axis ignores it, which is exactly what locking means.
        """
        return self.value if self.absolute else host + self.value


@dataclass(frozen=True, slots=True)
class Span:
    """One axis of a range: where it begins, where it ends, and whether it is fixed.

    `end` is absent for a span of one line, as the file stores it. Both ends share
    one `absolute`: the file keeps an axis in either the relative field or the
    absolute one, and cannot express a range locked at one end only.
    """

    begin: int
    end: int | None = None
    absolute: bool = False

    @property
    def last(self) -> int:
        """Return the closing line of this span, which is `begin` when it spans one."""
        return self.begin if self.end is None else self.end

    def resolve(self, host: int) -> tuple[int, int]:
        """Return the first and last line this axis covers, for a formula at `host`.

        An absolute axis ignores `host`, exactly as `Coordinate.resolve` does. The
        two are kept apart because a span has an end to carry and a coordinate
        does not, and folding them would put an unused end on every reference.
        """
        if self.absolute:
            return (self.begin, self.last)
        return (host + self.begin, host + self.last)


@dataclass(frozen=True, slots=True)
class FormulaReference:
    """A reference to one cell from inside a formula.

    An axis of `None` is unbounded rather than zero, so no row means the whole
    column. `tableId` names another table by identity, never by name or position,
    which is why renaming a table cannot break a formula pointing into it.
    """

    column: Coordinate | None = None
    row: Coordinate | None = None
    tableId: str | None = None
    broken: bool = False

    @property
    def crossTable(self) -> bool:
        """Report whether this reference points into a different table."""
        return self.tableId is not None

    def resolve(self, host: CellReference) -> CellReference:
        """Return the cell this reference names, for a formula living at `host`.

        Refuses rather than guessing on the two cases that have no single cell to
        name: a broken reference, whose coordinates point nowhere by design, and
        an unbounded one, which names a whole column or row.
        """
        if self.broken:
            raise FormulaError(
                "This reference is broken and names no cell. Numbers stores it "
                "with sentinel coordinates precisely because there is nothing "
                "left to point at."
            )
        if self.column is None or self.row is None:
            raise FormulaError(
                "This reference is unbounded on one axis, so it names a whole "
                "column or row rather than a cell."
            )
        return CellReference(
            self.row.resolve(host.row),
            self.column.resolve(host.col),
            rowAbsolute=self.row.absolute,
            colAbsolute=self.column.absolute,
        )


@dataclass(frozen=True, slots=True)
class FormulaRange:
    """A rectangle of cells named from inside a formula.

    Carried separately from `FormulaReference` because a range is its own node
    type with its own anchoring, which is what makes adjusting one range in a
    multi-range call unable to disturb the others.
    """

    columns: Span | None = None
    rows: Span | None = None
    tableId: str | None = None

    @property
    def crossTable(self) -> bool:
        """Report whether this range points into a different table."""
        return self.tableId is not None

    def resolve(self, host: CellReference) -> CellRange:
        """Return the rectangle this range covers, for a formula living at `host`.

        The counterpart of `FormulaReference.resolve`, where a formula's vocabulary
        rejoins ordinary addressing. An unbounded axis stays unbounded, which
        `CellRange` represents as absence rather than as a span of every row.
        """
        rows = (
            self.rows.resolve(host.row) if self.rows is not None else (None, None)
        )
        columns = (
            self.columns.resolve(host.col)
            if self.columns is not None
            else (None, None)
        )
        rowLocked = self.rows.absolute if self.rows is not None else False
        columnLocked = self.columns.absolute if self.columns is not None else False
        return CellRange.fromAxes(
            ((rows[0], rowLocked), (rows[1], rowLocked)),
            ((columns[0], columnLocked), (columns[1], columnLocked)),
        )


@dataclass(frozen=True, slots=True)
class FormulaFunctionCall:
    """A call to one of Apple's built-in functions, named by its own index.

    The index is numeric in the archive and no name map ships with this library
    yet, so 168 is SUM and this model says so no further. Deriving that map is
    its own work.
    """

    index: int
    argumentCount: int


@dataclass(frozen=True, slots=True)
class FormulaUnknownCall:
    """A function Numbers itself could not resolve, which keeps its spelling.

    Numbers preserves the text rather than discarding the formula, so a document
    written by something else still round-trips. This model does the same.
    """

    name: str
    argumentCount: int


# What a node carries. A number literal's content is a Decimal and a string
# literal's is a str, so neither needs a wrapper class to be told apart from the
# others. An operator carries nothing, its meaning being its type and its arity
# implied.
NodeContent = (
    Decimal
    | str
    | FormulaFunctionCall
    | FormulaUnknownCall
    | FormulaReference
    | FormulaRange
    | None
)


@dataclass(frozen=True, slots=True)
class FormulaNode:
    """One node of a formula, in the postfix order the file stores.

    `raw` is the node's archive bytes as read, kept so a node this model does not
    interpret survives a rewrite exactly. Excluded from equality, being provenance
    rather than content.
    """

    nodeType: int
    content: NodeContent = None
    raw: bytes = field(default=b"", compare=False, repr=False)

    @property
    def recognized(self) -> bool:
        """Report whether this model gave the node meaning beyond its type."""
        return self.content is not None


@dataclass(frozen=True, slots=True)
class Formula:
    """One cell's formula, as the postfix node array the file stores.

    Frozen for the same reason `Style` is: Numbers shares one archive between every
    cell a formula was dragged into, so a mutable one would turn a single edit into
    a silent edit of all of them. Replace it on the cell to change it.
    """

    nodes: tuple[FormulaNode, ...] = ()

    def __iter__(self) -> Iterator[FormulaNode]:
        """Walk the nodes in stored order, so a formula reads as its own sequence."""
        return iter(self.nodes)

    def __len__(self) -> int:
        """Return the number of nodes, which is what postfix order counts."""
        return len(self.nodes)

    @property
    def references(self) -> tuple[FormulaReference, ...]:
        """Return every single-cell reference in this formula, in stored order."""
        return tuple(
            node.content for node in self.nodes
            if isinstance(node.content, FormulaReference)
        )

    @property
    def ranges(self) -> tuple[FormulaRange, ...]:
        """Return every range in this formula, each of which is its own node.

        Separate from `references` because a multi-range call carries each range
        as an independent node, and a walk that stopped at the first one would
        silently miss the rest of the argument list.
        """
        return tuple(
            node.content for node in self.nodes
            if isinstance(node.content, FormulaRange)
        )

    @property
    def broken(self) -> bool:
        """Report whether any reference in this formula points nowhere."""
        return any(
            isinstance(node.content, FormulaReference) and node.content.broken
            for node in self.nodes
        )


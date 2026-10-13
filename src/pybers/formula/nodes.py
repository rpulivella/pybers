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
across every document on 2026-09-03. A single-cell reference carries it
only as `absolute` on each coordinate: not one of the 21 such nodes in the documents
carries `ASTStickyBits`. A range carries both, the field variant it sits in and
the sticky bits beside it. Reading the sticky bits as authoritative for a
single-cell reference therefore finds nothing and reports everything unlocked.

**Unboundedness is absence.** `SUM(A)` stores a column and no row at all, so a
row of `None` means the whole column rather than row zero. The same rule
`pybers.addressing.ranges` already follows. A range's tract stores the unbounded axis
as a sentinel line, read here as `None`.

UPDATES
2026-10-13  A boolean literal and a range reaching every row or column, for PYB-139.
2026-09-18  A broken reference names the rows and columns it lost, for PYB-17.
2026-09-11  Apple's list node is a bracket the author typed, for #67. It
            enclosed one value in all 4364 instances measured.
2026-09-08  A reference and a range follow a target that moved, for #13. A
            locked axis stays where it is, which is what locking means.
2026-09-08  The operator node types, the thunking functions, and content
            for the nodes `LET` and `LAMBDA` are stored as, for #45.
2026-09-04  Function calls name themselves and know their argument counts,
            for #44. The index stays the stored form, so authoring by name
            and by index write one archive.
2026-09-03  Written for #41. Node types, the key slot and the sticky-bits rule
            were all measured against the documents rather than read off the schema,
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

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellReference
from pybers.errors import PybersError
from pybers.formula.functions import (
    ArgumentCountError,
    NumbersFunction,
    findFunction,
    findFunctionIndex,
    findFunctionName,
    findFunctionNamed,
)

# The node types this model gives meaning to. Every other type is carried through
# untouched: the node message has 45 fields and the documents use 16, so a model
# claiming to understand the rest would be describing the schema rather than the
# documents.
functionNodeType: int = 16
numberNodeType: int = 17
booleanNodeType: int = 18
stringNodeType: int = 19
unknownFunctionNodeType: int = 31
referenceNodeType: int = 36
brokenReferenceNodeType: int = 46
rangeNodeType: int = 67

# Every operator Numbers declares, taken from `TSCE.ASTNodeArrayArchive.ASTNodeType`
# rather than from a spreadsheet grammar, so an operator this library does not know
# is a node type Apple did not declare. `test_formula_text` asserts the two agree.
# Reading it the other way round is what left numbers-parser, which took openpyxl's
# Excel tokenizer, with a precedence table holding no comparison at all.
additionNodeType: int = 1
subtractionNodeType: int = 2
multiplicationNodeType: int = 3
divisionNodeType: int = 4
powerNodeType: int = 5
concatenationNodeType: int = 6
greaterThanNodeType: int = 7
greaterThanOrEqualNodeType: int = 8
lessThanNodeType: int = 9
lessThanOrEqualNodeType: int = 10
equalToNodeType: int = 11
notEqualToNodeType: int = 12
negationNodeType: int = 13
plusSignNodeType: int = 14
percentNodeType: int = 15

# A bracketed sub-expression, which Apple declares as `LIST_NODE` and gives one
# field, `AST_list_node_numArgs`. That field is 1 in all 4364 instances across six
# real documents, and a list of one is a bracket. It is the author's own bracket
# rather than one derived from precedence: 193 of the 379 distinct formulas
# carrying one enclose what precedence already bound. See
# docs/findings/findings-08-formula-text.md.
listNodeType: int = 25

# An argument the writer left out, which is what the commas of `DURATION(,,,K1,,)`
# each stand for.
emptyArgumentNodeType: int = 22

# A second node for an argument that is not there, which Numbers writes in some
# positions where it writes type 22 in others. `DURATION(,,,K1,,)` fills its first
# three with type 22 and its last two with this, and both evaluate to nothing:
# the arithmetic of the two duration measurements accounts for K1 and for no other
# argument. The rule choosing between them is not established, so this is
# rendered as the omitted argument it behaves as and never written.
tokenNodeType: int = 23

# The bracketing pair around an argument Numbers evaluates lazily, and the pair
# around a lambda body. Both carry nothing and neither reaches the text.
beginThunkNodeType: int = 34
endThunkNodeType: int = 35
beginLambdaThunkNodeType: int = 56
endLambdaThunkNodeType: int = 57

# Whitespace a person typed, kept beside the tokens rather than inside them.
appendWhitespaceNodeType: int = 32
prependWhitespaceNodeType: int = 33

# `LET` and `LAMBDA` are functions Numbers documents and offers in its own
# function browser, and the format stores neither as an indexed call: each gets
# node types of its own. Measured 2026-09-04 against
# tests/measurements/46-formula-rare-functions, from formulas Numbers accepted, a
# working `LET` and a `LAMBDA` reached through `LAMBDA.APPLY`.
letBindNodeType: int = 52
endScopeNodeType: int = 54
lambdaNodeType: int = 55
letNodeTypes: tuple[int, ...] = (letBindNodeType, endScopeNodeType)
lambdaNodeTypes: tuple[int, ...] = (
    lambdaNodeType, beginLambdaThunkNodeType, endLambdaThunkNodeType
)

# Both bind a variable, and Numbers' own authoring class calls the node that
# names one `letOrLambdaVar`, which is why it belongs to neither alone.
variableNodeType: int = 53

# The four functions whose arguments Numbers wraps in thunks, read from
# `+[TSCEFunctionSpec functionIndexUsesThunks:]` in Numbers 15.3.1, which compares
# its argument against exactly these and nothing else. CHOOSE, IF, IFS and SWITCH,
# and each thunks every argument after its first: measured for IF against
# tests/measurements/18-formula-literals, whose `IF(1>0,1,2)` brackets the two branches
# and leaves the condition bare.
thunkingFunctionIndices: frozenset[int] = frozenset({19, 62, 313, 336})

# A deleted reference is node type 46 carrying coordinates deliberately pointing
# nowhere. Read as ordinary numbers they name a cell far outside any table and
# raise nothing, which is why they are recognized here rather than at a caller.
brokenColumnSentinel: int = 32767
brokenRowSentinel: int = 2147483647

# A range reaching every row stores this absolute row with no end, and one reaching
# every column this column: the broken values again, given meaning by the node type.
# Measured in tests/measurements/71-whole-axis-ranges-and-booleans.
unboundedRangeColumn: int = brokenColumnSentinel
unboundedRangeRow: int = brokenRowSentinel


class FormulaError(PybersError, ValueError):
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

    def shifted(self, delta: int) -> Coordinate:
        """Return this axis pointing `delta` lines further on, or itself when locked.

        Locking pins an axis to a line, so a retarget leaves it there and `B$1`
        moved down a row is still `B$1`. Returning `self` unchanged is how a caller
        separates a move that happened from one with nothing to move.
        """
        if self.absolute or delta == 0:
            return self
        return Coordinate(self.value + delta, self.absolute)


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

    def shifted(self, delta: int) -> Span:
        """Return this span `delta` lines further on, both ends together or neither.

        One `absolute` covers both ends, so moving one end alone is unrepresentable
        here rather than merely discouraged, which is what keeps `C3:C25` a span of
        23 lines however far it travels.
        """
        if self.absolute or delta == 0:
            return self
        return Span(
            self.begin + delta,
            None if self.end is None else self.end + delta,
            self.absolute,
        )


@dataclass(frozen=True, slots=True)
class FormulaReferenceLoss:
    """The rows and columns a broken reference named before they were removed.

    Numbers writes these beside the `#REF!` sentinels, as each line's UUID value,
    in all three references measured breaking. `range` records whether a range
    broke rather than a single cell, and each axis keeps the lock it had.
    """

    columns: tuple[int, ...] = ()
    rows: tuple[int, ...] = ()
    range: bool = False
    columnsAbsolute: bool = False
    rowsAbsolute: bool = False


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
    loss: FormulaReferenceLoss | None = None

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
                "This reference is broken and names no cell."
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

    def shifted(self, *, rows: int = 0, cols: int = 0) -> FormulaReference:
        """Return this reference pointing `rows` down and `cols` right, or itself.

        A broken reference comes back untouched: Numbers records `#REF` as
        coordinates deliberately pointing nowhere, and moving them would repair one
        into a working cell. An unbounded axis names a whole column or row and has
        no line to move either.
        """
        if self.broken:
            return self
        column = None if self.column is None else self.column.shifted(cols)
        row = None if self.row is None else self.row.shifted(rows)
        if column is self.column and row is self.row:
            return self
        return FormulaReference(column, row, self.tableId)


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

    def shifted(self, *, rows: int = 0, cols: int = 0) -> FormulaRange:
        """Return this range `rows` down and `cols` right, or itself when it cannot.

        Both ends of an axis travel together, since `Span` carries them as one, so
        a range that moves keeps the block it covers rather than growing.
        """
        columns = None if self.columns is None else self.columns.shifted(cols)
        movedRows = None if self.rows is None else self.rows.shifted(rows)
        if columns is self.columns and movedRows is self.rows:
            return self
        return FormulaRange(columns, movedRows, self.tableId)


@dataclass(frozen=True, slots=True)
class FormulaFunctionCall:
    """A call to one of Apple's built-in functions, stored as its index.

    The index is what the archive holds, so `named` is a way of writing one down
    rather than a second representation. `name` is None for a function the map
    does not carry, which leaves the call intact rather than refusing it.
    """

    index: int
    argumentCount: int

    @property
    def name(self) -> str | None:
        """Return the function's name, or None when the table does not carry it."""
        return findFunctionName(self.index)

    @property
    def function(self) -> NumbersFunction | None:
        """Return the function this calls, with its argument counts, or None."""
        return findFunction(self.index)

    @classmethod
    def named(cls, name: str, argumentCount: int) -> FormulaFunctionCall:
        """Build a call by function name, `SUM` or `sum`, checking the count.

        Refuses a name Numbers does not offer and a count it does not accept,
        since either would store as an error cell. Construct with an index to
        write one anyway.
        """
        function = findFunctionNamed(name)
        if not function.offered:
            raise ArgumentCountError(
                f"{function.name} is {function.availability} rather than offered, "
                "so Numbers does not take it by name. Construct with its index "
                "if you mean to write one anyway."
            )
        if not function.accepts(argumentCount):
            bound = "any number" if function.unbounded else function.maximumArguments
            raise ArgumentCountError(
                f"{function.name} takes {function.minimumArguments} to {bound} "
                f"arguments, not {argumentCount}."
            )
        return cls(index=findFunctionIndex(name), argumentCount=argumentCount)


@dataclass(frozen=True, slots=True)
class FormulaUnknownCall:
    """A function Numbers itself could not resolve, which keeps its spelling.

    Numbers preserves the text rather than discarding the formula, so a document
    written by something else still round-trips. This model does the same.
    """

    name: str
    argumentCount: int


@dataclass(frozen=True, slots=True)
class FormulaBinding:
    """The name `LET` gives a value, and the number every use of it carries.

    Numbers writes the spelling once, on the binding, and refers to it afterward by
    a number counting from one within the formula. Both are kept because the number
    is what the archive matches on and the spelling is what a person reads.
    """

    name: str
    symbol: int
    continuation: bool = False


@dataclass(frozen=True, slots=True)
class FormulaVariable:
    """One use of a name a `LET` or a `LAMBDA` bound, stored as its number alone.

    The spelling lives on the binding rather than here, so renaming a bound value
    is one edit rather than one per use.
    """

    symbol: int


@dataclass(frozen=True, slots=True)
class FormulaLambda:
    """A `LAMBDA`'s parameter names, and the number the first of them takes.

    The names are the archive's own list and the numbering runs on from
    `firstSymbol`, which is zero when a lambda takes no parameters at all.
    """

    names: tuple[str, ...] = ()
    firstSymbol: int = 0


@dataclass(frozen=True, slots=True)
class FormulaGroup:
    """A bracketed sub-expression, and how many values its brackets enclose.

    `argumentCount` is 1 in every instance measured, which is what makes Apple's
    list node a bracket. It is carried rather than assumed so that a wider one is
    refused by the renderer instead of written out as something it is not.
    """

    argumentCount: int = 1


# What a node carries. A number literal's content is a Decimal and a string
# literal's is a str, so neither needs a wrapper class to be told apart from the
# others. An operator carries nothing, its meaning being its type and its arity
# implied.
NodeContent = (
    Decimal
    | bool
    | str
    | FormulaFunctionCall
    | FormulaGroup
    | FormulaUnknownCall
    | FormulaReference
    | FormulaRange
    | FormulaBinding
    | FormulaVariable
    | FormulaLambda
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


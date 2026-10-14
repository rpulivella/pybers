#!/usr/bin/env python3
"""\
A stored formula out as the text Numbers displays for it.

The other half of `pybers.formula.parse`, and the half that makes it
testable: comparing hand-written node arrays stops scaling at about a dozen
cases, and rendering every formula in a real document and parsing it back does
not. See docs/findings/findings-08-formula-text.md.

It walks a stack, because the file is postfix. Each node takes what it needs off
that stack and puts one piece back, and a complete formula leaves exactly one.

**Brackets come from two places, and both are needed.** Apple's list node records
the bracket an author typed, including the 193 distinct formulas whose brackets
precedence already implied. It does not record every bracket: one formula in the
documents needs one that associativity alone forces and carries no node for it, so
the tree still has to supply what the nodes do not.

**What a person cannot type is dropped.** The whitespace nodes record where a
person pressed the space bar, which retyping the formula in Numbers drops too, and
the thunk brackets are structure the parser puts back from the function.

UPDATES
2026-10-13  A node renders by matching what it holds, checked exhaustive by
            mypy, for PYB-139.
2026-10-13  A boolean literal renders as TRUE or FALSE, for PYB-139.
2026-09-11  A bracket the author typed is written back, for #67. The claim that
            the file records no parentheses was false; node type 25 is one.
2026-09-08  `renderAddress` and `findShortestNames` exported for #13, so that one
            reference can be shown without rendering the formula around it.
2026-09-08  Written for #45.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import assert_never

from pybers.addressing.ranges import RangeEndpoint, renderEndpoint
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    tableNameSeparator,
    toCellReference,
)
from pybers.formula.nodes import (
    Formula,
    FormulaBinding,
    FormulaError,
    FormulaFunctionCall,
    FormulaGroup,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaUnknownCall,
    FormulaVariable,
    additionNodeType,
    emptyArgumentNodeType,
    endScopeNodeType,
    negationNodeType,
    percentNodeType,
    plusSignNodeType,
    powerNodeType,
    subtractionNodeType,
    tokenNodeType,
)
from pybers.formula.syntax import (
    argumentSeparator,
    atomPrecedence,
    booleanTexts,
    brokenReferenceText,
    cosmeticNodeTypes,
    formulaMarker,
    lambdaName,
    letName,
    operatorPrecedence,
    operatorSymbols,
    percentSymbol,
    quoteString,
    thunkNodeTypes,
)


@dataclass(frozen=True, slots=True)
class Rendered:
    """One finished piece of text, and how tightly the operator in it binds.

    The precedence travels with the text so that whatever encloses it can decide
    on brackets without parsing what it is enclosing.
    """

    text: str
    precedence: int = atomPrecedence

    def enclosed(self, within: int) -> str:
        """Return this text, bracketed when the enclosing operator binds tighter."""
        return f"({self.text})" if self.precedence < within else self.text


def collectBoundNames(formula: Formula) -> dict[int, str]:
    """Return the name every symbol in a formula carries, from its own bindings.

    Read in one pass up front because a use comes before its `LAMBDA` in stored
    order: the body is on the stack by the time the node naming its parameters
    arrives.
    """
    names: dict[int, str] = {}
    for node in formula:
        content = node.content
        if isinstance(content, FormulaBinding):
            names[content.symbol] = content.name
        elif isinstance(content, FormulaLambda):
            for offset, name in enumerate(content.names):
                names[content.firstSymbol + offset] = name
    return names


def renderAddress(
    node: FormulaNode, host: CellReference, names: Mapping[str, str]
) -> str:
    """Return the text of one reference or range node, from the cell holding it."""
    content = node.content
    if isinstance(content, FormulaReference) and content.broken:
        return brokenReferenceText
    if isinstance(content, FormulaReference):
        column = content.column
        row = content.row
        body = renderEndpoint(
            RangeEndpoint(
                None if row is None else row.resolve(host.row),
                None if column is None else column.resolve(host.col),
                row.absolute if row is not None else False,
                column.absolute if column is not None else False,
            )
        )
        return qualifyAddress(body, content.tableId, names)
    if not isinstance(content, FormulaRange):
        raise FormulaError(f"Node type {node.nodeType} names no address.")
    extent = content.resolve(host)
    first = renderEndpoint(
        RangeEndpoint(
            extent.startRow, extent.startCol,
            extent.startRowAbsolute, extent.startColAbsolute,
        )
    )
    last = renderEndpoint(
        RangeEndpoint(
            extent.endRow, extent.endCol,
            extent.endRowAbsolute, extent.endColAbsolute,
        )
    )
    # Written out even when both ends coincide, because a tract covering one cell
    # is a range in the file and reading `A1` back would make it a coordinate.
    return qualifyAddress(f"{first}:{last}", content.tableId, names)


def qualifyAddress(
    body: str, tableId: str | None, names: Mapping[str, str]
) -> str:
    """Return an address with the name of the table it reaches into, when it does."""
    if tableId is None:
        return body
    name = names.get(tableId)
    if name is None:
        raise FormulaError(
            f"This formula reaches into table {tableId}, and no name was given "
            "for it. Pass `tables=document.tableIdentities` to name it."
        )
    return f"{name}{tableNameSeparator}{body}"


def renderNumber(value: Decimal) -> str:
    """Return a literal as it was written, without normalizing what it says."""
    return str(value)


def renderCall(name: str, arguments: list[Rendered]) -> Rendered:
    """Return one call written out, its arguments in the order they were stored."""
    body = argumentSeparator.join(item.text for item in arguments)
    return Rendered(f"{name}({body})")


@dataclass(slots=True)
class Renderer:
    """One walk over a stored formula, building the text Numbers displays for it.

    A stack, because the file is postfix: each node takes what it needs off the
    stack and puts one piece back, and a complete formula leaves exactly one.
    """

    formula: Formula
    host: CellReference
    names: Mapping[str, str]
    symbols: dict[int, str] = field(default_factory=dict)
    stack: list[Rendered] = field(default_factory=list)
    bindings: list[tuple[str, str, bool]] = field(default_factory=list)

    def pop(self, count: int) -> list[Rendered]:
        """Return the last `count` pieces, in the order they were pushed."""
        if len(self.stack) < count:
            raise FormulaError(
                f"This formula asks for {count} values with {len(self.stack)} on "
                "the stack, so its nodes do not form one expression."
            )
        taken = self.stack[len(self.stack) - count:]
        del self.stack[len(self.stack) - count:]
        return taken

    def render(self) -> str:
        """Walk every node, and return the one piece a whole formula leaves behind."""
        self.symbols = dict(collectBoundNames(self.formula))
        for node in self.formula:
            self.step(node)
        if len(self.stack) != 1:
            raise FormulaError(
                f"This formula leaves {len(self.stack)} values rather than one, "
                "so it is not a single expression."
            )
        return f"{formulaMarker}{self.stack[0].text}"

    def step(self, node: FormulaNode) -> None:
        """Take one node, and put what it makes of the stack back onto it.

        Matched on what the node holds, and `assert_never` makes mypy name any
        content type the model gains and this does not render.
        """
        kind = node.nodeType
        content = node.content
        if kind in cosmeticNodeTypes or kind in thunkNodeTypes:
            return
        match content:
            case bool():
                self.stack.append(Rendered(booleanTexts[content]))
            case Decimal():
                self.stack.append(Rendered(renderNumber(content)))
            case str():
                self.stack.append(Rendered(quoteString(content)))
            case FormulaReference() | FormulaRange():
                self.stack.append(
                    Rendered(renderAddress(node, self.host, self.names))
                )
            case FormulaGroup():
                self.stepGroup(content)
            case FormulaFunctionCall():
                self.stepCall(content)
            case FormulaUnknownCall():
                self.stack.append(
                    renderCall(content.name, self.pop(content.argumentCount))
                )
            case FormulaVariable():
                self.stepVariable(content)
            case FormulaBinding():
                value = self.pop(1)[0]
                self.bindings.append((content.name, value.text, content.continuation))
            case FormulaLambda():
                self.stepLambda(content)
            case None:
                self.stepBare(kind)
            case _:
                assert_never(content)

    def stepBare(self, kind: int) -> None:
        """Take a node that holds nothing, whose type alone says what it does."""
        # Type 23 is the second spelling of an argument that is not there, and it
        # writes the same nothing. Reading it back gives type 22, the only one of
        # the two whose placement is established, so those formulas round trip
        # through the text and not through the node type.
        if kind in (emptyArgumentNodeType, tokenNodeType):
            self.stack.append(Rendered(""))
        elif kind == endScopeNodeType:
            self.stepEndScope()
        elif kind in operatorPrecedence:
            self.stepOperator(kind)
        else:
            raise FormulaError(
                f"Node type {kind} has no written form. A formula holding one can "
                "be read and written back, and cannot be rendered as text."
            )

    def stepGroup(self, group: FormulaGroup) -> None:
        """Bracket the piece on top of the stack, as the author bracketed it.

        The result scores as an atom, so an operator enclosing it adds no second
        pair. Refuses a wider list: every one of the 4364 measured encloses one
        value, and rendering a wider one as a bracket would state something the
        documents do not support.
        """
        if group.argumentCount != 1:
            raise FormulaError(
                f"This list node encloses {group.argumentCount} values, and every "
                "one measured encloses a single value. A formula holding it can "
                "be read and written back, and cannot be rendered as text."
            )
        self.stack.append(Rendered(f"({self.pop(1)[0].text})"))

    def stepCall(self, call: FormulaFunctionCall) -> None:
        """Write one indexed call, refusing an index nothing names."""
        if call.name is None:
            raise FormulaError(
                f"Function {call.index} is not in the table this build carries, so "
                "there is no name to write. Regenerate it with "
                "tools/local/functions_extract.py."
            )
        self.stack.append(renderCall(call.name, self.pop(call.argumentCount)))

    def stepVariable(self, variable: FormulaVariable) -> None:
        """Write one use of a bound name, refusing a number nothing bound."""
        name = self.symbols.get(variable.symbol)
        if name is None:
            raise FormulaError(
                f"This formula uses value {variable.symbol} and binds no name to "
                "it, so there is nothing to write."
            )
        self.stack.append(Rendered(name))

    def stepEndScope(self) -> None:
        """Write the `LET` whose bindings have been collected, and its body."""
        body = self.pop(1)[0]
        taken: list[tuple[str, str, bool]] = []
        while self.bindings:
            binding = self.bindings.pop()
            taken.insert(0, binding)
            if not binding[2]:
                break
        if not taken:
            raise FormulaError("A scope ends here having bound nothing.")
        pieces = [part for name, value, _ in taken for part in (name, value)]
        pieces.append(body.text)
        self.stack.append(Rendered(f"{letName}({argumentSeparator.join(pieces)})"))

    def stepLambda(self, lambdaNode: FormulaLambda) -> None:
        """Write one `LAMBDA`, its parameter names ahead of the body they serve."""
        body = self.pop(1)[0]
        pieces = [*lambdaNode.names, body.text]
        self.stack.append(
            Rendered(f"{lambdaName}({argumentSeparator.join(pieces)})")
        )

    def stepOperator(self, kind: int) -> None:
        """Write one operator, bracketing an operand only where the tree needs it."""
        level = operatorPrecedence[kind]
        if kind == percentNodeType:
            operand = self.pop(1)[0]
            self.stack.append(
                Rendered(f"{operand.enclosed(level)}{percentSymbol}", level)
            )
            return
        if kind in (negationNodeType, plusSignNodeType):
            operand = self.pop(1)[0]
            symbol = operatorSymbols[
                subtractionNodeType if kind == negationNodeType else additionNodeType
            ]
            self.stack.append(
                Rendered(f"{symbol}{operand.enclosed(level)}", level)
            )
            return
        left, right = self.pop(2)
        symbol = operatorSymbols[kind]
        # The right operand of a left-associative operator is bracketed at equal
        # precedence as well, since `1-(2-3)` and `1-2-3` are different trees and
        # the text has to keep them apart. `^` is the one that leans the other way.
        if kind == powerNodeType:
            leftText = f"({left.text})" if left.precedence <= level else left.text
            rightText = right.enclosed(level)
        else:
            leftText = left.enclosed(level)
            rightText = (
                f"({right.text})" if right.precedence <= level else right.text
            )
        self.stack.append(Rendered(f"{leftText}{symbol}{rightText}", level))


def renderFormula(
    formula: Formula,
    host: CellAddress,
    *,
    tables: Mapping[str, str] | None = None,
) -> str:
    """Return the text Numbers displays for a formula held in one cell.

    `host` is the cell holding it, because an unlocked reference is an offset from
    there and one archive shows differently in each cell it was dragged into.
    `tables` names the tables a formula reaches into, from `Document.tableIdentities`.
    """
    return Renderer(
        formula=formula, host=toCellReference(host), names=findShortestNames(tables)
    ).render()


def findShortestNames(tables: Mapping[str, str] | None) -> dict[str, str]:
    """Return the shortest name each table identity answers to, keyed by identity.

    The inverse of `Document.tableIdentities`, which carries both `Table 2` and
    `Sheet 1::Table 2` for the same table, so that a formula reads `Table 2::A1`
    where that is unambiguous and qualifies further only where it has to.
    """
    names: dict[str, str] = {}
    for name, identity in sorted(
        (tables or {}).items(), key=lambda pair: (len(pair[0]), pair[0])
    ):
        names.setdefault(identity, name)
    return names


__all__ = ["renderAddress", "renderFormula", "findShortestNames"]

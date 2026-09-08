#!/usr/bin/env python3
"""\
A stored formula out as the text Numbers displays for it.

The other half of `pybers.model.formulaparse`, and the half that makes it
testable: comparing hand-written node arrays stops scaling at about a dozen
cases, and rendering every formula in a real document and parsing it back does
not. See tests/fixtures/findings-08-formula-text.md.

It walks a stack, because the file is postfix. Each node takes what it needs off
that stack and puts one piece back, and a complete formula leaves exactly one.

**Brackets are put in from the tree rather than remembered.** The file records no
parentheses, so two formulas differing only in where they were bracketed differ
only in the order of their nodes, and what goes out has to bracket exactly what
the tree demands.

**What a person cannot type is dropped.** The whitespace nodes record where a
person pressed the space bar, which retyping the formula in Numbers drops too, and
the thunk brackets are structure the parser puts back from the function.

UPDATES
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

from pybers.addressing.ranges import RangeEndpoint, endpointText
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    tableNameSeparator,
    toCellReference,
)
from pybers.model.formula import (
    Formula,
    FormulaBinding,
    FormulaError,
    FormulaFunctionCall,
    FormulaLambda,
    FormulaNode,
    FormulaRange,
    FormulaReference,
    FormulaUnknownCall,
    FormulaVariable,
    additionNodeType,
    brokenReferenceNodeType,
    emptyArgumentNodeType,
    endScopeNodeType,
    negationNodeType,
    numberNodeType,
    percentNodeType,
    plusSignNodeType,
    powerNodeType,
    rangeNodeType,
    referenceNodeType,
    stringNodeType,
    subtractionNodeType,
    tokenNodeType,
)
from pybers.model.formulasyntax import (
    argumentSeparator,
    atomPrecedence,
    brokenReferenceText,
    cosmeticNodeTypes,
    formulaMarker,
    lambdaName,
    letName,
    operatorPrecedence,
    operatorSymbols,
    percentSymbol,
    quoted,
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


def boundNames(formula: Formula) -> dict[int, str]:
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


def addressText(
    node: FormulaNode, host: CellReference, names: Mapping[str, str]
) -> str:
    """Return the text of one reference or range node, from the cell holding it."""
    content = node.content
    if isinstance(content, FormulaReference) and content.broken:
        return brokenReferenceText
    if isinstance(content, FormulaReference):
        column = content.column
        row = content.row
        body = endpointText(
            RangeEndpoint(
                None if row is None else row.resolve(host.row),
                None if column is None else column.resolve(host.col),
                row.absolute if row is not None else False,
                column.absolute if column is not None else False,
            )
        )
        return qualifiedText(body, content.tableId, names)
    if not isinstance(content, FormulaRange):
        raise FormulaError(f"Node type {node.nodeType} names no address.")
    extent = content.resolve(host)
    first = endpointText(
        RangeEndpoint(
            extent.startRow, extent.startCol,
            extent.startRowAbsolute, extent.startColAbsolute,
        )
    )
    last = endpointText(
        RangeEndpoint(
            extent.endRow, extent.endCol,
            extent.endRowAbsolute, extent.endColAbsolute,
        )
    )
    # Written out even when both ends coincide, because a tract covering one cell
    # is a range in the file and reading `A1` back would make it a coordinate.
    return qualifiedText(f"{first}:{last}", content.tableId, names)


def qualifiedText(
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


def numberText(value: Decimal) -> str:
    """Return a literal as it was written, without normalizing what it says."""
    return str(value)


def callText(name: str, arguments: list[Rendered]) -> Rendered:
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
        self.symbols = dict(boundNames(self.formula))
        for node in self.formula:
            self.step(node)
        if len(self.stack) != 1:
            raise FormulaError(
                f"This formula leaves {len(self.stack)} values rather than one, "
                "so it is not a single expression."
            )
        return f"{formulaMarker}{self.stack[0].text}"

    def step(self, node: FormulaNode) -> None:
        """Take one node, and put what it makes of the stack back onto it."""
        kind = node.nodeType
        content = node.content
        if kind in cosmeticNodeTypes or kind in thunkNodeTypes:
            return
        if kind == numberNodeType and isinstance(content, Decimal):
            self.stack.append(Rendered(numberText(content)))
            return
        if kind == stringNodeType and isinstance(content, str):
            self.stack.append(Rendered(quoted(content)))
            return
        # Type 23 is the second spelling of an argument that is not there, and it
        # writes the same nothing. Reading it back gives type 22, the only one of
        # the two whose placement is established, so those formulas round trip
        # through the text and not through the node type.
        if kind in (emptyArgumentNodeType, tokenNodeType):
            self.stack.append(Rendered(""))
            return
        if kind in (referenceNodeType, brokenReferenceNodeType, rangeNodeType):
            self.stack.append(
                Rendered(addressText(node, self.host, self.names))
            )
            return
        if isinstance(content, FormulaFunctionCall):
            self.stepCall(content)
            return
        if isinstance(content, FormulaUnknownCall):
            self.stack.append(
                callText(content.name, self.pop(content.argumentCount))
            )
            return
        if isinstance(content, FormulaVariable):
            self.stepVariable(content)
            return
        if isinstance(content, FormulaBinding):
            value = self.pop(1)[0]
            self.bindings.append((content.name, value.text, content.continuation))
            return
        if kind == endScopeNodeType:
            self.stepEndScope()
            return
        if isinstance(content, FormulaLambda):
            self.stepLambda(content)
            return
        if kind in operatorPrecedence:
            self.stepOperator(kind)
            return
        raise FormulaError(
            f"Node type {kind} has no written form. A formula holding one can be "
            "read and written back, and cannot be rendered as text."
        )

    def stepCall(self, call: FormulaFunctionCall) -> None:
        """Write one indexed call, refusing an index nothing names."""
        if call.name is None:
            raise FormulaError(
                f"Function {call.index} is not in the table this build carries, so "
                "there is no name to write. Regenerate it with "
                "tools/functions-extract.py."
            )
        self.stack.append(callText(call.name, self.pop(call.argumentCount)))

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
    # The shortest name a table answers to, so a formula reads `Table 2::A1` where
    # that is unambiguous and qualifies further only where it has to.
    names: dict[str, str] = {}
    for name, identity in sorted(
        (tables or {}).items(), key=lambda pair: (len(pair[0]), pair[0])
    ):
        names.setdefault(identity, name)
    return Renderer(
        formula=formula, host=toCellReference(host), names=names
    ).render()


__all__ = ["renderFormula"]

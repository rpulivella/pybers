#!/usr/bin/env python3
"""\
Formula text in, and the nodes the file stores out.

Text is a constructor and never reaches a package: Numbers stores no formula text
at all, so everything here ends as nodes. What it buys is an author who can write
a long expression rather than assembling a dozen nodes by hand.

Recursive descent, which puts the nodes out in postfix order by construction:
each rule parses its operands and then emits its own node, which is the order the
file holds, so nothing is built as a tree and flattened afterward.

**An argument count is not checked here, because Numbers does not refuse one
either.** A one-argument ROUND is stored and shown as an error in the cell, so
refusing it would decline text Numbers itself takes. A function Numbers declares
and then will not resolve, `ALTITUDE` among them, is written by its spelling,
which is also what Numbers writes.

**Thunks are put back rather than typed.** Numbers brackets every argument after
the first of the four functions that evaluate lazily, and a person types none of
that. See `thunkingFunctionIndices`.

UPDATES
2026-10-13  TRUE and FALSE without brackets are boolean literals, for PYB-139.
2026-09-11  A bracket becomes the node Numbers stores for one, for #67.
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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import (
    CellAddress,
    CellReference,
    CellReferenceLike,
    ReferenceError,
    toCellReference,
)
from pybers.formula.functions import FunctionAvailability, functionsByName
from pybers.formula.nodes import (
    Formula,
    FormulaBinding,
    FormulaFunctionCall,
    FormulaGroup,
    FormulaLambda,
    FormulaNode,
    FormulaReference,
    FormulaUnknownCall,
    FormulaVariable,
    NodeContent,
    additionNodeType,
    beginLambdaThunkNodeType,
    beginThunkNodeType,
    booleanNodeType,
    brokenReferenceNodeType,
    concatenationNodeType,
    divisionNodeType,
    emptyArgumentNodeType,
    endLambdaThunkNodeType,
    endScopeNodeType,
    endThunkNodeType,
    functionNodeType,
    lambdaNodeType,
    letBindNodeType,
    listNodeType,
    multiplicationNodeType,
    numberNodeType,
    percentNodeType,
    powerNodeType,
    rangeNodeType,
    referenceNodeType,
    stringNodeType,
    subtractionNodeType,
    thunkingFunctionIndices,
    unknownFunctionNodeType,
    variableNodeType,
)
from pybers.formula.syntax import (
    FormulaSyntaxError,
    Token,
    binaryOperators,
    booleanLiterals,
    buildRange,
    buildReference,
    comparisonOperators,
    formulaMarker,
    lambdaName,
    letName,
    nestingLimit,
    percentSymbol,
    resolveQualifierIdentity,
    tokenize,
    unaryOperators,
    unquote,
)


@dataclass(slots=True)
class Parser:
    """One pass over the tokens of one formula, emitting nodes in stored order.

    Recursive descent, so the nodes come out postfix by construction: each rule
    parses its operands and then emits its own node, which is the order the file
    holds. Nothing is built as a tree first and flattened afterward.
    """

    text: str
    tokens: list[Token]
    host: CellAddress
    tables: Mapping[str, str]
    pieces: Mapping[str, CellRange | CellReference]
    nodes: list[FormulaNode] = field(default_factory=list)
    bound: dict[str, int] = field(default_factory=dict)
    symbols: int = 0
    position: int = 0
    depth: int = 0

    def peek(self) -> Token:
        """Return the token about to be read, without consuming it."""
        return self.tokens[self.position]

    def take(self) -> Token:
        """Return the token about to be read, and move past it."""
        token = self.tokens[self.position]
        self.position += 1
        return token

    def accept(self, kind: str, text: str | None = None) -> Token | None:
        """Consume and return the next token when it is the one wanted."""
        token = self.peek()
        if token.kind != kind or (text is not None and token.text != text):
            return None
        return self.take()

    def fail(self, message: str, token: Token | None = None) -> FormulaSyntaxError:
        """Return the error to raise, pointing at the token that could not be used."""
        return FormulaSyntaxError(
            message, self.text, (token or self.peek()).position
        )

    def emit(self, nodeType: int, content: NodeContent = None) -> None:
        """Append one node in stored order."""
        self.nodes.append(FormulaNode(nodeType=nodeType, content=content))

    def parse(self) -> Formula:
        """Parse the whole text, refusing anything left over at the end."""
        if self.peek().kind == "end":
            raise self.fail("The formula is empty.")
        self.parseExpression()
        if self.peek().kind != "end":
            raise self.fail("This is left over after a complete formula.")
        return Formula(nodes=tuple(self.nodes))

    def parseExpression(self) -> None:
        """Parse one expression, the whole precedence ladder from the bottom.

        Depth is counted here because every nested construct passes through it,
        and refusing is what keeps hostile text from exhausting the stack and
        raising `RecursionError` where a formula error belongs.
        """
        if self.depth >= nestingLimit:
            raise self.fail(
                f"This nests more than {nestingLimit} levels deep, which is "
                "further than this parser goes."
            )
        self.depth += 1
        self.parseComparison()
        self.depth -= 1

    def parseComparison(self) -> None:
        """Parse comparisons, which bind least tightly of everything Numbers has."""
        self.parseBinary(
            self.parseConcatenation,
            {
                symbol: nodeType for symbol, nodeType in binaryOperators.items()
                if nodeType in comparisonOperators
            },
        )

    def parseConcatenation(self) -> None:
        """Parse `&`, which joins what arithmetic has already worked out."""
        self.parseBinary(self.parseAdditive, {"&": concatenationNodeType})

    def parseAdditive(self) -> None:
        """Parse addition and subtraction."""
        self.parseBinary(
            self.parseMultiplicative,
            {"+": additionNodeType, "-": subtractionNodeType},
        )

    def parseMultiplicative(self) -> None:
        """Parse multiplication and division."""
        self.parseBinary(
            self.parseUnary,
            {"*": multiplicationNodeType, "/": divisionNodeType},
        )

    def parseBinary(
        self, operand: Callable[[], None], operators: dict[str, int]
    ) -> None:
        """Parse one left-associative level: an operand, then any number of pairs."""
        operand()
        while True:
            token = self.peek()
            if token.kind != "operator" or token.text not in operators:
                return
            self.take()
            operand()
            self.emit(operators[token.text])

    def parseUnary(self) -> None:
        """Parse a prefix sign, which binds tighter than the power beneath it.

        `-2^2` is four, as in Numbers and in Excel: the sign belongs to the two
        before the square reaches it.
        """
        token = self.peek()
        if token.kind == "operator" and token.text in unaryOperators:
            self.take()
            self.parseUnary()
            self.emit(unaryOperators[token.text])
            return
        self.parsePower()

    def parsePower(self) -> None:
        """Parse `^`, which is right-associative and takes a signed exponent."""
        self.parsePostfix()
        if self.accept("operator", "^") is not None:
            self.parseUnary()
            self.emit(powerNodeType)

    def parsePostfix(self) -> None:
        """Parse the percent sign, which follows what it divides."""
        self.parsePrimary()
        while self.accept("operator", percentSymbol) is not None:
            self.emit(percentNodeType)

    def parsePrimary(self) -> None:
        """Parse one value: a literal, an address, a call, or a bracketed expression."""
        token = self.take()
        if token.kind == "number":
            try:
                self.emit(numberNodeType, Decimal(token.text))
            except InvalidOperation as exc:
                raise self.fail("This is not a number.", token) from exc
            return
        if token.kind == "string":
            self.emit(stringNodeType, unquote(token.text))
            return
        if token.kind == "broken":
            self.emit(brokenReferenceNodeType, FormulaReference(broken=True))
            return
        if token.kind == "placeholder":
            self.emitPiece(token)
            return
        if token.kind == "open":
            self.parseExpression()
            if self.accept("close") is None:
                raise self.fail("This bracket is opened and never closed.", token)
            # Recorded rather than discarded, because Numbers records it: a bracket
            # precedence does not need survives a round trip through Numbers itself.
            self.emit(listNodeType, FormulaGroup())
            return
        if token.kind in ("name", "address"):
            self.parseNamed(token)
            return
        raise self.fail("A value belongs here.", token)

    def parseNamed(self, token: Token) -> None:
        """Parse what a word introduced: a call, a bound value, or an address."""
        if self.peek().kind == "open":
            self.parseCall(token)
            return
        if token.kind == "name" and token.text in self.bound:
            self.emit(variableNodeType, FormulaVariable(self.bound[token.text]))
            return
        literal = booleanLiterals.get(token.text.upper())
        if literal is not None and not token.qualifier:
            self.emit(booleanNodeType, literal)
            return
        self.emitAddress(token)

    def emitPiece(self, token: Token) -> None:
        """Emit an address the caller handed over already built, by its name.

        The point of taking one is that it stays whatever this library validated
        rather than being spliced into a string and parsed back out.
        """
        piece = self.pieces.get(token.text)
        if piece is None:
            offered = ", ".join(sorted(repr(name) for name in self.pieces))
            raise self.fail(
                f"No address was given for {token.text!r}. "
                f"Given: {offered or 'nothing'}.",
                token,
            )
        if isinstance(piece, CellReference):
            self.emit(
                referenceNodeType,
                buildReference(CellRange.fromReferences(piece, piece), self.host, None),
            )
            return
        if piece.start is not None and piece.start == piece.end:
            self.emit(referenceNodeType, buildReference(piece, self.host, None))
            return
        self.emit(
            rangeNodeType,
            buildRange(piece, self.host, None, self.text, token.position),
        )

    def emitAddress(self, token: Token) -> None:
        """Emit the reference or the range an address names, from where it sits.

        The addressing error travels out with its own words: it already says that
        `A0` names row zero and that rows count from one, and replacing that with
        a summary would hide the one thing the writer needs to know.
        """
        try:
            extent = CellRange.parse(token.text)
        except ReferenceError as exc:
            raise self.fail(str(exc), token) from exc
        tableId = resolveQualifierIdentity(token, self.tables, self.text)
        # A colon is what tells a range from a reference, rather than the shape it
        # covers: Numbers writes a tract for `A1:A1` and a coordinate for `A1`.
        if ":" in token.text:
            self.emit(
                rangeNodeType,
                buildRange(extent, self.host, tableId, self.text, token.position),
            )
            return
        self.emit(referenceNodeType, buildReference(extent, self.host, tableId))

    def parseCall(self, token: Token) -> None:
        """Parse a call, dispatching the two the format stores as node types."""
        if token.qualifier:
            raise self.fail("A function is not reached through a table.", token)
        name = token.text.upper()
        if name == letName:
            self.parseLet(token)
            return
        if name == lambdaName:
            self.parseLambda(token)
            return
        self.parseFunction(token)

    def parseArgument(self, thunked: bool) -> None:
        """Parse one argument, bracketing it when the function evaluates it lazily.

        An argument left out is a node of its own rather than an absence, which is
        what each comma of `DURATION(,,,K1,,)` writes.
        """
        if thunked:
            self.emit(beginThunkNodeType)
        token = self.peek()
        if token.kind in ("comma", "close"):
            self.emit(emptyArgumentNodeType)
        else:
            self.parseExpression()
        if thunked:
            self.emit(endThunkNodeType)

    def parseFunction(self, token: Token) -> None:
        """Parse an ordinary call, by index when Numbers accepts the name.

        The argument count is not checked. Numbers takes `ROUND(2.5)`, stores it,
        and shows an error in the cell, so refusing here would decline text
        Numbers itself accepts.
        """
        function = functionsByName.get(token.text) or functionsByName.get(
            token.text.upper()
        )
        # A function Numbers declares and then refuses the name of is stored by its
        # spelling, exactly as Numbers stores it: `21-formula-errors` holds
        # `UNKNOWNFUNC` and `46-formula-rare-functions` holds `ALTITUDE` that way.
        index = (
            None if function is None
            or function.availability is FunctionAvailability.reserved
            else function.index
        )
        thunked = index in thunkingFunctionIndices
        count = self.parseArguments(
            token, lambda position: thunked and position > 0
        )
        if index is None:
            self.emit(
                unknownFunctionNodeType,
                FormulaUnknownCall(name=token.text, argumentCount=count),
            )
            return
        self.emit(functionNodeType, FormulaFunctionCall(index, count))

    def parseArguments(
        self, token: Token, thunked: Callable[[int], bool]
    ) -> int:
        """Parse a bracketed argument list and return how many arguments it held."""
        if self.accept("open") is None:
            raise self.fail("A call opens with a bracket.", token)
        if self.accept("close") is not None:
            return 0
        count = 0
        while True:
            self.parseArgument(thunked(count))
            count += 1
            if self.accept("comma") is not None:
                continue
            if self.accept("close") is not None:
                return count
            raise self.fail("An argument list wants a comma or a bracket.")

    def bind(self, name: str) -> int:
        """Give a name its number, which is what every use of it carries.

        Numbers writes the spelling once and refers to it by a number counting from
        one within the formula, so a name bound twice takes two numbers and the
        later one wins, exactly as an inner scope would.
        """
        self.symbols += 1
        self.bound[name] = self.symbols
        return self.symbols

    def parseLet(self, token: Token) -> None:
        """Parse `LET(name, value, ..., body)`, which the file stores as node types.

        Each value is parsed before its name is bound, so a value naming the name
        it is about to bind reads the outer one, which is what a scope means.
        """
        if self.accept("open") is None:
            raise self.fail("A call opens with a bracket.", token)
        outer = dict(self.bound)
        first = True
        while True:
            name = self.accept("name")
            if name is None:
                raise self.fail("`LET` names a value before it gives it one.")
            if self.accept("comma") is None:
                raise self.fail("`LET` wants a value after the name it binds.")
            self.parseExpression()
            # Bound after its own value is parsed, so a value naming the name it
            # is about to bind reads the outer one.
            self.emit(
                letBindNodeType,
                FormulaBinding(
                    name=name.text,
                    symbol=self.bind(name.text),
                    continuation=not first,
                ),
            )
            first = False
            if self.accept("comma") is None:
                raise self.fail("`LET` wants a body after the values it binds.")
            # A name where the body belongs is another pair, since `LET` takes as
            # many as it is given and only the last argument is the body.
            if self.peek().kind == "name" and self.tokens[
                self.position + 1
            ].kind == "comma":
                continue
            break
        self.parseExpression()
        if self.accept("close") is None:
            raise self.fail("`LET` is opened and never closed.", token)
        self.emit(endScopeNodeType)
        self.bound = outer

    def parseLambda(self, token: Token) -> None:
        """Parse `LAMBDA(name, ..., body)`, whose parameters precede its body."""
        if self.accept("open") is None:
            raise self.fail("A call opens with a bracket.", token)
        outer = dict(self.bound)
        names: list[str] = []
        firstSymbol = 0
        while self.peek().kind == "name" and self.tokens[
            self.position + 1
        ].kind == "comma":
            parameter = self.take().text
            self.take()
            symbol = self.bind(parameter)
            firstSymbol = firstSymbol or symbol
            names.append(parameter)
        self.emit(beginLambdaThunkNodeType)
        if self.peek().kind == "close":
            # A lambda with nothing in it is what `LAMBDA()` writes, and Numbers
            # accepts the text and marks the cell as an error.
            self.emit(emptyArgumentNodeType)
        else:
            self.parseExpression()
        if self.accept("close") is None:
            raise self.fail("`LAMBDA` is opened and never closed.", token)
        self.emit(endLambdaThunkNodeType)
        self.emit(
            lambdaNodeType,
            FormulaLambda(names=tuple(names), firstSymbol=firstSymbol),
        )
        self.bound = outer


def parseFormula(
    text: str,
    host: CellReferenceLike,
    *,
    tables: Mapping[str, str] | None = None,
    pieces: Mapping[str, CellRange | CellReference] | None = None,
) -> Formula:
    """Return the formula a written expression describes, as the nodes it stores.

    `host` is the cell that will hold it, because an unlocked reference is an
    offset from there. `tables` maps a name to an identity, from
    `Sheet.tableIdentities`, and `pieces` supplies an address by name for a
    `{placeholder}` in the text.
    """
    body = text.strip()
    if body.startswith(formulaMarker):
        body = body[len(formulaMarker):]
    return Parser(
        text=body,
        tokens=tokenize(body, tuple(tables or ())),
        host=toCellReference(host).address,
        tables=tables or {},
        pieces=pieces or {},
    ).parse()


__all__ = ["parseFormula"]

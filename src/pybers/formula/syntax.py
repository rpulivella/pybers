#!/usr/bin/env python3
"""\
The vocabulary both directions of formula text share: operators, and the tokens.

Split from the two halves that use it so that neither can hold an operator table
of its own. A parser and a renderer disagreeing about precedence would put out a
document whose text reads correctly and whose tree says something else.

**The operator table comes from Numbers' own node types**, the ASTNodeType enum
of `TSCE.ASTNodeArrayArchive`, which declares each of the fifteen. Deriving it
that way makes an operator this library does not know a node type Apple did not
declare, and the test asserting the two agree fails the day a release adds one.
Starting instead from a spreadsheet grammar and correcting toward Numbers is what
left numbers-parser, which took openpyxl's Excel tokenizer, with a precedence
table holding no comparison at all: one less-than worked and a comparison after
arithmetic raised.

**A reference is an offset from the cell holding the formula**, which is why every
conversion here takes that cell. Passing the wrong one is not an error, it is a
wrong answer.

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

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pybers.addressing.ranges import CellRange
from pybers.addressing.reference import CellReference, tableNameSeparator
from pybers.formula.nodes import (
    Coordinate,
    FormulaError,
    FormulaRange,
    FormulaReference,
    Span,
    additionNodeType,
    appendWhitespaceNodeType,
    beginLambdaThunkNodeType,
    beginThunkNodeType,
    concatenationNodeType,
    divisionNodeType,
    endLambdaThunkNodeType,
    endThunkNodeType,
    equalToNodeType,
    greaterThanNodeType,
    greaterThanOrEqualNodeType,
    lessThanNodeType,
    lessThanOrEqualNodeType,
    multiplicationNodeType,
    negationNodeType,
    notEqualToNodeType,
    percentNodeType,
    plusSignNodeType,
    powerNodeType,
    prependWhitespaceNodeType,
    subtractionNodeType,
)

# The equals sign Numbers shows in front of a formula and never stores. Rendered
# because that is what a person reads in the formula bar, and optional on the way
# in because that is what a person types.
formulaMarker: str = "="

argumentSeparator: str = ","

# What Numbers displays for a reference whose cell no longer exists. The archive
# records the same thing as coordinates pointing nowhere, so this spelling is the
# text side of a fact the file states structurally.
brokenReferenceText: str = "#REF!"

# The names the format stores as node types rather than as an indexed call.
letName: str = "LET"
lambdaName: str = "LAMBDA"

# Every operator Numbers declares, by the text that writes it. Derived from the
# node types rather than from a grammar, so the two cannot disagree.
binaryOperators: dict[str, int] = {
    "<>": notEqualToNodeType,
    "<=": lessThanOrEqualNodeType,
    ">=": greaterThanOrEqualNodeType,
    "=": equalToNodeType,
    "<": lessThanNodeType,
    ">": greaterThanNodeType,
    "&": concatenationNodeType,
    "+": additionNodeType,
    "-": subtractionNodeType,
    "*": multiplicationNodeType,
    "/": divisionNodeType,
    "^": powerNodeType,
}

# Two of the three symbols above are also prefixes, and one is a suffix. Each is
# its own node type, so the parser never has to remember which reading it chose.
unaryOperators: dict[str, int] = {
    "-": negationNodeType,
    "+": plusSignNodeType,
}
percentSymbol: str = "%"

operatorSymbols: dict[int, str] = {
    nodeType: symbol for symbol, nodeType in binaryOperators.items()
}

# Binding strength, higher first, as Numbers evaluates: arithmetic binds tighter
# than concatenation, which binds tighter than comparison, and a prefix minus
# binds tighter than the power it is written in front of.
comparisonPrecedence: int = 1
concatenationPrecedence: int = 2
additivePrecedence: int = 3
multiplicativePrecedence: int = 4
unaryPrecedence: int = 5
powerPrecedence: int = 6
percentPrecedence: int = 7

# What a thing that needs no bracketing scores, so that a comparison against any
# operator's precedence answers "leave it alone".
atomPrecedence: int = 99

# How deeply one expression may nest before parsing refuses. A guard on this
# parser's own stack rather than a measurement of Numbers: the descent spends
# about eight frames per level, so hostile text would otherwise exhaust the
# interpreter and raise `RecursionError` where a formula error belongs.
nestingLimit: int = 64

operatorPrecedence: dict[int, int] = {
    equalToNodeType: comparisonPrecedence,
    notEqualToNodeType: comparisonPrecedence,
    lessThanNodeType: comparisonPrecedence,
    lessThanOrEqualNodeType: comparisonPrecedence,
    greaterThanNodeType: comparisonPrecedence,
    greaterThanOrEqualNodeType: comparisonPrecedence,
    concatenationNodeType: concatenationPrecedence,
    additionNodeType: additivePrecedence,
    subtractionNodeType: additivePrecedence,
    multiplicationNodeType: multiplicativePrecedence,
    divisionNodeType: multiplicativePrecedence,
    negationNodeType: unaryPrecedence,
    plusSignNodeType: unaryPrecedence,
    powerNodeType: powerPrecedence,
    percentNodeType: percentPrecedence,
}

comparisonOperators: tuple[int, ...] = tuple(
    nodeType for nodeType, level in operatorPrecedence.items()
    if level == comparisonPrecedence
)

# Carried through a walk and never rendered. The whitespace pair records where a
# person pressed the space bar, which no reading of the text can recover, and the
# thunk pairs are structure the parser puts back from the function being called.
cosmeticNodeTypes: frozenset[int] = frozenset({
    appendWhitespaceNodeType,
    prependWhitespaceNodeType,
})
thunkNodeTypes: frozenset[int] = frozenset({
    beginThunkNodeType,
    endThunkNodeType,
    beginLambdaThunkNodeType,
    endLambdaThunkNodeType,
})

# One endpoint of an address: a cell, a whole column, or a whole row, each free to
# lock either axis. The three are written out rather than folded into optional
# groups, because `A` and `1` have to be told apart by which one matched.
endpointExpression: str = r"\$?[A-Za-z]+\$?[0-9]+|\$?[A-Za-z]+|\$?[0-9]+"

addressPattern: re.Pattern[str] = re.compile(
    rf"(?:{endpointExpression})(?::(?!:)(?:{endpointExpression}))?"
)

# A table name in front of an address, `Table 2::A1`, qualified further as
# `Sheet 2::Table 1::A1` when a bare table name would name two tables. Names carry
# spaces, so this stops at the punctuation a formula cannot put inside one.
qualifierPattern: re.Pattern[str] = re.compile(r'(?:[^,()"\s][^,()"]*?::)+')

numberPattern: re.Pattern[str] = re.compile(
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
stringPattern: re.Pattern[str] = re.compile(r'"(?:[^"]|"")*"')
placeholderPattern: re.Pattern[str] = re.compile(r"\{([^{}]*)\}")
brokenPattern: re.Pattern[str] = re.compile(r"#REF!", re.IGNORECASE)

# A function name or a bound value, which reaches past what an address may hold:
# `LAMBDA.APPLY` carries a dot and a name a person binds may carry an underscore.
identifierPattern: re.Pattern[str] = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


class FormulaSyntaxError(FormulaError):
    """Text that is not a formula, reported with the offset that failed.

    `position` is an index into the text as given, so a caller can point at the
    character rather than guess which of three `SUM(` the message meant.
    """

    def __init__(self, message: str, text: str, position: int) -> None:
        """Build the error, quoting the text from the offset that failed."""
        self.position = position
        self.text = text
        super().__init__(f"{message} At offset {position}: {text[position:][:24]!r}")


@dataclass(frozen=True, slots=True)
class Token:
    """One piece of formula text, and where in the text it began.

    `width` is how much of the text this consumed, which is not the length of
    `text` for a placeholder or a quoted literal, and `qualifier` is the
    `Table 2::` an address was reached through.
    """

    kind: str
    text: str
    position: int
    width: int
    qualifier: str = ""


def unquote(text: str) -> str:
    """Return a quoted literal's own text, with each doubled quote read as one."""
    return text[1:-1].replace('""', '"')


def quoted(text: str) -> str:
    """Return a string literal as Numbers writes it, doubling any quote inside."""
    escaped = text.replace('"', '""')
    return f'"{escaped}"'


def tokenize(text: str, tables: Sequence[str] = ()) -> list[Token]:
    """Return the tokens of one formula, each carrying the offset it began at.

    Addresses are recognized here rather than in the parser, because a qualified
    one carries spaces and a table name cannot be found by looking at one
    character. `tables` is every name this document answers to, matched literally
    so that a table called `Sales (EU)` or `2026` is read as its own name rather
    than as a bracket or a number. What is left ambiguous is deliberate: bare
    letters are a `name`, and only the parser knows whether `A` is a column or a
    value `LET` bound.
    """
    # Longest first, so `Sheet 2::Table 1` is taken whole rather than as a table
    # called `Sheet 2` that happens to share the prefix.
    known = sorted(tables, key=len, reverse=True)
    tokens: list[Token] = []
    position = 0
    while position < len(text):
        character = text[position]
        if character.isspace():
            position += 1
            continue
        if character == '"':
            match = stringPattern.match(text, position)
            if match is None:
                raise FormulaSyntaxError(
                    "A string literal is opened and never closed.", text, position
                )
            tokens.append(
                Token("string", match.group(), position, len(match.group()))
            )
            position = match.end()
            continue
        if character in "({" or character.isalnum() or character in "$.#":
            token = readValueToken(text, position, known)
            if token is not None:
                tokens.append(token)
                position += token.width
                continue
        if character in "()":
            tokens.append(
                Token(
                    "open" if character == "(" else "close", character, position, 1
                )
            )
            position += 1
            continue
        if character == argumentSeparator:
            tokens.append(Token("comma", character, position, 1))
            position += 1
            continue
        if character == percentSymbol:
            tokens.append(Token("operator", percentSymbol, position, 1))
            position += 1
            continue
        symbol = next(
            (
                candidate for candidate in binaryOperators
                if text.startswith(candidate, position)
            ),
            None,
        )
        if symbol is not None:
            tokens.append(Token("operator", symbol, position, len(symbol)))
            position += len(symbol)
            continue
        raise FormulaSyntaxError(
            "This is not part of a formula.", text, position
        )
    tokens.append(Token("end", "", len(text), 0))
    return tokens


def readQualifier(text: str, position: int, known: Sequence[str]) -> str:
    """Return the `Table 2::` prefix at this offset, matching known names first.

    A name is matched literally when the document supplies one, which is the only
    way to read `Sales (EU)::A1` or `2026::A1`: no rule over characters can say
    where a name Numbers permits ends. The pattern is the fallback, so a caller
    with no names still parses the ordinary spellings and still gets told which
    table it named.
    """
    for name in known:
        if text.startswith(name + tableNameSeparator, position):
            return name + tableNameSeparator
    match = qualifierPattern.match(text, position)
    return "" if match is None else match.group()


def readValueToken(
    text: str, position: int, known: Sequence[str] = ()
) -> Token | None:
    """Return the number, address, name or placeholder starting here, or None.

    None rather than an error, so the caller can go on to try the operators. The
    order matters once: a qualifier is looked for before a number or an address,
    since `2026::A1` begins with digits and `Table 2::A1` with a column label.
    """
    prefix = readQualifier(text, position, known)
    if prefix:
        start = position + len(prefix)
        address = addressPattern.match(text, start)
        if address is None:
            return None
        return Token(
            "address", address.group(), position,
            len(prefix) + len(address.group()), prefix,
        )
    placeholder = placeholderPattern.match(text, position)
    if placeholder is not None:
        return Token(
            "placeholder", placeholder.group(1), position, len(placeholder.group())
        )
    broken = brokenPattern.match(text, position)
    if broken is not None:
        return Token("broken", broken.group(), position, len(broken.group()))
    number = numberPattern.match(text, position)
    if number is not None:
        return Token("number", number.group(), position, len(number.group()))
    address = addressPattern.match(text, position)
    word = identifierPattern.match(text, position)
    if address is None and word is None:
        return None
    # A word reaching further than an address is one: `LAMBDA.APPLY` and `my_rate`
    # both begin with something that is a column label on its own.
    if word is not None and (address is None or len(word.group()) > len(
        address.group()
    )):
        return Token("name", word.group(), position, len(word.group()))
    if address is None:
        return None
    body = address.group()
    # Bare letters are as much a function name or a bound value as a column, and
    # only the parser knows which, so the distinction is left to it.
    kind = "name" if body.isalpha() else "address"
    return Token(kind, body, position, len(body))


def qualifierIdentity(
    token: Token, tables: Mapping[str, str], text: str
) -> str | None:
    """Return the identity a `Table 2::` prefix names, or None when there is none.

    A table is named in a formula by identity and never by name, so a name this
    document does not carry is refused here rather than written as a reference
    into nothing.
    """
    if not token.qualifier:
        return None
    name = token.qualifier[: -len(tableNameSeparator)]
    identity = tables.get(name)
    if identity is None:
        offered = ", ".join(sorted(repr(key) for key in tables)) or "nothing"
        raise FormulaSyntaxError(
            f"{name!r} is not a table this document carries. A formula names a "
            f"table by identity, so a name it does not know cannot be written. "
            f"Known: {offered}.",
            text,
            token.position,
        )
    return identity


def coordinateFor(line: int, absolute: bool, host: int) -> Coordinate:
    """Return one axis of a reference, as an offset unless it was written locked."""
    return Coordinate(
        line if absolute else line - host, absolute=absolute
    )


def spanFor(
    begin: int, end: int, absolute: bool, host: int
) -> Span:
    """Return one axis of a range, with the end omitted when it spans one line.

    Absence is how the file writes a span of one, so repeating the beginning would
    make a range this library wrote differ from the same range Numbers wrote.
    """
    first = begin if absolute else begin - host
    last = end if absolute else end - host
    return Span(begin=first, end=None if last == first else last, absolute=absolute)


def referenceFor(
    extent: CellRange, host: CellReference, tableId: str | None
) -> FormulaReference:
    """Return the single-cell reference an address names, from the cell holding it.

    An axis the address left out stays out, which is how `SUM(A)` stores a column
    and no row at all.
    """
    column = (
        None if extent.startCol is None
        else coordinateFor(extent.startCol, extent.startColAbsolute, host.col)
    )
    row = (
        None if extent.startRow is None
        else coordinateFor(extent.startRow, extent.startRowAbsolute, host.row)
    )
    return FormulaReference(column=column, row=row, tableId=tableId)


def rangeFor(
    extent: CellRange, host: CellReference, tableId: str | None, text: str,
    position: int,
) -> FormulaRange:
    """Return the range an address names, refusing one locked at a single end.

    The file keeps an axis in either its relative field or its absolute one and
    has no third place to say that one end of it is fixed, so `$A1:B1` is a thing
    this format cannot store rather than a thing this library declines to.
    """
    for axis, first, last in (
        ("row", extent.startRowAbsolute, extent.endRowAbsolute),
        ("column", extent.startColAbsolute, extent.endColAbsolute),
    ):
        if first != last:
            raise FormulaSyntaxError(
                f"This range locks one end of its {axis} and not the other, and "
                "the file keeps a whole axis in either its relative field or its "
                "absolute one. Lock both ends or neither.",
                text,
                position,
            )
    columns = (
        None if extent.startCol is None or extent.endCol is None
        else spanFor(
            extent.startCol, extent.endCol, extent.startColAbsolute, host.col
        )
    )
    rows = (
        None if extent.startRow is None or extent.endRow is None
        else spanFor(
            extent.startRow, extent.endRow, extent.startRowAbsolute, host.row
        )
    )
    return FormulaRange(columns=columns, rows=rows, tableId=tableId)


__all__ = ["FormulaSyntaxError", "Token", "tokenize"]

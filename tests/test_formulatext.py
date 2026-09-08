#!/usr/bin/env python3
"""\
A formula written as text becomes the nodes the file stores, and reads back.

The corpus test is the one that means anything. Every other assertion here checks
pybers against pybers, which can agree with itself while both halves are wrong;
rendering every formula in a real document and parsing it back starts from an AST
that came out of Numbers rather than out of this library.

Node arrays are asserted as `(nodeType, content)` pairs, because `FormulaNode`
excludes its archive bytes from equality and a parsed node has none to carry.

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

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

import pybers
from pybers import (
    CellRange,
    CellReference,
    Formula,
    FormulaFunctionCall,
    FormulaSyntaxError,
    FormulaUnknownCall,
    parseFormula,
    renderFormula,
)
from pybers._generated import TSCEArchives_pb2 as tsce
from pybers._persistence import readPackage
from pybers._persistence.types import archiveTypeId
from pybers.model import formulasyntax
from pybers.model.formula import (
    additionNodeType,
    appendWhitespaceNodeType,
    beginThunkNodeType,
    endThunkNodeType,
    functionNodeType,
    greaterThanNodeType,
    numberNodeType,
    prependWhitespaceNodeType,
    rangeNodeType,
    referenceNodeType,
    thunkingFunctionIndices,
    tokenNodeType,
)

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

# TST.TableDataList, so a golden can be compared at its pooled lists rather than
# through the model, which would agree with itself while both halves were wrong.
dataListTypeId: int = 6005

# The three formulas in the corpus carrying node type 23, whose placement rule is
# not established. Their text round trips and their node array does not, which is
# named here so a fourth appearing is a failure rather than a silent widening.
# See findings-08-formula-text.md.
textOnlyRoundTrip: frozenset[tuple[str, str]] = frozenset({
    ("15-number-duration-formats", "L1"),
    ("15-number-duration-formats", "M1"),
    ("46-formula-rare-functions", "B12"),
})


def fixturePath(name: str) -> Path:
    """Return a fixture path, skipping when it has not been made yet."""
    path = fixtureDirectory / f"{name}.numbers"
    if not path.is_file():
        pytest.skip(f"Fixture {path.name} is not present.")
    return path


def dataListBytes(path: Path) -> dict[int, bytes]:
    """Return every pooled data list in a package, keyed by archive identifier."""
    package = readPackage(path)
    return {
        archive.identifier: b"".join(message.data for message in archive.messages)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        if archiveTypeId(archive) == dataListTypeId
    }


def firstTable(name: str) -> pybers.Table:
    """Return the first table of a fixture, which is where these formulas live."""
    return pybers.open(fixturePath(name)).sheets[0].tables[0]


def shape(formula: Formula) -> list[tuple[int, object]]:
    """Return a formula as the pairs that carry its meaning, dropping its bytes."""
    return [(node.nodeType, node.content) for node in formula]


def typed(formula: Formula) -> list[tuple[int, object]]:
    """Return the same, without the nodes recording whitespace a person typed.

    Types 32 and 33 carry where the space bar was pressed, which no reading of the
    text recovers and which retyping the formula in Numbers drops as well. See
    findings-08-formula-text.md.
    """
    return [
        pair for pair in shape(formula)
        if pair[0] not in (appendWhitespaceNodeType, prependWhitespaceNodeType)
    ]


def formulasInCorpus() -> list[tuple[str, str, Formula, CellReference, dict[str, str]]]:
    """Return every formula in every fixture, with what rendering one needs."""
    found = []
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        document = pybers.open(path)
        names = document.tableIdentities
        for sheet in document.sheets:
            for table in sheet.tables:
                for reference, cell in table.cells.items():
                    if cell.formula is not None:
                        found.append(
                            (path.stem, str(reference), cell.formula,
                             reference, names)
                        )
    return found


# ── AC 1: text becomes the AST it describes ──────────────────────────────────


def testTextBecomesTheNodesTheFileStores() -> None:
    """`=1+1` parses to the three nodes `18-formula-literals` holds for it.

    Compared against a fixture Numbers wrote rather than against an array written
    here, so this asserts what the format does and not what the parser prefers.
    """
    stored = firstTable("18-formula-literals").cell("A1").formula
    assert stored is not None
    assert shape(parseFormula("=1+1", "A1")) == typed(stored)


def testASumOfLiteralsParsesToTheIndexedCallNumbersWrote() -> None:
    """`=SUM(1,2,3)` carries SUM's own index and its argument count."""
    stored = firstTable("18-formula-literals").cell("C1").formula
    assert stored is not None
    parsed = parseFormula("=SUM(1,2,3)", "C1")
    assert shape(parsed) == typed(stored)
    assert parsed.nodes[-1].content == FormulaFunctionCall(index=168, argumentCount=3)


def testTheLeadingEqualsIsOptionalOnTheWayIn() -> None:
    """A person types the equals sign or does not, and both mean one formula."""
    assert shape(parseFormula("=1+1", "A1")) == shape(parseFormula("1+1", "A1"))


def testAssigningFormulaTextStoresTheFormulaAgainstThatCell() -> None:
    """`cell.formulaText = ...` parses against the cell, so no host can be wrong."""
    table = firstTable("18-formula-literals")
    table.cell("A2").formulaText = "=SUM(1,2,3)"
    stored = table.cell("A2").formula
    assert stored is not None
    assert shape(stored) == shape(table.cell("C1").formula)


# ── AC 2: a stored formula renders to what Numbers displays ──────────────────


def testAStoredFormulaRendersAsTheTextItWasTypedFrom() -> None:
    """Row 11 of `20-formula-shapes`, against what row 12 says was typed into it.

    The strongest assertion in this file that does not need Numbers open. Each
    label was written by the person who typed the formula beside it, so this
    compares the rendering against a human's own record rather than against a
    string written here to match what the renderer already does.
    """
    table = firstTable("20-formula-shapes")
    for column in "ABCDEF":
        label = table.cell(f"{column}12").value
        assert isinstance(label, str)
        typedText = label.split(":", 1)[1].strip().lstrip("=")
        rendered = table.cell(f"{column}11").formulaText
        assert rendered == f"={typedText}", column


def testACellWithoutAFormulaRendersAsNothingRatherThanEmptyText() -> None:
    """None and the empty string are different answers, and only one is honest."""
    assert firstTable("18-formula-literals").cell("A2").formulaText is None


def testOneSharedArchiveRendersDifferentlyInEachCellHoldingIt() -> None:
    """`19-formula-dragged` shares one archive at refcount 2, and it must.

    A relative reference is an offset from whichever cell holds the formula, so
    rendering without a host would have to invent one and would be wrong in every
    cell but that one.
    """
    table = firstTable("19-formula-dragged")
    assert table.cell("E2").formula == table.cell("E3").formula
    assert table.cell("E2").formulaText == "=SUM(B1:D1)"
    assert table.cell("E3").formulaText == "=SUM(B2:D2)"


# ── AC 3: the two are inverses over a real corpus ────────────────────────────


def testEveryFormulaInTheCorpusRendersAndParsesBackToItsOwnNodes() -> None:
    """Render then parse every formula in every fixture, and compare the nodes.

    The anchor for everything else here: each AST came out of Numbers, so the two
    halves cannot agree with each other while both are wrong. The three exceptions
    are named rather than skipped, so a fourth is a failure.
    """
    checked = 0
    exceptions = set()
    for name, address, formula, host, names in formulasInCorpus():
        text = renderFormula(formula, host, tables=names)
        again = parseFormula(text, host, tables=names)
        checked += 1
        if shape(again) != typed(formula):
            exceptions.add((name, address))
    assert checked > 70, "the corpus carries the formulas this depends on"
    assert exceptions == set(textOnlyRoundTrip)


def testEveryFormulaInTheCorpusRendersToTextThatSurvivesReparsing() -> None:
    """The property with no exceptions: the text is stable, all 77 of them.

    Weaker than node equality and true where that is not, which is what a caller
    printing a formula and writing it back actually depends on.
    """
    for name, address, formula, host, names in formulasInCorpus():
        text = renderFormula(formula, host, tables=names)
        again = renderFormula(
            parseFormula(text, host, tables=names), host, tables=names
        )
        assert again == text, f"{name} {address}"


def testTheOperatorTableIsTheOneNumbersDeclares() -> None:
    """Every operator node type in the schema is one this library writes.

    Derived from `ASTNodeType` rather than from a spreadsheet grammar, so a
    release adding an operator fails here instead of parsing it as something
    else. See findings-08-formula-text.md.
    """
    declared = {
        value.name: value.number
        for value in tsce.ASTNodeArrayArchive.ASTNodeArchive.DESCRIPTOR
        .fields_by_name["AST_node_type"].enum_type.values
    }
    expected = {
        "ADDITION_NODE", "SUBTRACTION_NODE", "MULTIPLICATION_NODE",
        "DIVISION_NODE", "POWER_NODE", "CONCATENATION_NODE",
        "GREATER_THAN_NODE", "GREATER_THAN_OR_EQUAL_TO_NODE", "LESS_THAN_NODE",
        "LESS_THAN_OR_EQUAL_TO_NODE", "EQUAL_TO_NODE", "NOT_EQUAL_TO_NODE",
        "NEGATION_NODE", "PLUS_SIGN_NODE", "PERCENT_NODE",
    }
    assert expected <= set(declared), "Numbers renamed or dropped an operator"
    written = set(formulasyntax.operatorPrecedence)
    assert written == {declared[name] for name in expected}


# ── AC 4: precedence, brackets and nesting ───────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("=1+2*3", "1 2 3 * +"),
        ("=(1+2)*3", "1 2 + 3 *"),
        ("=1-2-3", "1 2 - 3 -"),
        ("=1-(2-3)", "1 2 3 - -"),
        ("=2^3^2", "2 3 2 ^ ^"),
        ("=-2^2", "2 2 ^ neg"),
        ("=1&2=3", "1 2 & 3 ="),
        ("=1<2", "1 2 <"),
    ],
)
def testPrecedenceFollowsNumbersRatherThanTheOrderWritten(
    text: str, expected: str
) -> None:
    """Arithmetic binds tighter than comparison, and brackets override both.

    Written as the postfix the file holds, since that IS the tree: `1+2*3` and
    `(1+2)*3` differ in node order and in nothing else.
    """
    symbols = {1: "+", 2: "-", 3: "*", 4: "/", 5: "^", 6: "&", 11: "=", 9: "<",
               13: "neg"}
    produced = " ".join(
        symbols.get(node.nodeType, str(node.content))
        for node in parseFormula(text, "A1")
    )
    assert produced == expected


def testACallNestedInsideACallIsStoredAsOneFlatArray() -> None:
    """`IF(SUM(A1:A5)>10,...)` against the fixture Numbers wrote it in."""
    stored = firstTable("20-formula-shapes").cell("D11").formula
    assert stored is not None
    parsed = parseFormula('=IF(SUM(A1:A5)>10,"big","small")', "D11")
    assert shape(parsed) == typed(stored)


def testALazyArgumentIsBracketedAndAConditionIsNot() -> None:
    """The four functions Numbers thunks, and only the arguments after the first.

    Read from `functionIndexUsesThunks:` rather than guessed, and measured for
    `IF` against `18-formula-literals`. See findings-08-formula-text.md.
    """
    parsed = parseFormula("=IF(1>0,1,2)", "F1")
    types = [node.nodeType for node in parsed]
    assert types.count(beginThunkNodeType) == 2
    assert types.count(endThunkNodeType) == 2
    # The condition is bare, so the first bracket opens after the comparison.
    assert types.index(beginThunkNodeType) > types.index(greaterThanNodeType)
    assert 62 in thunkingFunctionIndices


def testAnUnthunkedFunctionBracketsNothing() -> None:
    """Guard the guard: brackets everywhere would pass the assertion above."""
    types = [node.nodeType for node in parseFormula("=SUM(1,2,3)", "A1")]
    assert beginThunkNodeType not in types


# ── AC 5: anchoring survives the text, per axis ──────────────────────────────


@pytest.mark.parametrize(
    ("text", "column", "row"),
    [
        ("=$B$1", (True, 2), (True, 1)),
        ("=$B1", (True, 2), (False, -1)),
        ("=B$1", (False, -5), (True, 1)),
        ("=B1", (False, -5), (False, -1)),
    ],
)
def testAnchoringIsPerAxisAndSurvivesBeingWritten(
    text: str, column: tuple[bool, int], row: tuple[bool, int]
) -> None:
    """Each of the four spellings, from a host at G2, locked as it was written.

    An absolute axis is a line counted from one and a relative one is a signed
    offset, so the two are compared as pairs rather than as numbers: reading one
    as the other names a real cell and raises nothing.
    """
    reference = parseFormula(text, "G2").references[0]
    assert reference.column is not None and reference.row is not None
    assert (reference.column.absolute, reference.column.value) == column
    assert (reference.row.absolute, reference.row.value) == row


def testMixedAnchoringMatchesWhatNumbersStoredForTheSameText() -> None:
    """`$B1+C$1` at G2, against `19-formula-dragged`, which holds exactly that."""
    stored = firstTable("19-formula-dragged").cell("G2").formula
    assert stored is not None
    assert shape(parseFormula("=$B1+C$1", "G2")) == typed(stored)


def testALockedRangeLocksBothEndsOrNeither() -> None:
    """The file keeps a whole axis in one field variant, so half is unstorable.

    Refused rather than written with the lock quietly dropped, which would open in
    Numbers as a range that moves when it was written not to.
    """
    with pytest.raises(FormulaSyntaxError, match="locks one end"):
        parseFormula("=SUM($A1:B1)", "A5")


# ── AC 6: ranges, whole columns and other tables ─────────────────────────────


def testARangeParsesToTheTractNodeTheArchiveUses() -> None:
    """`SUM(A1:A10)` is a colon tract, not two coordinates."""
    stored = firstTable("20-formula-shapes").cell("A11").formula
    assert stored is not None
    parsed = parseFormula("=SUM(A1:A10)", "A11")
    assert shape(parsed) == typed(stored)
    assert parsed.nodes[0].nodeType == rangeNodeType


def testAWholeColumnParsesToACoordinateWithNoRowAtAll() -> None:
    """`SUM(A)` stores a column and no row, which is how unboundedness is written."""
    stored = firstTable("20-formula-shapes").cell("F11").formula
    assert stored is not None
    parsed = parseFormula("=SUM(A)", "F11")
    assert shape(parsed) == typed(stored)
    assert parsed.nodes[0].nodeType == referenceNodeType
    assert parsed.references[0].row is None


def testAReferenceIntoAnotherTableCarriesThatTablesIdentity() -> None:
    """`Table 2::A1` names a table by identity, which the document supplies.

    Both directions, against the fixture holding a cross-table and a cross-sheet
    reference, the second of which has to qualify because two tables are named
    `Table 1`.
    """
    document = pybers.open(fixturePath("20-formula-shapes"))
    table = document.sheets[0].tables[0]
    assert table.cell("G11").formulaText == "=Table 2::A1"
    assert table.cell("H11").formulaText == "=Sheet 2::Table 1::A1"

    parsed = parseFormula("=Table 2::A1", "G11", tables=document.tableIdentities)
    assert shape(parsed) == typed(table.cell("G11").formula)
    assert parsed.references[0].crossTable


def testACellReachesAnotherTableWithoutBeingHandedTheNames() -> None:
    """The ergonomic half of the above: a cell knows the document it sits in."""
    table = pybers.open(fixturePath("20-formula-shapes")).sheets[0].tables[0]
    table.cell("A1").formulaText = "=Table 2::A1*2"
    assert table.cell("A1").formulaText == "=Table 2::A1*2"
    assert table.cell("A1").formula is not None
    assert table.cell("A1").formula.references[0].crossTable


@pytest.mark.parametrize(
    "name",
    ["Sales", "Q1 2026", "Sales-EU", "Ventas 2026", "\u58f2\u4e0a", "Table.2",
     "Sales (EU)", "A1", "Rate: gross", "Sales, net", '2026', "SUM"],
)
def testATableNamedAnythingNumbersAllowsRoundTripsThroughTheText(
    name: str,
) -> None:
    """A custom name, including one holding a bracket, a comma or only digits.

    Matched against the names the document carries rather than against a rule over
    characters, which is the only way to know where a name Numbers permits ends.
    Every fixture is named `Table 1` or `Table 2`, so nothing else here would
    notice a parser that could read only those.
    """
    document = pybers.open(fixturePath("20-formula-shapes"))
    document.sheet("Sheet 1").table("Table 2").name = name
    source = document.sheet("Sheet 1").table("Table 1")

    rendered = source.cell("G11").formulaText
    assert rendered == f"={name}::A1"
    again = parseFormula("=" + f"{name}::A1", "G11",
                         tables=document.tableIdentities)
    assert shape(again) == typed(source.cell("G11").formula)


def testATableNameWithOuterSpacesIsRefusedRatherThanMisread() -> None:
    """The one spelling this cannot read, refused loudly and named as such.

    A formula is tokenized left to right and whitespace between tokens is skipped,
    so a name whose own first character is a space cannot be told from the gap in
    front of it. Numbers has never been seen to keep one.
    """
    document = pybers.open(fixturePath("20-formula-shapes"))
    document.sheet("Sheet 1").table("Table 2").name = "  padded  "
    with pytest.raises(FormulaSyntaxError, match="not a table this document"):
        parseFormula("=  padded  ::A1", "G11", tables=document.tableIdentities)


def testATableNameTheDocumentDoesNotCarryIsRefused() -> None:
    """A name naming no table would otherwise be written as a reference to nothing."""
    document = pybers.open(fixturePath("20-formula-shapes"))
    with pytest.raises(FormulaSyntaxError, match="not a table this document"):
        parseFormula(
            "=Ledger::A1", "A1", tables=document.tableIdentities
        )


# ── AC 7: what is not a formula is refused, with the position ────────────────


@pytest.mark.parametrize(
    ("text", "position"),
    [
        ("=1+", 2),
        ("=SUM(1,2", 7),
        ("=(1+2", 0),
        ('="unterminated', 0),
        ("=1 $ 2", 2),
        ("=", 0),
    ],
)
def testTextThatIsNotAFormulaIsRefusedWithTheOffsetThatFailed(
    text: str, position: int
) -> None:
    """Refused rather than stored as something that opens wrong in Numbers.

    The offset is into the text without its equals sign, which is what a caller
    would point at, and is asserted so the message cannot decay into "invalid".
    """
    with pytest.raises(FormulaSyntaxError) as raised:
        parseFormula(text, "A1")
    assert raised.value.position == position


def testAnAddressBelowTheOriginRefusesInTheAddressingLayersOwnWords() -> None:
    """`A0` says it names row zero, rather than that it addresses nothing.

    The reason travels out of `CellRange.parse` intact. Row zero and column zero
    are the two mistakes a zero-based instinct makes, and the message has to name
    which one it was rather than summarize both away.
    """
    for text, offset in (("=A0", 0), ("=SUM(A0:A5)", 4), ("=A1+B0", 3)):
        with pytest.raises(FormulaSyntaxError, match="rows count from 1") as raised:
            parseFormula(text, "B2")
        assert raised.value.position == offset


def testTextNestedDeeperThanTheParserGoesIsRefusedRatherThanCrashing() -> None:
    """Hostile text fails as a formula error rather than as a `RecursionError`.

    Descent spends about eight interpreter frames per level, so text nested a few
    hundred deep exhausts the stack. Sixty levels still parse, which is further
    than a person nests.
    """
    assert len(parseFormula("=" + "(" * 60 + "1" + ")" * 60, "A1")) == 1
    with pytest.raises(FormulaSyntaxError, match="levels deep"):
        parseFormula("=" + "(" * 400 + "1" + ")" * 400, "A1")


def testARefusedFormulaLeavesTheCellExactlyAsItWas() -> None:
    """A failed parse writes nothing, so a cell keeps whatever it held."""
    cell = firstTable("18-formula-literals").cell("A1")
    before = cell.formula
    with pytest.raises(FormulaSyntaxError):
        cell.formulaText = "=SUM(1,"
    assert cell.formula is before


# ── AC 8: an address passed rather than interpolated ─────────────────────────


def testAnAddressMayBePassedAsAPieceRatherThanSplicedIntoTheText() -> None:
    """A range this library validated stays validated on its way into a formula."""
    table = firstTable("20-formula-shapes")
    table.cell("A1").formulaSet(
        "=SUM({sales})", sales=CellRange.parse("A1:A10")
    )
    assert table.cell("A1").formulaText == "=SUM(A1:A10)"


def testASingleCellPieceBecomesACoordinateRatherThanARange() -> None:
    """A `CellReference` names one cell, and the file has a node kind for that."""
    formula = parseFormula(
        "={anchor}*2", "B2", pieces={"anchor": CellReference.parse("$A$1")}
    )
    assert formula.nodes[0].nodeType == referenceNodeType
    assert renderFormula(formula, "B2") == "=$A$1*2"


def testAPlaceholderWithNoAddressGivenIsRefusedByName() -> None:
    """Naming what was expected, since a silent empty would parse as nonsense."""
    with pytest.raises(FormulaSyntaxError, match="No address was given"):
        parseFormula("=SUM({sales})", "A1")


# ── AC 9: LET and LAMBDA, which are node types rather than calls ─────────────


def testLetRoundTripsThroughTextLikeAnyOtherFormula() -> None:
    """`LET` binds a name to a value and the file stores neither as a call.

    Asserted against `46-formula-rare-functions`, whose `LET` Numbers accepted and
    evaluated to 3.
    """
    stored = firstTable("46-formula-rare-functions").cell("B9").formula
    assert stored is not None
    assert renderFormula(stored, "B9") == "=LET(x,2,x+1)"
    assert shape(parseFormula("=LET(x,2,x+1)", "B9")) == typed(stored)


def testLambdaRoundTripsThroughTextWithItsParametersAheadOfItsBody() -> None:
    """A `LAMBDA` reached through `LAMBDA.APPLY`, both directions."""
    stored = firstTable("46-formula-rare-functions").cell("B13").formula
    assert stored is not None
    text = "=LAMBDA.APPLY(2,LAMBDA(x,x+1))"
    assert renderFormula(stored, "B13") == text
    # The stored formula carries whitespace nodes a person typed, which the text
    # cannot express and retyping in Numbers drops as well.
    assert shape(parseFormula(text, "B13")) == typed(stored)


def testALambdaBindsItsParametersOnlyInsideItself() -> None:
    """A name is a bound value inside the lambda and a column outside it."""
    inside = parseFormula("=LAMBDA(x,x+1)", "A1")
    assert not inside.references, "x names the parameter, not column X"
    outside = parseFormula("=SUM(x)", "A1")
    assert outside.references, "the same name outside names a column"


# ── AC 10: a name Numbers does not accept keeps its spelling ─────────────────


def testAFunctionNumbersDoesNotKnowKeepsItsSpelling() -> None:
    """Stored the way Numbers stores it, so text Numbers takes this takes too."""
    stored = firstTable("21-formula-errors").cell("D1").formula
    assert stored is not None
    parsed = parseFormula("=UNKNOWNFUNC(1)", "D1")
    assert shape(parsed) == typed(stored)
    assert parsed.nodes[-1].content == FormulaUnknownCall("UNKNOWNFUNC", 1)


def testAReservedFunctionIsWrittenBySpellingRatherThanByItsIndex() -> None:
    """Numbers declares an index for `ALTITUDE` and then refuses the name.

    So the index is not what it writes, and writing one would produce a formula
    calling something else. Measured against `46-formula-rare-functions`.
    """
    stored = firstTable("46-formula-rare-functions").cell("B20").formula
    assert stored is not None
    parsed = parseFormula('=ALTITUDE("Denver")', "B20")
    assert shape(parsed) == typed(stored)
    assert parsed.nodes[-1].nodeType != functionNodeType


def testAnArgumentCountNumbersAcceptsIsNotRefusedHere() -> None:
    """`ROUND(2.5)` is stored by Numbers and shown as an error in the cell.

    Refusing it would decline text Numbers itself takes, which is the whole of
    this criterion.
    """
    stored = firstTable("18-formula-literals").cell("D1").formula
    assert stored is not None
    assert shape(parseFormula("=ROUND(2.5)", "D1")) == typed(stored)


def testAnOmittedArgumentIsANodeRatherThanAnAbsence() -> None:
    """Each comma of `DURATION(,,,K1,,)` writes an argument that is not there.

    The two the corpus writes as node type 23 come back as 22, which is the only
    one of the two whose placement is established. The text is what round trips.
    See findings-08-formula-text.md.
    """
    table = firstTable("15-number-duration-formats")
    assert table.cell("L1").formulaText == "=DURATION(,,,K1,,)"
    parsed = parseFormula("=DURATION(,,,K1,,)", "L1")
    assert parsed.nodes[-1].content == FormulaFunctionCall(index=212, argumentCount=6)
    assert tokenNodeType not in [node.nodeType for node in parsed]


# ── The written forms literals take ──────────────────────────────────────────


def testANumberLiteralKeepsItsOwnSpelling() -> None:
    """A decimal is written as it was read, never normalized through a float."""
    formula = parseFormula("=2.50+1E+3", "A1")
    assert [node.content for node in formula][:2] == [
        Decimal("2.50"), Decimal("1E+3")
    ]
    # The trailing zero survives, which routing through a float would not do.
    assert renderFormula(formula, "A1") == "=2.50+1E+3"


def testAQuoteInsideAStringIsDoubledRatherThanEscaped() -> None:
    """Which is how Numbers writes one, and the only spelling it reads back."""
    formula = parseFormula('="say ""yes"""', "A1")
    assert [node.content for node in formula] == ['say "yes"']
    assert renderFormula(formula, "A1") == '="say ""yes"""'


def testABrokenReferenceIsWrittenAndReadAsTheOneNumbersShows() -> None:
    """`#REF!` is coordinates pointing nowhere on purpose, both ways."""
    stored = firstTable("21-formula-errors").cell("C1").formula
    assert stored is not None
    assert renderFormula(stored, "C1") == "=#REF!"
    assert parseFormula("=#REF!", "C1").broken


def testTheNodeArrayIsWhatIsStoredAndTheTextIsNeverWritten() -> None:
    """The text is a constructor. Nothing here reaches the file."""
    formula = parseFormula("=SUM(A1:A10)", "A11")
    assert isinstance(formula, Formula)
    assert all(
        node.nodeType in (rangeNodeType, functionNodeType, numberNodeType,
                          additionNodeType)
        for node in formula
    )

# ── AC 1: the golden, which is the only test Numbers itself confirmed ────────

goldenDirectory: Path = Path(__file__).resolve().parent / "golden"

# The three formulas the golden was authored from, as text, in the order a reader
# of `tests/golden/README.md` will find them described.
authoredFormulas: tuple[tuple[str, str], ...] = (
    ("B1", "=Sheet 1::Table 1::A11*2+1"),
    ("C1", '=IF(SUM(A1:A10)>10,"big","small")'),
    ("D1", '=$A$1&" units"'),
)


def authorFormulas(working: Path) -> None:
    """Write the golden's three formulas into a copy of `20-formula-shapes`."""
    document = pybers.open(working)
    table = document.sheet("Sheet 1").table("Table 2")
    for address, text in authoredFormulas:
        table.cell(address).formulaText = text
    document.save()


def testFormulasAuthoredAsTextMatchTheirGoldenFile(tmp_path: Path) -> None:
    """Three formulas written as text, against output confirmed in Numbers itself.

    Every other test here checks pybers against pybers, which can agree with
    itself while both halves are wrong. See `tests/golden/README.md` for the
    confirmation state of this file.
    """
    golden = goldenDirectory / "20-formula-authored-as-text.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"

    working = Path(shutil.copy(fixturePath("20-formula-shapes"),
                               tmp_path / "20.numbers"))
    authorFormulas(working)
    assert dataListBytes(golden) == dataListBytes(working), (
        "the writer no longer produces the confirmed formula lists"
    )


def testTheAuthoredGoldenHoldsWhatItClaimsTo() -> None:
    """Guard the guard: a golden replaced by an unedited copy would pass silently.

    The cross-table reference is asserted structurally as well, because a written
    formula that lost its table identity still reads back as a formula and points
    at the wrong table.
    """
    golden = goldenDirectory / "20-formula-authored-as-text.numbers"
    if not golden.is_file():
        pytest.skip(f"{golden.name} is not present yet")
    table = pybers.open(golden).sheet("Sheet 1").table("Table 2")
    for address, text in authoredFormulas:
        assert table.cell(address).formulaText == text

    crossTable = table.cell("B1").formula
    assert crossTable is not None
    assert crossTable.references[0].crossTable, "the table identity survived"
    # pybers evaluates nothing, so each cell holds the pending state until Numbers
    # recalculates on open. Confirming that is what the golden exists for.
    assert all(
        table.cell(address).value is None for address, _ in authoredFormulas
    )

#!/usr/bin/env python3
"""\
Names for function indices, checked against fixtures whose formulas are known.

The four pairs asserted here come from documents that carry the formulas in their
own cells, so `SUM` is 168 because a fixture written in Numbers says so, not
because the extractor and this suite agree with each other.

UPDATES
2026-09-04  Written for #44.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"

import dataclasses
import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

import pybers
from pybers import Formula, FormulaFunctionCall, FormulaNode
from pybers._persistence import readPackage
from pybers._persistence.types import archiveTypeId
from pybers.model.formula import functionNodeType
from pybers.model.functions import (
    ArgumentCountError,
    UnknownFunctionError,
    functionFor,
    functionIndexFor,
    functionNamed,
    functionNameFor,
    functionsByIndex,
    functionsByName,
)

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"
repositoryRoot: Path = Path(__file__).resolve().parent.parent

# TSCE.FormulaArchive, the pooled formula list. Named here rather than imported
# because the identifier is read from the archive and is not a generated constant.
formulaListTypeId: int = 6005

# The highest index Apple assigned in the original alphabetical pass, measured
# 2026-09-04 on Numbers 15.3.1. Everything above it was appended later and is
# in release order rather than name order.
originalAlphabeticalCeiling: int = 167


def fixturePath(name: str) -> Path:
    """Return a fixture path, skipping when it has not been made yet."""
    path = fixtureDirectory / f"{name}.numbers"
    if not path.is_file():
        pytest.skip(f"Fixture {path.name} is not present.")
    return path


def firstTable(name: str) -> pybers.Table:
    """Return the first table of a fixture, which is where these formulas live."""
    return pybers.open(fixturePath(name)).sheets[0].tables[0]


def calls(table: pybers.Table) -> list[FormulaFunctionCall]:
    """Return every function call in a table's formulas, in cell iteration order."""
    return [
        node.content
        for cell in table.cells.values()
        if cell.formula is not None
        for node in cell.formula
        if isinstance(node.content, FormulaFunctionCall)
    ]


def dataListBytes(path: Path) -> dict[int, bytes]:
    """Return every pooled data list in a package, keyed by archive identifier."""
    package = readPackage(path)
    return {
        archive.identifier: b"".join(message.data for message in archive.messages)
        for iwaFile in package.iwaFiles
        for archive in iwaFile.archives
        if archiveTypeId(archive) == formulaListTypeId
    }


def extractor() -> ModuleType:
    """Return the extraction script as a module, for its comparison logic.

    `scripts/` carries no `__init__.py` and the file name has a hyphen, so
    `import_module` with a string is the only spelling that works, the same way
    `scripts/pr-preflight-check.py` reaches the standards checker.
    """
    if str(repositoryRoot) not in sys.path:
        sys.path.insert(0, str(repositoryRoot))
    if str(repositoryRoot / "tools") not in sys.path:
        sys.path.insert(0, str(repositoryRoot / "tools"))
    return importlib.import_module("tools.functions-extract")


# ── AC 1: a call reports its name ────────────────────────────────────────────


def testEveryKnownPairMatchesTheFixtureThatEstablishedIt() -> None:
    """The four indices measured from real documents name the right functions."""
    assert functionNameFor(168) == "SUM"
    assert functionNameFor(62) == "IF"
    assert functionNameFor(231) == "SUMIFS"
    assert functionNameFor(126) == "ROUND"


def testFormulaLiteralsFixtureNamesItsCalls() -> None:
    """18 carries SUM, ROUND twice and IF, which is what the map must report."""
    named = sorted(call.name or str(call.index) for call in calls(firstTable(
        "18-formula-literals"
    )))
    assert named == ["IF", "ROUND", "ROUND", "SUM"]


def testFormulaShapesFixtureNamesItsCalls() -> None:
    """20 adds SUMIFS over ranges, so the map covers more than the arithmetic ones."""
    named = sorted(call.name or str(call.index) for call in calls(firstTable(
        "20-formula-shapes"
    )))
    assert named == ["IF", "SUM", "SUM", "SUM", "SUM", "SUMIFS"]


def testNameLookupIsCaseInsensitiveAndTrimmed() -> None:
    """A caller typing a function the way Numbers accepts it gets the same index."""
    assert functionIndexFor("sum") == 168
    assert functionIndexFor("  Sum  ") == 168
    assert functionIndexFor("SUM") == 168


def testDottedFunctionNamesKeepTheirDot() -> None:
    """`REFERENCE.NAME` is one function whose name contains a dot, not two names."""
    assert functionNameFor(functionIndexFor("REFERENCE.NAME")) == "REFERENCE.NAME"


def testTheOriginalIndicesAreInAlphabeticalOrder() -> None:
    """Indices 1 to 167 name their functions alphabetically, ABS first, YEAR last.

    Apple assigned that block in one pass and has appended ever since, so the
    ordering is a property of the map that owes nothing to how it was extracted.
    A misread index inside the block lands out of order, which is what makes this
    a check on the extractor rather than a restatement of it: `COLUMN`, `IF`,
    `PI`, `RAND`, `ROW` and `TODAY` all sit here and all six were read by a code
    shape that carries the index differently from the other 314.
    """
    within = sorted(
        (index, function.name)
        for index, function in functionsByIndex.items()
        if index <= originalAlphabeticalCeiling
    )
    assert [name for _index, name in within] == sorted(
        name for _index, name in within
    )
    assert within[0] == (1, "ABS")
    assert within[-1] == (originalAlphabeticalCeiling, "YEAR")


# ── AC 2: an unknown function survives ───────────────────────────────────────


def testUnknownIndexReportsNoNameRatherThanRaising() -> None:
    """An index outside the map names nothing and is still a usable call."""
    call = FormulaFunctionCall(index=64000, argumentCount=2)
    assert call.name is None
    assert call.index == 64000
    assert functionNameFor(64000) is None


def testUnknownNameRefusesRatherThanInventingAnIndex() -> None:
    """Authoring by a name the map lacks raises, since a guess would call
    something else."""
    with pytest.raises(UnknownFunctionError):
        functionIndexFor("NOTAFUNCTION")


def testUnknownIndexRoundTripsThroughTheFileUnchanged(tmp_path: Path) -> None:
    """A call the map cannot name is written and read back with its index intact."""
    source = shutil.copy(fixturePath("18-formula-literals"), tmp_path / "18.numbers")
    document = pybers.open(source)
    cell = document.sheets[0].tables[0].cell("D1")
    nodes = list(cell.formula.nodes)
    nodes[-1] = dataclasses.replace(
        nodes[-1], content=FormulaFunctionCall(index=64000, argumentCount=1), raw=b""
    )
    cell.formula = Formula(nodes=tuple(nodes))
    document.save()

    after = pybers.open(source).sheets[0].tables[0].cell("D1")
    call = after.formula.nodes[-1].content
    assert isinstance(call, FormulaFunctionCall)
    assert call.index == 64000
    assert call.name is None


# ── AC 3: naming a function changes nothing about what is written ────────────


def testCallByNameEqualsCallByIndex() -> None:
    """`named` is a way of spelling an index, so the two calls are one value."""
    assert FormulaFunctionCall.named("SUM", 2) == FormulaFunctionCall(168, 2)
    assert FormulaFunctionCall.named("IF", 3) == FormulaFunctionCall(62, 3)


def testAuthoringByNameWritesTheSameArchiveAsAuthoringByIndex(
    tmp_path: Path,
) -> None:
    """The same edit made both ways produces byte-identical formula archives."""

    def write(target: Path, call: FormulaFunctionCall) -> dict[int, bytes]:
        source = shutil.copy(fixturePath("18-formula-literals"), target)
        document = pybers.open(source)
        cell = document.sheets[0].tables[0].cell("A1")
        cell.formula = Formula(
            nodes=(
                *cell.formula.nodes[:-1],
                FormulaNode(nodeType=functionNodeType, content=call),
            )
        )
        document.save()
        return dataListBytes(source)

    byIndex = write(tmp_path / "index.numbers", FormulaFunctionCall(168, 2))
    byName = write(tmp_path / "name.numbers", FormulaFunctionCall.named("sum", 2))
    assert byIndex == byName


# ── AC 4: the map ships with the library ─────────────────────────────────────


def testTheMapLivesInsideTheInstalledPackage() -> None:
    """The generated module sits under pybers itself, which is what hatchling ships.

    pyproject declares `packages = ["src/pybers"]`, so anything under the package
    directory is in the wheel. Asserting the file's location is therefore the same
    claim as asserting it installs, without building one.
    """
    from pybers._generated import functions as generated

    packageRoot = Path(pybers.__file__).resolve().parent
    assert Path(generated.__file__).resolve().is_relative_to(packageRoot)


def testTheTableIsPopulatedAndReadOnly() -> None:
    """A shared table handed out mutable would rename a function for every caller."""
    assert len(functionsByIndex) > 300
    with pytest.raises(TypeError):
        functionsByIndex[1] = "NOPE"  # type: ignore[index]


# ── AC 6 and 7: a call reports the counts its function accepts ───────────────


def testACallReportsTheArgumentCountsItsFunctionAccepts() -> None:
    """`HYPERLINK` takes one or two, which a caller learns before writing either."""
    hyperlink = functionNamed("HYPERLINK")
    assert (hyperlink.minimumArguments, hyperlink.maximumArguments) == (1, 2)
    assert hyperlink.accepts(1) and hyperlink.accepts(2)
    assert not hyperlink.accepts(0) and not hyperlink.accepts(3)


def testAFunctionTakingNoArgumentsSaysSo() -> None:
    """`PI` accepts nothing, which a maximum read as a count of declared
    arguments would have reported as two."""
    pi = functionNamed("PI")
    assert (pi.minimumArguments, pi.maximumArguments) == (0, 0)
    assert pi.accepts(0) and not pi.accepts(1)


def testARepeatingGroupMakesTheMaximumAFloor() -> None:
    """`SUM` declares a maximum of two and accepts eight, because it repeats."""
    total = functionNamed("SUM")
    assert total.maximumArguments == 2
    assert total.unbounded
    assert total.accepts(8) and total.accepts(3)
    assert not total.accepts(0)


def testAPairedRepeatingGroupIsStillUnbounded() -> None:
    """`SUMIFS` takes three and then criteria pairs, which is why it has a
    group of two rather than a limit."""
    sumifs = functionNamed("SUMIFS")
    assert sumifs.repeatingGroupSize == 2
    assert sumifs.accepts(3) and sumifs.accepts(101)
    assert not sumifs.accepts(2)


def testAuthoringByNameRefusesACountTheFunctionRejects() -> None:
    """The ergonomic path refuses what Numbers would store as an error cell."""
    with pytest.raises(ArgumentCountError):
        FormulaFunctionCall.named("ROUND", 1)
    with pytest.raises(ArgumentCountError):
        FormulaFunctionCall.named("PI", 1)


def testAuthoringByIndexStillWritesWhateverIsAsked() -> None:
    """The explicit path stays open, so an error cell can be written on purpose.

    `=ROUND(2.5)` is exactly what 18-formula-literals holds, stored by Numbers
    as an error, so refusing to express it would make that document unwritable.
    """
    call = FormulaFunctionCall(index=126, argumentCount=1)
    assert call.name == "ROUND"
    assert call.function is not None and not call.function.accepts(1)


# ── AC 8: no claim contradicts a document ────────────────────────────────────


def testNoValidFormulaInTheCorpusContradictsTheTable() -> None:
    """Every argument count in every fixture is accepted by the function holding it.

    Errored cells are excluded because Numbers itself rejected them, and the
    table agreeing that they are errors is the next test rather than this one.
    """
    offenders: list[str] = []
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        document = pybers.open(path)
        for sheet in document.sheets:
            for table in sheet.tables:
                for cell in table.cells.values():
                    if cell.formula is None or cell.errored:
                        continue
                    for node in cell.formula:
                        call = node.content
                        if not isinstance(call, FormulaFunctionCall):
                            continue
                        function = call.function
                        if function is not None and not function.accepts(
                            call.argumentCount
                        ):
                            offenders.append(
                                f"{path.name} {function.name}"
                                f"({call.argumentCount})"
                            )
    assert offenders == []


def testTheTableAgreesWithNumbersAboutAnErroredCall() -> None:
    """`=ROUND(2.5)` is stored as an error, and the table independently rejects it."""
    table = firstTable("18-formula-literals")
    errored = [
        node.content
        for cell in table.cells.values()
        if cell.formula is not None and cell.errored
        for node in cell.formula
        if isinstance(node.content, FormulaFunctionCall)
    ]
    assert errored, "18-formula-literals carries an errored formula"
    for call in errored:
        function = call.function
        assert function is not None
        assert not function.accepts(call.argumentCount)


# ── AC 9: the functions no authoring method reaches ──────────────────────────


def testFunctionsTheAuthoringMethodsNeverReachedAreNamed() -> None:
    """These 22 came from the class metadata, which the first reading never saw."""
    for name in ("TRUE", "FALSE", "HYPERLINK", "CURRENCY", "BITLSHIFT", "ISOWEEKNUM"):
        function = functionNamed(name)
        assert function.index is not None
        assert functionFor(function.index) == function


# ── AC 11: a name Numbers declares but refuses ───────────────────────────────


def testAReservedFunctionIsNamedRatherThanDropped() -> None:
    """Indices 281 to 284 are declared, spec-less, and refused by Numbers itself.

    46-formula-rare-functions holds all four typed out, and Numbers answers
    "isn't a valid function name" for each, so carrying them lets a document
    calling one read as a name instead of a bare number.
    """
    for name, index in (("LATITUDE", 281), ("LONGITUDE", 282),
                        ("BEARING", 283), ("ALTITUDE", 284)):
        function = functionNamed(name)
        assert function.index == index
        assert function.reserved
        assert functionNameFor(index) == name


def testAReservedFunctionAcceptsNoArgumentCountAtAll() -> None:
    """Reading one names it; authoring one is refused whatever is passed."""
    altitude = functionNamed("ALTITUDE")
    assert not any(altitude.accepts(count) for count in range(0, 6))
    with pytest.raises(ArgumentCountError):
        FormulaFunctionCall.named("ALTITUDE", 1)


def testAnInternalFunctionIsNamedSoASpilledDocumentIsLegible() -> None:
    """`SPILL` is index 337 and fills every cell a formula spills into.

    Measured in 46-formula-rare-functions, where a MAKEARRAY anchored at C15
    leaves `SPILL($C$15)` in the three cells it covers. Dropping the internal
    functions would read every one of those as a bare number.
    """
    spill = functionNamed("SPILL")
    assert spill.index == 337
    assert str(spill.availability) == "internal"
    assert not spill.offered
    assert spill.accepts(1) and not spill.accepts(2)
    assert functionNameFor(337) == "SPILL"


def testAnInternalFunctionIsRefusedByNameAndAllowedByIndex() -> None:
    """The ergonomic path declines; the explicit one stays open."""
    with pytest.raises(ArgumentCountError):
        FormulaFunctionCall.named("SPILL", 1)
    assert FormulaFunctionCall(index=337, argumentCount=1).name == "SPILL"


def testAnOperatorCarriesAFunctionIndexAsWellAsANodeType() -> None:
    """Operators are node types in every formula the corpus holds, and Numbers
    also declares an indexed form for each."""
    multiply = functionNamed("op.Multiply")
    assert multiply.index == 169
    assert not multiply.offered
    assert multiply.minimumArguments == 2


# ── Functions the format stores as node types ────────────────────────────────


def testLetAndLambdaCarryArgumentCountsAndNoIndex() -> None:
    """Both are documented functions the archive stores as node types.

    The counts match the signatures Numbers publishes in its own function
    browser: LET takes up to 126 name and value pairs plus a calculation, and
    LAMBDA up to 253 parameters plus one.
    """
    let = functionNamed("LET")
    assert (let.index, let.minimumArguments, let.maximumArguments) == (None, 3, 253)
    assert let.repeatingGroupSize == 2

    lambdaFunction = functionNamed("LAMBDA")
    assert lambdaFunction.index is None
    assert (lambdaFunction.minimumArguments, lambdaFunction.maximumArguments) == (
        1, 254
    )


def testAFunctionWithNoIndexRefusesToProduceOne() -> None:
    """There is no index to write, and inventing one would call something else."""
    with pytest.raises(UnknownFunctionError):
        functionIndexFor("LET")
    assert "LET" not in {f.name for f in functionsByIndex.values()}


# ── AC 5 and 10: regenerating reports what changed ───────────────────────────


def testComparisonReportsAnAddedFunction() -> None:
    """A function Numbers gained appears as added rather than silently arriving."""
    module = extractor()
    before = {"ABS": module.NumbersFunction("ABS", 1, 1, 1, 0)}
    after = dict(before) | {"NEWONE": module.NumbersFunction("NEWONE", 2, 1, 1, 0)}
    comparison = module.compareTables(after, before)
    assert [f.name for f in comparison.added] == ["NEWONE"]
    assert comparison.removed == () and comparison.changed == ()
    assert comparison.unchangedCount == 1


def testComparisonReportsARemovedAndAChangedFunction() -> None:
    """A withdrawn index and one whose counts moved are different findings."""
    module = extractor()
    before = {
        "ABS": module.NumbersFunction("ABS", 1, 1, 1, 0),
        "GONE": module.NumbersFunction("GONE", 2, 1, 1, 0),
        "NOW": module.NumbersFunction("NOW", 3, 1, 1, 0),
    }
    after = {
        "ABS": module.NumbersFunction("ABS", 1, 1, 1, 0),
        "NOW": module.NumbersFunction("NOW", 3, 1, 4, 0),
    }
    comparison = module.compareTables(after, before)
    assert [f.name for f in comparison.removed] == ["GONE"]
    assert [(w.maximumArguments, n.maximumArguments)
            for w, n in comparison.changed] == [(1, 4)]
    assert comparison.unchangedCount == 1


def testComparisonAgainstItselfIsEmpty() -> None:
    """Regenerating on the same Numbers reports nothing, which is what makes a
    real change visible."""
    module = extractor()
    committed = module.readCommitted(
        repositoryRoot / "src" / "pybers" / "_generated" / "functions.py"
    )
    assert committed is not None
    comparison = module.compareTables(committed, committed)
    assert (comparison.added, comparison.removed, comparison.changed) == ((), (), ())
    assert comparison.unchangedCount == len(committed)


def testTheCommittedTableMatchesWhatTheLibraryLoads() -> None:
    """The generated file and the model read the same table, so a stale
    regeneration cannot pass unnoticed."""
    module = extractor()
    committed = module.readCommitted(
        repositoryRoot / "src" / "pybers" / "_generated" / "functions.py"
    )
    assert committed is not None
    def fields(function: object) -> tuple[object, ...]:
        return tuple(
            getattr(function, attribute)
            for attribute in ("name", "index", "minimumArguments",
                              "maximumArguments", "repeatingGroupSize", "reserved")
        )

    # Compared field by field: the extractor and the model each define their own
    # NumbersFunction, so two identical rows are never the same type.
    assert {name: fields(f) for name, f in committed.items()} == {
        name: fields(f) for name, f in functionsByName.items()
    }

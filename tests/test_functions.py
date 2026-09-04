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
from pybers.model.formula import functionNodeType
from pybers.model.functions import (
    UnknownFunctionError,
    functionIndexFor,
    functionNameFor,
    functionNames,
)
from pybers.numbersfile import readPackage
from pybers.numbersfile.types import archiveTypeId

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
    if str(repositoryRoot / "scripts") not in sys.path:
        sys.path.insert(0, str(repositoryRoot / "scripts"))
    return importlib.import_module("scripts.functions-extract")


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
        (index, name)
        for index, name in functionNames.items()
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


def testTheMapIsPopulatedAndReadOnly() -> None:
    """A shared map handed out mutable would rename a function for every caller."""
    assert len(functionNames) > 300
    with pytest.raises(TypeError):
        functionNames[1] = "NOPE"  # type: ignore[index]


# ── AC 5: regenerating reports what changed ──────────────────────────────────


def testComparisonReportsAnAddedFunction() -> None:
    """A function Numbers gained appears as added rather than silently arriving."""
    module = extractor()
    comparison = module.compareMaps({1: "ABS", 2: "NEWONE"}, {1: "ABS"})
    assert comparison.added == ((2, "NEWONE"),)
    assert comparison.removed == ()
    assert comparison.renamed == ()
    assert comparison.unchangedCount == 1


def testComparisonReportsARemovedAndARenamedFunction() -> None:
    """A withdrawn index and a re-spelled one are different findings."""
    module = extractor()
    comparison = module.compareMaps({1: "ABS", 3: "NOW"}, {1: "ABS", 2: "GONE",
                                                           3: "WAS"})
    assert comparison.removed == ((2, "GONE"),)
    assert comparison.renamed == ((3, "WAS", "NOW"),)
    assert comparison.unchangedCount == 1


def testComparisonAgainstItselfIsEmpty() -> None:
    """Regenerating on the same Numbers reports nothing, which is what makes a
    real change visible."""
    module = extractor()
    comparison = module.compareMaps(dict(functionNames), dict(functionNames))
    assert (comparison.added, comparison.removed, comparison.renamed) == ((), (), ())
    assert comparison.unchangedCount == len(functionNames)

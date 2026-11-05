#!/usr/bin/env python3
"""\
The prose gate reads a Markdown line in full, whatever code span it holds.

A code span at the start of a line, blanked to spaces, once made the line read as an
indented code block, so the whole sentence escaped every check.

UPDATES
2026-10-26  A split verb warns on a time adverb alone.
2026-10-21  Every phrase the writing rules added, and a sentence opening on a
            conjunction or a preamble, each on one line and across a wrap, for
            PYB-249.
2026-10-13  Imports `lib/standards.py` rather than loading the command, for
            PYB-204.
2026-10-06  Written for PYB-178.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/06"

from pathlib import Path

import pytest

repositoryRoot: Path = Path(__file__).resolve().parent.parent
from tools.workflow.lib import standards  # noqa: E402


def findMessages(text: str) -> list[str]:
    """Return every finding the gate reports for one Markdown text."""
    findings: list = []
    standards.checkFile(Path("sample.md"), findings, text)
    return [finding[3] for finding in findings if finding[0] == "FAIL"]


@pytest.mark.parametrize(
    "line",
    ["`x` is load-bearing here.\n", "`foo/bar/` is load-bearing here.\n"],
    ids=["short span", "path span"],
)
def testALineOpeningWithACodeSpanIsChecked(line: str) -> None:
    assert findMessages(line) != []


def testALineHoldingACodeSpanMidwayIsChecked() -> None:
    assert findMessages("See `a.py`, load-bearing here.\n") != []


@pytest.mark.parametrize(
    "line",
    ["`load-bearing` opens the line.\n", "A span, `load-bearing`, sits midway.\n"],
    ids=["span first", "span midway"],
)
def testTextInsideACodeSpanStaysExempt(line: str) -> None:
    assert findMessages(line) == []


def testAnIndentedCodeBlockStaysExempt() -> None:
    assert findMessages("A paragraph.\n\n    load-bearing in code\n") == []


bannedSamples: list[str] = [
    "Reading no longer is the hard part.",
    "Parsing is the hard part.",
    "Speed is the one that matters.",
    "Correctness is the part that matters.",
    "The corpus grew.",
    "Both corpora grew.",
    "We circle back.",
    "It is hand-coded.",
    "He hand-codes it.",
    "Hand-coding it took a week.",
    "It was built by hand.",
]


@pytest.mark.parametrize("sentence", bannedSamples)
def testABannedPhraseFailsOnOneLine(sentence: str) -> None:
    assert findMessages(f"{sentence}\n") != []


@pytest.mark.parametrize("sentence", [s for s in bannedSamples if s.count(" ") > 2])
def testABannedPhraseFailsAcrossAWrap(sentence: str) -> None:
    words = sentence.split(" ")
    middle = len(words) // 2
    wrapped = " ".join(words[:middle]) + "\n" + " ".join(words[middle:]) + "\n"
    assert findMessages(wrapped) != []


@pytest.mark.parametrize("opener", ["And", "But", "So", "Allow me", "Let us"])
@pytest.mark.parametrize(
    "shape",
    ["{opener} it ran.\n", "It stopped. {opener} it ran.\n", "- {opener} it ran.\n",
     "It stopped.\n{opener} it ran.\n"],
    ids=["line start", "after a sentence", "list item", "after a wrap"],
)
def testASentenceOpeningOnABannedWordFails(opener: str, shape: str) -> None:
    assert findMessages(shape.format(opener=opener)) != []


@pytest.mark.parametrize(
    "text",
    ["It ran and\nstopped.\n", "It ran, so it stopped.\n", "It ran but stopped.\n"],
    ids=["wrapped mid-sentence", "after a comma", "mid-sentence"],
)
def testTheSameWordInsideASentencePasses(text: str) -> None:
    assert findMessages(text) == []


def testLetUsIsNoLongerExemptFromTheWeakLetCheck() -> None:
    findings: list = []
    standards.checkFile(Path("sample.md"), findings, "This will let us ship.\n")
    assert any("weak" in finding[3] for finding in findings)


@pytest.mark.parametrize(
    "source",
    ["x = 1  # So it runs.\n", 'def f():\n    """And this opens badly."""\n',
     'def f():\n    """Run it.\n\n    But this opens badly.\n    """\n'],
    ids=["comment", "one-line docstring", "docstring paragraph"],
)
def testAPythonSentenceOpeningOnABannedWordFails(source: str) -> None:
    findings: list = []
    standards.checkFile(Path("sample.py"), findings, source)
    assert any("sentence opens" in finding[3] for finding in findings)


def testAOneLineDocstringIsChecked() -> None:
    findings: list = []
    source = 'def f():\n    """It is load-bearing."""\n'
    standards.checkFile(Path("sample.py"), findings, source)
    assert any("load-bearing" in finding[3] for finding in findings)


def testASentenceAfterAClosingQuoteIsChecked() -> None:
    assert findMessages('It ran." So it stopped.\n') != []


def testAHashInsideAStringIsNotAComment() -> None:
    findings: list = []
    standards.checkFile(Path("sample.py"), findings, 'label = "# So it runs."\n')
    assert findings == []


def testAFileThatCannotTokenizeKeepsItsEarlierComments() -> None:
    findings: list = []
    standards.checkFile(Path("sample.py"), findings, "# It is load-bearing.\nx = (\n")
    assert any("load-bearing" in finding[3] for finding in findings)


def findWarnings(text: str) -> list[str]:
    """Return every warning the gate reports for one Markdown text."""
    findings: list = []
    standards.checkFile(Path("sample.md"), findings, text)
    return [finding[3] for finding in findings if finding[0] == "WARN"]


@pytest.mark.parametrize("sentence", [
    "The table is currently sorted by name.\n",
    "The value was previously cached by Numbers.\n",
])
def testATimeAdverbInsideAVerbWarns(sentence: str) -> None:
    assert any(warning.startswith("split verb") for warning in findWarnings(sentence))


@pytest.mark.parametrize("sentence", [
    "A schema can only express what the file stores.\n",
    "The writer must never round a number.\n",
    "The cell is also shared by the formula.\n",
])
def testAnyOtherAdverbInsideAVerbPasses(sentence: str) -> None:
    warnings = findWarnings(sentence)
    assert not any(warning.startswith("split verb") for warning in warnings)

#!/usr/bin/env python3
"""\
What `ticket.py` does to a drafted body on its way to GitHub, and what it reports.

GitHub renders an issue, pull request or comment body with GFM hard line breaks on,
so a newline inside a paragraph becomes a `<br>`. `unwrapParagraphs` joins those
paragraphs and reports what it changed, so the caller can say so rather than
rewriting an author's text in silence.

**The line ending is the author's, not the tool's.** Inside a fenced code block a
carriage return is the author's code rather than their formatting, and `splitlines`
followed by a `"\n".join` converts every one of them with nothing reported.

The first tests under `tests/` covering `scripts/`, which has none. Written narrowly
on purpose: these functions are pure over a string, needing no network and no
credential, which makes them the one piece of that tooling worth pinning before
PYB-11 decides what testing repo scripts should look like.

UPDATES
2026-09-11  `BodyChanges` in place of a tuple, for #74.
2026-09-11  Written for #72.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/11"

import sys
from pathlib import Path

import pytest

# `scripts/` is not a package and is not installed, so it is reached the way `pr.py`
# reaches it: by path. Inserted at the front so a stray `ticket` elsewhere cannot win.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ticket  # noqa: E402

# ── PYB-72 AC 1.i: the endings an author chose survive ───────────────────────


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("a fenced block", "```\r\nfirst\r\nsecond\r\n```\r\n"),
        ("a tilde fence", "~~~\r\ncode\r\n~~~\r\n"),
        ("list items", "- an item\r\n- another\r\n"),
        ("a table", "| a | b |\r\n| --- | --- |\r\n| 1 | 2 |\r\n"),
        ("a heading and a quote", "# Title\r\n\r\n> quoted\r\n"),
    ],
)
def testCarriageReturnsSurviveWhereANewlineIsMeaningful(
    label: str, body: str
) -> None:
    """A `\\r\\n` inside these is content, and converting it is a rewrite."""
    changes = ticket.unwrapParagraphs(body)

    assert changes.text == body, label
    assert changes.joined == 0, label


def testAFenceCarriesItsContentThroughUntouched() -> None:
    """The case that motivated PYB-72: pasted code keeps its own endings."""
    body = "Before.\n\n```python\r\ndef f() -> None:\r\n    pass\r\n```\n"

    changes = ticket.unwrapParagraphs(body)

    assert "\r\n" in changes.text
    assert changes.text == body
    assert changes.joined == 0


# ── PYB-72 AC 1: a change that does happen is reported ───────────────────────


def testJoiningAWrappedParagraphIsCounted() -> None:
    """The one transformation left, and it says so."""
    changes = ticket.unwrapParagraphs("one line\r\nand its continuation\r\n")

    assert changes.text == "one line and its continuation\r\n"
    assert changes.joined == 1


def testAJoinedParagraphKeepsTheEndingOfItsLastLine() -> None:
    """The join replaces the breaks inside, never the one that closes it."""
    changes = ticket.unwrapParagraphs("alpha\r\nbeta\r\n")

    assert changes.text.endswith("\r\n")


def testABareCarriageReturnBetweenProseIsJoinedAndCounted() -> None:
    """`splitlines` breaks on a lone `\\r`, so prose using one is still prose."""
    changes = ticket.unwrapParagraphs("alpha\rbeta\r")

    assert changes.text == "alpha beta\r"
    assert changes.joined == 1


# ── PYB-72 AC 2: silence when there is nothing to say ────────────────────────


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("one line", "a single line\n"),
        ("no trailing newline", "no newline at the end"),
        ("separated paragraphs", "first para\n\nsecond para\n"),
        ("empty", ""),
    ],
)
def testABodyNeedingNothingReportsNothing(label: str, body: str) -> None:
    """A report on every call is noise, and noise is not read."""
    changes = ticket.unwrapParagraphs(body)

    assert changes.text == body, label
    assert changes.joined == 0, label


# ── The layer above: reading the draft off disk ──────────────────────────────


def testReadingADraftDoesNotTranslateItsLineEndings(tmp_path: Path) -> None:
    """The half that `unwrapParagraphs` cannot reach on its own.

    `Path.read_text` applies universal newlines by default, so `\r\n` becomes
    `\n` before any of this code runs. Preserving endings inside the unwrap is
    worth nothing while the read above it has already thrown them away.
    """
    draft = tmp_path / "body.md"
    draft.write_bytes(b"Prose.\n\n```\r\nfirst\r\nsecond\r\n```\n")

    changes = ticket.readBodyFile(draft)

    assert changes.text.count("\r") == 3
    assert changes.joined == 0


def testReadingADraftStillJoinsItsWrappedProse(tmp_path: Path) -> None:
    """Reading without translation must not cost the unwrapping it exists for."""
    draft = tmp_path / "body.md"
    draft.write_bytes(b"a wrapped line\nand its continuation\n")

    changes = ticket.readBodyFile(draft)

    assert changes.text == "a wrapped line and its continuation\n"
    assert changes.joined == 1


# ── The behavior this function existed for, which must not regress ───────────


def testHardWrappedProseStillJoins() -> None:
    """The reason the function exists: eighty-eight columns must not reach GitHub."""
    changes = ticket.unwrapParagraphs(
        "This paragraph was wrapped by an editor\nand continues on a second line\n"
    )

    assert changes.text == (
        "This paragraph was wrapped by an editor and continues on a second line\n"
    )
    assert changes.joined == 1


def testAWrappedListItemJoinsIntoItsOwnItem() -> None:
    """A continuation joins the item rather than escaping the list."""
    changes = ticket.unwrapParagraphs(
        "- an item that was\n  wrapped by an editor\n- a second item\n"
    )

    assert changes.text == "- an item that was wrapped by an editor\n- a second item\n"
    assert changes.joined == 1

#!/usr/bin/env python3
"""\
Status messages: a step a long call reports, and a part a call skipped.

Each shape `docs/message-design.md` defines has its composer here, so a message's
structure comes from the composer and its author supplies only the words.

UPDATES
2026-11-24  Written for PYB-319.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

from collections.abc import Callable
from dataclasses import dataclass

ellipsis: str = "…"


@dataclass(frozen=True, slots=True)
class ProgressStep:
    """A step a long call has started, and how far it is when its total is known."""

    message: str
    completed: int | None = None
    total: int | None = None

    def __post_init__(self) -> None:
        if (self.completed is None) != (self.total is None):
            raise ValueError("A step carries a count and its total together.")

    def __str__(self) -> str:
        if self.total is None:
            return self.message
        return f"{self.message} {self.completed}/{self.total}"


type ProgressListener = Callable[[ProgressStep], None]


def findPhraseRefusal(phrase: str) -> str | None:
    """Return why a status phrase is malformed, or None when it reads as one.

    The one place a phrase's form is decided: lowercase first, no closing mark.
    """
    if not phrase or phrase != phrase.strip():
        return f"A status phrase holds words and no outer spaces, not {phrase!r}."
    if phrase[0].isupper():
        return f"A status phrase opens in lowercase, and {phrase!r} does not."
    if phrase.endswith((".", ellipsis)):
        return f"A status phrase takes no closing mark, and {phrase!r} has one."
    return None


def composeProgressStep(phrase: str) -> ProgressStep:
    """Return a step whose total is unknown, `reading the document…`."""
    refusal = findPhraseRefusal(phrase)
    if refusal is not None:
        raise ValueError(refusal)
    return ProgressStep(f"{phrase}{ellipsis}")


def composeProgressCount(phrase: str, completed: int, total: int) -> ProgressStep:
    """Return a step of a known total, `reading the fonts… 12/2411`."""
    if not 0 <= completed <= total:
        raise ValueError(f"A count of {completed} of {total} is out of its range.")
    return ProgressStep(composeProgressStep(phrase).message, completed, total)


def dropProgress(step: ProgressStep) -> None:
    """Hear a step and do nothing, for a call given no listener."""


@dataclass(frozen=True, slots=True)
class PartSkip:
    """A part a call matched and left as it was, and why, as a short phrase.

    `place` is the part as text that reads back, a reference or a path.
    """

    place: str
    reason: str

    def __post_init__(self) -> None:
        refusal = findPhraseRefusal(self.reason)
        if refusal is not None:
            raise ValueError(refusal)


__all__ = [
    "PartSkip",
    "ProgressListener",
    "ProgressStep",
    "composeProgressCount",
    "composeProgressStep",
    "dropProgress",
]

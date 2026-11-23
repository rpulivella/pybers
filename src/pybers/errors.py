#!/usr/bin/env python3
"""\
Every error this library raises, rooted so that one `except` clause can be right.

`PybersError` is the base of all of them, which is the shape `requests`,
`sqlalchemy` and every PEP 249 database driver settled on: a caller wrapping
`pybers.open` in a `try` needs one name, and a library without one leaves them
catching `Exception` and swallowing their own bugs along with ours.

**Each error keeps the builtin base it already had**, so `ReferenceError` is still
a `ValueError` and `SelectionError` is still a `LookupError`. Adding a root rather
than replacing those is what keeps an existing `except ValueError` working, and it
is the same move `requests` makes so that its `JSONDecodeError` answers to both
names.

Only the two general ones live here, with the composers every message is built
by, one per shape `docs/message-design.md` defines. An error belonging to a feature
lives with that feature, because moving it here would put half of `formula` in a
file named for exceptions, and `pybers` re-exports them all so a caller sees one list.

UPDATES
2026-11-23  `composeRefusal`, `composeTextRefusal`, `composeReadRefusal` and
            `composeFault`, one composer per shape of message, for PYB-307.
2026-11-17  `composeChoiceRefusal`, a refused choice and the closest one, for
            PYB-266.
2026-09-08  Written for #58, after finding that `ContainerError` escapes
            `pybers.open` on a file that is not a zip and was not exported,
            leaving `except Exception` as the only correct clause.
"""
from __future__ import annotations

import difflib
from collections.abc import Sequence

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/08"


nothingWritten: str = "Nothing was written"
nothingRead: str = "Nothing was read"
issuesAddress: str = "https://github.com/rpulivella/pybers/issues"
choicesListedMost: int = 5


def formatSentence(text: str) -> str:
    """Return one part of a message as a sentence, the one place a period is added.

    A part arriving with its own period is a composer misused, refused so the period
    is never doubled.
    """
    if text.endswith("."):
        raise ValueError(f"A message part takes no period, and {text!r} has one.")
    return f"{text}."


def composeRefusal(
    place: str, cause: str, fix: str | None = None, notDone: str | None = None
) -> str:
    """Return a refusal: the place, its cause, any fix, then what was not done.

    The structure every refusal shares, so no author repeats it.
    """
    parts = [formatSentence(f"{place} {cause}")]
    parts += [formatSentence(part) for part in (fix, notDone) if part is not None]
    return " ".join(parts)


def composeWithheldRefusal(refusal: str, notDone: str) -> str:
    """Return a refusal a check composed, ending in what the call did not do."""
    return f"{refusal} {formatSentence(notDone)}"


def composeTextRefusal(
    text: str, index: int, cause: str, fix: str | None = None
) -> str:
    """Return the refusal of malformed text, its place the column counted from one."""
    return composeRefusal(f"`{text}`, column {index + 1},", cause, fix)


def composeReadRefusal(path: object, cause: str, fix: str | None = None) -> str:
    """Return the refusal of a file pybers cannot read as a Numbers document."""
    return composeRefusal(str(path), cause, fix, nothingRead)


def composeFault(place: str, cause: str, notDone: str | None = None) -> str:
    """Return a fault in pybers, a state it should never reach, asking for a report."""
    return composeRefusal(place, cause, f"Report this at {issuesAddress}", notDone)


class PybersError(Exception):
    """Anything this library raises, and the one name a caller can always catch."""

    choices: tuple[str, ...] = ()
    notDone: str | None = None


def composeChoiceRefusal[ErrorType: PybersError](
    errorType: type[ErrorType],
    given: object,
    noun: str,
    choices: Sequence[str],
    notDone: str | None = None,
) -> ErrorType:
    """Return the refusal of a value not among its choices, stating the closest.

    Where none is close and too many to list, the error carries its choices and what
    was not done, so a consumer can say where the choices are before that.
    """
    shown = given if isinstance(given, str) else repr(given)
    closest = difflib.get_close_matches(str(given), choices, n=1)
    if closest:
        fix: str | None = f"The closest is {closest[0]}"
    elif len(choices) <= choicesListedMost:
        fix = f"The choices are {formatChoiceList(choices)}"
    else:
        fix = None
    error = errorType(composeRefusal(repr(shown), f"is not {noun}", fix, notDone))
    if fix is None:
        error.choices = tuple(choices)
        error.notDone = notDone
    return error


def formatChoiceList(choices: Sequence[str]) -> str:
    """Return choices as prose, `a, b and c`."""
    if len(choices) == 1:
        return choices[0]
    return f"{', '.join(choices[:-1])} and {choices[-1]}"


class ReadError(PybersError, RuntimeError):
    """A `.numbers` document whose structure could not be walked."""


class WriteError(PybersError, RuntimeError):
    """A document that could not be written back to a package."""


__all__ = [
    "PybersError",
    "ReadError",
    "WriteError",
    "composeChoiceRefusal",
    "composeRefusal",
    "nothingRead",
    "nothingWritten",
]

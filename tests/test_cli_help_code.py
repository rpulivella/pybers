#!/usr/bin/env python3
"""\
Help shows a span quoted in backticks as code, without the backticks only in color.

UPDATES
2026-11-24  Written for PYB-315.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/24"

import click

from conftest import renderPlain
from pybers.cli._app import app
from pybers.cli._help import formatHelp, formatHelpText


def testColoredHelpDropsTheBackticksAndStylesTheSpan() -> None:
    shown = formatHelpText("Give `fonts` or a file.", colored=True)
    assert shown.plain == "Give fonts or a file."
    assert [(span.start, span.end, span.style) for span in shown.spans] == [
        (5, 10, "code"),
    ]


def testPlainTextKeepsTheBackticks() -> None:
    assert formatHelpText("Give `fonts` or a file.", colored=False).plain == (
        "Give `fonts` or a file."
    )


def renderShowHelp(color: bool) -> str:
    """Return `pybers show --help` as plain text, rendered in color or not."""
    show = app.get_command(click.Context(app), "show")
    assert show is not None
    shown = formatHelp(show, click.Context(show, info_name="show", color=color))
    return renderPlain(shown)


def testHelpInColorShowsNoBacktick() -> None:
    assert "`" not in renderShowHelp(color=True)


def testPlainHelpKeepsTheBackticks() -> None:
    assert "`fonts`" in renderShowHelp(color=False)

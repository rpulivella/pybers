#!/usr/bin/env python3
"""\
The two consoles every command prints through, and the theme that names their styles.

`console` carries results on stdout and `statusConsole` carries spinners, progress
and refusals on stderr, so a piped or pasted result never holds a spinner frame.
Lines are soft-wrapped, so a pasted report keeps each fact on one line, and a tree
draws two-column guides rather than Rich's four. See `docs/cli-design.md`.

UPDATES
2026-11-24  `showProgress`, a spinner for a step and a bar for a known total, for
            PYB-319.
2026-11-23  The logo's styles, for PYB-304.
2026-11-03  The badge styles, for PYB-223.
2026-10-11  The theme's styles are a frozendict, for PYB-189.
2026-10-07  Written for PYB-169.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn
from rich.status import Status
from rich.theme import Theme
from rich.tree import Tree

import pybers

themeStyles: frozendict[str, str] = frozendict({
    "label": "dim",
    "value": "bold",
    "success": "green",
    "failure": "red",
    "warning": "yellow",
    "detail": "dim",
    "identifier": "bold cyan",
    "code": "cyan",
    "badge.info": "bold black on cyan",
    "badge.success": "bold black on green",
    "badge.warning": "bold black on yellow",
    "badge.failure": "bold white on red",
    "logo.grid": "dim",
    "logo.mark": "bold",
    "logo.caret": "bold #ee9e10",
    "logo.name": "bold",
})
theme: Theme = Theme(themeStyles)

console: Console = Console(theme=theme, highlight=False, soft_wrap=True)
statusConsole: Console = Console(
    theme=theme, highlight=False, soft_wrap=True, stderr=True
)


class TreeCompact(Tree):
    """A Rich tree whose guides are two columns wide rather than four."""

    ASCII_GUIDES = ("  ", "| ", "+ ", "` ")
    # Rich picks the second and third sets for bold and double-underlined guides.
    TREE_GUIDES = [
        ("  ", "│ ", "├ ", "└ "),
        ("  ", "┃ ", "┣ ", "┗ "),
        ("  ", "║ ", "╠ ", "╚ "),
    ]


# One column wide, so a spinner fits the gutter where a section's marker sits.
spinnerName: str = "dots3"


class ProgressDisplay:
    """The one display a call's progress shows on stderr, a spinner or a bar.

    Rich runs one live display per console, so a step of a known total stops the
    spinner before its bar starts, and the reverse.
    """

    def __init__(self) -> None:
        self.status: Status | None = None
        self.progress: Progress | None = None
        self.task: TaskID | None = None

    def __call__(self, step: pybers.ProgressStep) -> None:
        if step.total is None:
            self.progressStop()
            if self.status is None:
                self.status = statusConsole.status(
                    step.message, spinner=spinnerName, spinner_style="value"
                )
                self.status.start()
            self.status.update(step.message)
            return
        self.statusStop()
        if self.progress is None:
            self.progress = Progress(
                SpinnerColumn(spinnerName, style="value"),
                TextColumn("{task.description}"),
                BarColumn(
                    bar_width=24, style="label", complete_style="value",
                    finished_style="value", pulse_style="value",
                ),
                TextColumn("{task.completed}/{task.total}", style="value"),
                console=statusConsole,
                transient=True,
                # Rich ends a bar with a newline where nothing was drawn.
                disable=not statusConsole.is_interactive,
            )
            self.progress.start()
        if self.task is None:
            self.task = self.progress.add_task(step.message, total=step.total)
        elif self.progress.tasks[0].description != step.message:
            # A new count restarts the bar.
            self.progress.reset(self.task, total=step.total, description=step.message)
        self.progress.update(self.task, completed=step.completed, total=step.total)

    def statusStop(self) -> None:
        """Stop the spinner, if one shows, leaving nothing behind."""
        if self.status is not None:
            self.status.stop()
            self.status = None

    def progressStop(self) -> None:
        """Stop the bar, if one shows, leaving nothing behind."""
        if self.progress is not None:
            self.progress.stop()
            self.progress, self.task = None, None


@contextmanager
def showProgress() -> Generator[ProgressDisplay]:
    """Show each step a call reports while it runs, and nothing once it finishes."""
    display = ProgressDisplay()
    try:
        yield display
    finally:
        display.statusStop()
        display.progressStop()


__all__ = [
    "ProgressDisplay", "TreeCompact", "console", "showProgress", "statusConsole",
    "theme", "themeStyles",
]

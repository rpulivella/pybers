#!/usr/bin/env python3
"""\
The two consoles every command prints through, and the theme that names their styles.

`console` carries results on stdout and `statusConsole` carries spinners, progress
and refusals on stderr, so a piped or pasted result never holds a spinner frame.
Lines are soft-wrapped, so a pasted report keeps each fact on one line, and a tree
draws two-column guides rather than Rich's four. See `docs/cli-design.md`.

UPDATES
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

from rich.console import Console
from rich.theme import Theme
from rich.tree import Tree

theme: Theme = Theme({
    "label": "dim",
    "value": "bold",
    "success": "green",
    "failure": "red",
    "warning": "yellow",
    "detail": "dim",
    "identifier": "bold cyan",
})

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


__all__ = ["TreeCompact", "console", "statusConsole", "theme"]

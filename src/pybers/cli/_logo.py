#!/usr/bin/env python3
"""\
The pybers logo drawn in a terminal: a selected cell between gridlines, holding the
Python prompt and a caret, beside the name.

`docs/logo/pybers-logo-dark.svg` measures the padding before the prompt, the gap before
the caret and the padding after it as about equal, so each is one column. The ring and
prompt take the terminal's own color, which reads on a light or a dark background, and
the caret alone keeps the logo's orange. See `docs/cli-design.md`.

UPDATES
2026-11-23  Written for PYB-304.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/23"

from rich.console import Group
from rich.text import Text

# The ring's inside: padding, the prompt, a gap, the caret, padding.
ringWidth: int = 7


def formatLogo() -> Group:
    """Return the logo and the name beside it, as Rich renders them."""
    edge = "━" * ringWidth
    column = " " * ringWidth
    return Group(
        Text.assemble(("    ╷", "logo.grid"), column, ("╷", "logo.grid")),
        Text.assemble(
            ("  ╶─", "logo.grid"), (f"┏{edge}┓", "logo.mark"), ("─╴", "logo.grid")
        ),
        Text.assemble(
            "    ", ("┃ ❯❯❯ ", "logo.mark"), ("▌", "logo.caret"), (" ┃", "logo.mark"),
            "   ", ("pybers", "logo.name"),
        ),
        Text.assemble(
            ("  ╶─", "logo.grid"), (f"┗{edge}┛", "logo.mark"), ("─╴", "logo.grid")
        ),
        Text.assemble(("    ╵", "logo.grid"), column, ("╵", "logo.grid")),
    )


__all__ = ["formatLogo"]

#!/usr/bin/env python3
"""\
The `pybers` command, a front end reaching the library through `import pybers`.

Each command is a module here, registered in `_app`, and a command that gains
subcommands becomes a package of its own. Click and Rich come from the `cli` extra,
so `main` says how to install them rather than failing with a traceback.

UPDATES
2026-11-23  Click and Rich rather than Typer, for PYB-304.
2026-10-07  Written for PYB-169, with `check` as the first command.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/07"

import sys


def main() -> None:
    """Run the `pybers` command."""
    try:
        from pybers.cli._app import app
    except ModuleNotFoundError as exc:
        if exc.name not in ("click", "rich"):
            raise
        sys.exit(
            "The pybers command needs Click and Rich. Install them with: "
            "pip install 'pybers[cli]'"
        )
    app(prog_name="pybers")


__all__ = ["main"]

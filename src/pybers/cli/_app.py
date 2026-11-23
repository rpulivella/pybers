#!/usr/bin/env python3
"""\
The command registry: the `pybers` Click group, its root options, and every command.

UPDATES
2026-11-23  A Click group, its help drawn by the renderer in `_help`, for PYB-304.
2026-11-19  `locale` removed, a locale set by `set --locale`, for PYB-301.
2026-10-28  `locale` registered, for PYB-272.
2026-10-27  `show` registered, for PYB-260.
2026-10-20  `set` registered, for PYB-217.
2026-10-12  A first argument naming no command runs check --names on it, for PYB-187.
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

import click

from pybers.cli._common import CommandSettings
from pybers.cli._help import writeHelp
from pybers.cli.check import runCheck
from pybers.cli.set import runSet
from pybers.cli.show import runShow

# What `pybers FILE` runs, so a document always shows something.
defaultCommandArguments: tuple[str, ...] = ("check", "--names")


class PybersGroup(click.Group):
    """The root command, which routes a first argument naming no command to `check`.

    A file named like a command is reached as `./check`, which names no command.
    """

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Resolve a command, or `check --names` when the first argument names none."""
        if args and self.get_command(ctx, args[0]) is None:
            args = [*defaultCommandArguments, *args]
        return super().resolve_command(ctx, args)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Write the root command's help through the one renderer."""
        writeHelp(self, ctx, formatter)


@click.pass_context
def runPybers(context: click.Context, debug: bool) -> None:
    """Store the root options for every command to read."""
    context.obj = CommandSettings(debug=debug)


app: PybersGroup = PybersGroup(
    "pybers",
    callback=runPybers,
    params=[click.Option(
        ["--debug"], is_flag=True, envvar="PYBERS_DEBUG", show_envvar=True,
        help="Print the full traceback of any error instead of one line.",
    )],
    commands=[runCheck, runSet, runShow],
    help="Read and write Apple Numbers documents.",
)


__all__ = ["app"]

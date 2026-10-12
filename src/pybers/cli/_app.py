#!/usr/bin/env python3
"""\
The command registry: the `pybers` Typer app, its root options, and every command.

Typer's traceback printer hides local variables, because a traceback gets pasted
into a public issue and a local can hold a cell's value.

Typer draws every help and error panel with a hard-coded rounded box and offers no
setting for it, so `typer.rich_utils.Panel` is replaced by `HelpSection`, which
draws the title over the table. `tests/test_cli_check.py` fails if a Typer release
brings the borders back. See `docs/cli-design.md`.

UPDATES
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

from typing import Annotated

import typer
import typer.core
import typer.rich_utils
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.padding import Padding
from rich.text import Text

# Typer bundles Click and names its types nowhere public, so an override reaches in.
from typer._click import Command, Context

from pybers.cli._common import CommandSettings
from pybers.cli.check import runCheck


class HelpSection:
    """A Typer help or error panel drawn as its title over its table, with no border.

    Indented one column, as Typer indents its usage line, so every line aligns.
    """

    def __init__(
        self,
        renderable: RenderableType = "",
        *,
        title: RenderableType | None = None,
        border_style: str = "",
        **_: object,
    ) -> None:
        """Keep what Typer would have framed, its border's color moving to the title."""
        self.renderable = renderable
        self.title = title
        self.titleStyle = border_style

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render the title, the table, and a blank line after them."""
        title = (
            Text(self.title, self.titleStyle) if isinstance(self.title, str)
            else self.title
        )
        shown = [title, self.renderable] if title is not None else [self.renderable]
        yield Padding(Group(*shown), (0, 0, 1, 1))


# What `pybers FILE` runs, so a document always shows something.
defaultCommandArguments: tuple[str, ...] = ("check", "--names")


class PybersGroup(typer.core.TyperGroup):
    """The root command, which routes a first argument naming no command to `check`.

    A file named like a command is reached as `./check`, which names no command.
    """

    def resolve_command(
        self, ctx: Context, args: list[str]
    ) -> tuple[str | None, Command | None, list[str]]:
        """Resolve a command, or `check --names` when the first argument names none."""
        if args and self.get_command(ctx, args[0]) is None:
            args = [*defaultCommandArguments, *args]
        return super().resolve_command(ctx, args)


# Typer imports `Panel` without re-exporting it, which is the name it draws with.
typer.rich_utils.Panel = HelpSection  # type: ignore[attr-defined,assignment]

app = typer.Typer(
    name="pybers",
    cls=PybersGroup,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


@app.callback()
def runPybers(
    context: typer.Context,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            envvar="PYBERS_DEBUG",
            help="Print the full traceback of any error instead of one line.",
        ),
    ] = False,
) -> None:
    """Read and write Apple Numbers documents."""
    context.obj = CommandSettings(debug=debug)


app.command("check")(runCheck)


__all__ = ["app"]

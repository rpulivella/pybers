#!/usr/bin/env python3
"""\
The one renderer every help screen goes through, the root command's and each command's.

Click writes plain help and no argument help at all, so a command is a `PybersCommand`
and each argument a `PybersArgument`, and the help reads the same whatever it belongs
to. A usage line is Click's own, a required argument bare and an optional one in
brackets, as POSIX writes them. See `docs/cli-design.md`.

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

import io
import re
import shutil
from collections.abc import Iterable
from enum import Enum
from typing import Any

import click
from rich.console import Console, Group, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from pybers.cli._console import theme
from pybers.cli._logo import formatLogo

# How far a section's rows and a command's description sit under their title.
rowIndent: int = 2
# The spaces and color codes ending a line, and one color code.
lineEnd: re.Pattern[str] = re.compile(r"(?: |\x1b\[[0-9;]*m)+$", re.MULTILINE)
colorCode: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*m")


class PybersArgument(click.Argument):
    """A positional argument carrying the help Click gives only to an option."""

    def __init__(self, *args: Any, help: str, **kwargs: Any) -> None:
        """Keep the argument's help, for the renderer to print beside its name."""
        super().__init__(*args, **kwargs)
        self.help = help


class ChoiceOfValues(click.Choice[Any]):
    """A choice among an enum's members, typed and shown by value rather than name."""

    def normalize_choice(self, choice: object, ctx: click.Context | None) -> str:
        """Match a member by its value, `json`, as it is typed and shown."""
        return super().normalize_choice(
            choice.value if isinstance(choice, Enum) else choice, ctx
        )


def formatChoices(choices: Iterable[object]) -> str:
    """Return a choice's alternatives as POSIX writes them, `text|json`."""
    return "|".join(
        str(each.value) if isinstance(each, Enum) else str(each) for each in choices
    )


def formatOptionName(option: click.Option) -> Text:
    """Return an option's flags and, unless it is a flag, what it takes."""
    shown = Text(", ".join([*option.opts, *option.secondary_opts]), "identifier")
    if option.is_flag:
        return shown
    if isinstance(option.type, click.Choice):
        takes = formatChoices(option.type.choices)
    else:
        takes = option.metavar or option.type.name.upper()
    return shown.append(f" {takes}", "label")


def formatOptionHelp(option: click.Option) -> Text:
    """Return an option's help, then its default and environment variable if shown."""
    shown = Text(option.help or "")
    if option.show_default and option.default is not None:
        default = formatChoices([option.default])
        shown.append(f" [default: {default}]", "detail")
    if option.show_envvar and isinstance(option.envvar, str):
        shown.append(f" [env var: {option.envvar}]", "detail")
    return shown


def formatSection(title: str, rows: list[tuple[Text, Text]]) -> list[RenderableType]:
    """Return a section as its title over its rows, with no border, or nothing."""
    if not rows:
        return []
    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0))
    table.add_column(no_wrap=True)
    table.add_column()
    for name, help in rows:
        table.add_row(name, help)
    return [Text(""), Text(title, "label"), Padding(table, (0, 0, 0, rowIndent))]


def formatHelp(command: click.Command, context: click.Context) -> Group:
    """Return a command's help: its usage, description, arguments, options, commands.

    The root command's help opens with the logo, and no other command's does.
    """
    usage = " ".join([context.command_path, *command.collect_usage_pieces(context)])
    shown: list[RenderableType] = [] if context.parent else [formatLogo(), Text("")]
    shown.append(Text.assemble(("Usage: ", "label"), (usage, "value")))
    if command.help:
        shown += [Text(""), Padding(Text(command.help), (0, 0, 0, rowIndent))]
    parameters = command.get_params(context)
    shown += formatSection("Arguments", [
        (Text(each.human_readable_name, "identifier"), Text(each.help or ""))
        for each in parameters if isinstance(each, PybersArgument)
    ])
    shown += formatSection("Options", [
        (formatOptionName(each), formatOptionHelp(each))
        for each in parameters if isinstance(each, click.Option) and not each.hidden
    ])
    if isinstance(command, click.Group):
        found = [
            command.get_command(context, name)
            for name in command.list_commands(context)
        ]
        shown += formatSection("Commands", [
            (Text(each.name or "", "identifier"), Text(each.get_short_help_str(10_000)))
            for each in found if each is not None and not each.hidden
        ])
    return Group(*shown)


def writeHelp(
    command: click.Command, context: click.Context, formatter: click.HelpFormatter
) -> None:
    """Write a command's help into Click's formatter, colored for Click to keep or drop.

    Click strips the color when its output is not a terminal, so it is always written.
    """
    width = context.terminal_width or shutil.get_terminal_size().columns
    buffer = io.StringIO()
    Console(
        file=buffer, width=width, theme=theme, highlight=False,
        force_terminal=True, color_system="standard",
    ).print(formatHelp(command, context))
    # Rich pads each line to the width, and a pasted help needs none of it.
    formatter.write(lineEnd.sub(
        lambda end: "".join(colorCode.findall(end.group())), buffer.getvalue()
    ))


class PybersCommand(click.Command):
    """A command whose help the one renderer draws."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Write this command's help through the one renderer."""
        writeHelp(self, ctx, formatter)


__all__ = [
    "ChoiceOfValues",
    "PybersArgument",
    "PybersCommand",
    "formatHelp",
    "writeHelp",
]

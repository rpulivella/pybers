#!/usr/bin/env python3
"""\
Every module-level function name opens with a verb, checked across the repository.

A method names its subject first and a module-level function its verb first, so a
name reads as an action rather than as the value it returns. Only the verb position
is checkable, and only against a list: a noun that doubles as a verb, `formatClaims`
once, passes it, which is why a new verb joins `leadingVerbs` deliberately.

UPDATES
2026-09-23  `clamp` and `relocate` added to the verbs, for PYB-18.
2026-09-17  `wait` added for PYB-76, which waits for GitHub to close a ticket.
2026-09-17  `reopen` added for PYB-76, which reopens a ticket a merge closed.
2026-09-17  `hold` added for PYB-94, which holds the display awake through a run.
2026-09-17  Written for PYB-98.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/17"

import ast
import re
from pathlib import Path

repositoryRoot: Path = Path(__file__).resolve().parent.parent
checkedDirectories: tuple[str, ...] = ("src", "tests", "scripts")

leadingVerbs: frozenset[str] = frozenset({
    "add", "apply", "assert", "assign", "attach", "author", "bind", "blank",
    "borrow", "build", "carries", "check", "choose", "clamp", "classify", "close",
    "collect",
    "compress", "confirm", "copy", "count", "create", "decode", "decompress",
    "delete", "detach", "drop", "edit", "emit", "encode", "expand", "extract",
    "find", "forge", "format", "generate", "hold", "index", "is", "iterate", "list",
    "load",
    "map", "mark", "measure", "merge", "move", "open", "order", "parse", "patch",
    "place", "post", "print", "qualify", "quote", "read", "reduce", "refuse",
    "register", "release", "relocate", "remap", "remove", "render", "reopen",
    "report", "request",
    "resolve", "retype", "rewrite", "run", "save", "select", "set", "shape", "show",
    "split", "summarize", "survey", "to", "tokenize", "unquote", "unwrap", "update",
    "verify", "wait", "walk", "write",
})

# `main` is looked up by name, and a fixture's name is the value a test receives.
exemptNames: frozenset[str] = frozenset({"main"})


def findVerblessFunctions(path: Path) -> list[str]:
    """Return each module-level function in a file whose name opens with no verb."""
    found = []
    for node in ast.parse(path.read_text()).body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        name = node.name
        if name.startswith("test") or name in exemptNames:
            continue
        decorators = [ast.unparse(decorator) for decorator in node.decorator_list]
        if any("fixture" in decorator for decorator in decorators):
            continue
        leading = re.match(r"_*([a-z]+)", name)
        if leading is None or leading.group(1) not in leadingVerbs:
            found.append(f"{path}:{node.lineno} {name}")
    return found


def testEveryModuleLevelFunctionOpensWithAVerb() -> None:
    """PYB-98 AC 5. A new verb is added to `leadingVerbs`; a noun is renamed."""
    found = [
        finding
        for directory in checkedDirectories
        for path in sorted((repositoryRoot / directory).rglob("*.py"))
        if "_generated" not in path.parts
        for finding in findVerblessFunctions(path)
    ]

    assert found == [], "open these names with a verb:\n  " + "\n  ".join(found)


def testAVerblessNameIsReportedWithItsFileAndLine(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def readValue():\n    pass\n\n\ndef valueFor():\n    pass\n\n\n"
        "class Holder:\n    def valueGet(self):\n        pass\n"
    )

    assert findVerblessFunctions(source) == [f"{source}:5 valueFor"]

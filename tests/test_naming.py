#!/usr/bin/env python3
"""\
Every module-level function name opens with a verb, checked across the repository.

A method names its subject first and a module-level function its verb first, so a
name reads as an action rather than as the value it returns. Only the verb position
is checkable, and only against a list: a noun that doubles as a verb, `formatClaims`
once, passes it, which is why a new verb joins `leadingVerbs` deliberately. A verb a
public function opens with comes from the public API instead, and `docs/vocabulary.md`
defines what it means, so each verb is written down in one place.

UPDATES
2026-11-20  `leadingVerbs` holds only the verbs no public function opens with, each
            public one read from `pybers.__all__`, for PYB-309.
2026-11-18  `escape` is a verb, as `CSS.escape` names it, for PYB-267.
2026-11-05  `pytest_xdist_auto_num_workers`, a hook xdist finds by name, is exempt, for
            PYB-277.
2026-11-03  `match` is a verb, for PYB-223.
2026-11-02  `compose` is a verb, for PYB-276.
2026-10-22  `pytest_addoption`, a hook pytest finds by name, is exempt, for PYB-255.
2026-10-14  `record` and `sort` are verbs, for PYB-211.
2026-10-14  Checks `tools/` too, which the move from `scripts/` brought into reach,
            for PYB-204.
2026-10-05  `restart` added to the verbs, for PYB-153.
2026-09-29  `claim`, `fill` and `recount` added to the verbs, for PYB-118.
2026-09-25  `convert` added to the verbs, for PYB-134.
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
import inspect
import re
from pathlib import Path

import pybers

repositoryRoot: Path = Path(__file__).resolve().parent.parent
checkedDirectories: tuple[str, ...] = ("src", "tests", "tools")

# The verbs only internal names open with; the public ones come from `publicVerbs`.
leadingVerbs: frozenset[str] = frozenset({
    "add", "apply", "assert", "assign", "attach", "author", "bind", "blank", "borrow",
    "build", "carries", "choose", "claim", "clamp", "classify", "close", "collect",
    "compare", "compress", "confirm", "convert", "copy", "count", "decode",
    "decompress", "delete", "detach", "drop", "edit", "emit", "encode", "expand",
    "extract", "fill", "forge", "generate", "hold", "index", "is", "iterate", "list",
    "load", "locate", "map", "mark", "match", "measure", "merge", "move", "normalize",
    "order", "patch", "place", "post", "print", "qualify", "quote", "read", "record",
    "recount", "reduce", "refuse", "register", "release", "relocate", "remap", "remove",
    "render", "reopen", "report", "request", "resolve", "restart", "retype", "rewrite",
    "run", "save", "select", "set", "shape", "show", "sort", "split", "summarize",
    "survey", "tokenize", "unquote", "unwrap", "update", "verify", "wait", "walk",
    "write",
})

# Each verb a public function opens with, which `docs/vocabulary.md` defines.
publicVerbs: frozenset[str] = frozenset(
    re.split(r"(?=[A-Z])", name)[0] for name in pybers.__all__
    if inspect.isfunction(getattr(pybers, name))
)

# `main` and a pytest hook are looked up by name, and a fixture's name is the value a
# test receives.
exemptNames: frozenset[str] = frozenset(
    {"main", "pytest_addoption", "pytest_xdist_auto_num_workers"}
)


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
        if leading is None or leading.group(1) not in leadingVerbs | publicVerbs:
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


def testNoPublicVerbIsAlsoListedForInternalNames() -> None:
    assert leadingVerbs & publicVerbs == frozenset()


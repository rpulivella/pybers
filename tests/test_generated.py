#!/usr/bin/env python3
"""\
The generated protobuf tree: that it is complete, and that its type stubs match it.

`tools/protos-extract.py` writes `_pb2.py` and `_pb2.pyi` from one protoc call, so
they cannot ordinarily drift. This is the guard for when they do: a regeneration run
without `protoc-gen-mypy` on PATH produces modules with no stubs beside them, and the
only symptom would be mypy quietly checking nothing where the protobuf surface is.

That surface is most of what every `_read` and `_write` module does, and a mistyped
field there is the failure this format answers with a plausible wrong number rather
than an error, so losing the check is worth failing a test over.

Nothing here needs protoc, which is deliberate: the extraction requires a local
Numbers.app and will never run in CI, but this check runs everywhere.

UPDATES
2026-09-02  Written for #4.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/02"

from pathlib import Path

generatedDirectory: Path = (
    Path(__file__).resolve().parent.parent / "src" / "pybers" / "_generated"
)


def test_thereIsAGeneratedTreeAtAll() -> None:
    """Guard the guard: an empty directory would make every case below vacuous."""
    assert len(list(generatedDirectory.glob("*_pb2.py"))) >= 30


def test_everyGeneratedModuleHasATypeStub() -> None:
    """A module without its stub means protoc ran without `protoc-gen-mypy`."""
    modules = {path.stem for path in generatedDirectory.glob("*_pb2.py")}
    stubs = {path.stem for path in generatedDirectory.glob("*_pb2.pyi")}

    assert not modules - stubs, (
        "generated modules with no type stub beside them: "
        + ", ".join(sorted(modules - stubs))
    )


def test_everyTypeStubHasAGeneratedModule() -> None:
    """The other direction: a stub left behind after its module was renamed.

    A stub with no module is dead weight that mypy still reads, and it would keep
    resolving a name that no longer exists.
    """
    modules = {path.stem for path in generatedDirectory.glob("*_pb2.py")}
    stubs = {path.stem for path in generatedDirectory.glob("*_pb2.pyi")}

    assert not stubs - modules, (
        "type stubs with no generated module beside them: "
        + ", ".join(sorted(stubs - modules))
    )

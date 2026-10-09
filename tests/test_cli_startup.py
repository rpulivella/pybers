#!/usr/bin/env python3
"""\
What the command line loads before it does any work, checked in a fresh interpreter.

UPDATES
2026-10-09  Written for PYB-181.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/09"

import subprocess
import sys

import pytest

loadedProtobufProbe: str = """\
import sys
from pybers.cli import main
sys.argv = ["pybers", *sys.argv[1:]]
try:
    main()
except SystemExit:
    pass
print(*sorted(
    name for name in sys.modules
    if name.startswith(("google.protobuf", "pybers._generated"))
))
"""


def listLoadedProtobufModules(*arguments: str) -> list[str]:
    """Run the command in a fresh interpreter and return the protobuf modules loaded."""
    result = subprocess.run(
        [sys.executable, "-c", loadedProtobufProbe, *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()[-1].split()


@pytest.mark.parametrize("arguments", [("--help",), ("check", "--help")])
def testHelpLoadsNoProtobuf(arguments: tuple[str, ...]) -> None:
    assert listLoadedProtobufModules(*arguments) == []


def testProbeSeesProtobufOnceADocumentIsRead() -> None:
    assert "google.protobuf" in listLoadedProtobufModules("check", "missing.numbers")

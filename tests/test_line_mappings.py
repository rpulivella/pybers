#!/usr/bin/env python3
"""\
A line map counted from zero and one counted from one are types mypy keeps apart.

Both answer where a line lands after an edit, and one passed where the other belongs
lands every formula, merge or tile a line away with nothing raised, so the stored
map's methods carry names of their own and mypy refuses the swap.

UPDATES
2026-11-18  Written for PYB-267.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/18"

import re
from pathlib import Path

import mypy.api
import pytest

import pybers

swappedMappings: str = """\
from pybers._engine.remapping import StoredLineMapping
from pybers.addressing.lines import LineMapping, LinesUnchanged
from pybers.table._lines import LineMap


def takeModel(lines: LineMapping) -> None:
    pass


def takeStored(lines: StoredLineMapping) -> None:
    pass


takeModel(LinesUnchanged())
takeStored(LineMap(lines=(0,), count=1))
takeModel(LineMap(lines=(0,), count=1))
takeStored(LinesUnchanged())
"""


def testMypyRefusesEachLineMapWhereTheOtherBelongs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MYPYPATH", str(Path(pybers.__file__).resolve().parent.parent))
    source = tmp_path / "swapped.py"
    source.write_text(swappedMappings)
    report, _, _ = mypy.api.run(
        ["--strict", "--no-incremental", "--cache-dir", str(tmp_path), str(source)]
    )
    refused = re.findall(r"swapped\.py:(\d+): error: Argument 1 to", report)
    assert refused == ["16", "17"], report

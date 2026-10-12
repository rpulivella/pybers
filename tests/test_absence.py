#!/usr/bin/env python3
"""\
The three reasons a value can be missing, each its own value and its own type.

UPDATES
2026-10-12  Written for PYB-190.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/12"

import copy
import pickle
from pathlib import Path

import mypy.api
import pytest

import pybers
from pybers import absence

sentinelNames: tuple[str, ...] = ("NOT_REQUESTED", "UNDETERMINED", "WITHHELD")

mixedUpSentinels: str = """\
import pybers


def readNames(names: tuple[str, ...] | pybers.NOT_REQUESTED) -> None:
    pass


readNames(pybers.UNDETERMINED)
"""


@pytest.mark.parametrize("name", sentinelNames)
def testASentinelPrintsAsItsName(name: str) -> None:
    found = getattr(pybers, name)
    assert (repr(found), str(found)) == (name, name)


@pytest.mark.parametrize("name", sentinelNames)
def testASentinelIsOneObjectWhereverItIsReached(name: str) -> None:
    found = getattr(pybers, name)
    assert found is getattr(absence, name)
    assert copy.deepcopy(found) is found
    assert pickle.loads(pickle.dumps(found)) is found


def testNoSentinelIsNoneOrAnother() -> None:
    found = [getattr(pybers, name) for name in sentinelNames]
    assert all(each is not None for each in found)
    assert len({id(each) for each in found}) == len(found)


def testMypyRejectsOneSentinelWhereAnotherIsExpected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MYPYPATH", str(Path(pybers.__file__).resolve().parent.parent))
    source = tmp_path / "mixed.py"
    source.write_text(mixedUpSentinels)
    report, _, status = mypy.api.run(
        ["--strict", "--no-incremental", "--cache-dir", str(tmp_path), str(source)]
    )
    assert status == 1
    assert 'incompatible type "UNDETERMINED"' in report

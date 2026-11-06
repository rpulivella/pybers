#!/usr/bin/env python3
"""\
The preflight's gates, each reporting how long it took.

UPDATES
2026-11-05  Written for PYB-277.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/05"

import pytest

from tools.workflow import preflight


def testEveryGateIsTimedEvenWhenItCannotRun(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> preflight.GateResult:
        raise preflight.PreflightError("no binary")

    monkeypatch.setitem(preflight.gates, "ruff", refuse)
    result = preflight.runGates(["ruff"])[0]
    assert not result.passed
    assert result.seconds >= 0

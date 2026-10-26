#!/usr/bin/env python3
"""\
Setting a board Status reads it back, because GitHub answers a mutation without errors
even when the board ends up holding something else.

UPDATES
2026-10-26  Taken from wingmate, which found the fault first.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/26"

from typing import Any

import pytest

from tools.workflow.lib import github

coordinates = github.BoardCoordinates(
    "PVT_synthetic", "PVTSSF_synthetic", {"Todo": "todo", "In Progress": "progress"},
)


def patchReadBack(monkeypatch: pytest.MonkeyPatch, boardReads: str) -> None:
    """Answer the mutation with nothing and the read-back with `boardReads`."""
    def request(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if "mutation" in query:
            return {}
        return {"node": {"fieldValueByName": {"name": boardReads}}}
    monkeypatch.setattr(github, "requestGraphql", request)


def testStatusThatLandedPasses(monkeypatch: pytest.MonkeyPatch) -> None:
    patchReadBack(monkeypatch, "In Progress")
    github.setBoardStatus(
        "synthetic-token", coordinates, "PVTI_synthetic", "In Progress"
    )


def testStatusTheBoardDoesNotHoldFailsLoudly(monkeypatch: pytest.MonkeyPatch) -> None:
    patchReadBack(monkeypatch, "Todo")
    with pytest.raises(RuntimeError, match="reads 'Todo'"):
        github.setBoardStatus(
            "synthetic-token", coordinates, "PVTI_synthetic", "In Progress"
        )

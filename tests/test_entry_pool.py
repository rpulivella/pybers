#!/usr/bin/env python3
"""\
The pool through which each reference-counted list of a table keys, claims and releases.

UPDATES
2026-10-29  Written for PYB-278.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/29"

from collections.abc import Callable

import pytest

from pybers._generated import TSTArchives_pb2 as tst
from pybers._persistence.pool import EntryPool, ListEntry
from pybers.errors import WriteError


def writeText(entry: ListEntry, text: str) -> None:
    entry.string = text


def buildPool(spend: Callable[[ListEntry], None] | None = None) -> EntryPool[str]:
    dataList = tst.TableDataList(listType=tst.TableDataList.STRING, nextListID=1)
    return EntryPool(dataList=dataList, noun="string", write=writeText, spend=spend)


def findEntry(pool: EntryPool[str], key: int) -> ListEntry:
    entry = pool.entryFind(key)
    assert entry is not None
    return entry


def testTheSameValueSharesOneEntry() -> None:
    pool = buildPool()

    first = pool.keyFor("Item")
    second = pool.keyFor("Item")

    assert first == second
    assert findEntry(pool, first).refcount == 2


def testASharedEntryIsSplitRatherThanOverwritten() -> None:
    pool = buildPool()
    shared = pool.keyFor("Item")
    pool.keyFor("Item")

    changed = pool.keyFor("Other", previous=shared)

    assert changed != shared
    assert findEntry(pool, shared).string == "Item"
    assert findEntry(pool, shared).refcount == 1


def testAnEntryOnlyOneCellNamesIsRewrittenInPlace() -> None:
    pool = buildPool()
    key = pool.keyFor("Item")

    assert pool.keyFor("Other", previous=key) == key
    assert findEntry(pool, key).string == "Other"


def testAClaimOnAKeyTheListDoesNotHoldIsRefused() -> None:
    pool = buildPool()

    with pytest.raises(WriteError, match="string 7, which its table does not hold"):
        pool.claim(7)

    assert not pool.touched


def testAReleaseNeverCountsBelowZero() -> None:
    pool = buildPool()
    key = pool.keyFor("Item")

    pool.release(key, 3)

    assert findEntry(pool, key).refcount == 0


def testAReleasedEntryStaysShareableUntilTheSaveEnds() -> None:
    pool = buildPool()
    key = pool.keyFor("Item")
    pool.release(key)

    assert pool.keyFor("Item") == key
    assert findEntry(pool, key).refcount == 1


def testASpendHookEmptiesAnEntryReleasedToZero() -> None:
    pool = buildPool(spend=lambda entry: entry.ClearField("string"))
    key = pool.keyFor("Item")

    pool.release(key)

    assert not findEntry(pool, key).HasField("string")
    assert pool.keyFor("Item") != key


def testASpentEntryNoRecordNamesIsRemoved() -> None:
    pool = buildPool()
    key = pool.keyFor("Item")
    pool.release(key)

    assert pool.spentRemove([], lambda _: ()) == {key}
    assert pool.entryFind(key) is None
    assert pool.keyFind("Item") is None

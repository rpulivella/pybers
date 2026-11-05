#!/usr/bin/env python3
"""\
A table's header rows, header columns and footer rows: read, set, moved and saved.

`40-table-bands` maxes every band of `Table 1`, five of each on 19 rows by 11
columns. `20-formula-shapes` holds `Table 2`, ten rows by five columns with one
stored cell at `A1`, and no header or footer.

UPDATES
2026-11-05  At least one row and one column stay outside the headers, as the
            maintainer confirmed in Numbers, for PYB-223.
2026-11-03  Written for PYB-223.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/03"

from pathlib import Path

import pytest

import pybers
from conftest import copyDocument, findDocumentPath
from pybers import TableHeaders


def buildTable(rows: int = 6, cols: int = 4) -> pybers.Table:
    """Return a table a created document holds, with no header or footer."""
    return pybers.create("en_US").sheet().tableAdd("Headers", rows, cols)


def testATableReadsTheHeadersNumbersStores() -> None:
    table = pybers.open(findDocumentPath("40-table-bands")).table("Table 1")
    assert table.headers == TableHeaders(headerRows=5, headerColumns=5, footerRows=5)


def testACreatedTableHasNoHeaderOrFooter() -> None:
    assert buildTable().headers == TableHeaders(0, 0, 0)


def testSettingOneCountKeepsTheOthers() -> None:
    table = buildTable()
    table.headersSet(headerRows=2, headerColumns=1)
    assert table.headersSet(footerRows=1) == TableHeaders(2, 1, 1)
    assert table.headers == TableHeaders(2, 1, 1)


def testAHeaderIsRemovedBySettingItToNone() -> None:
    table = buildTable()
    table.headersSet(headerRows=2)
    assert table.headersSet(headerRows=0) == TableHeaders()


@pytest.mark.parametrize(("counts", "message"), [
    ({"headerRows": 6}, "would make 6 header rows, and Numbers allows at most 5"),
    ({"footerRows": -1}, "footer rows -1 is not one"),
    ({"headerColumns": True}, "header columns True is not one"),
    ({"headerRows": 3, "footerRows": 3}, "would leave no row outside the headers"),
    ({"headerColumns": 4}, "would leave no column outside the headers"),
])
def testHeadersTheTableCannotHoldAreRefusedAndNothingChanges(
    counts: dict[str, int], message: str
) -> None:
    table = buildTable()
    with pytest.raises(pybers.ReferenceError, match=message):
        table.headersSet(**counts)
    assert table.headers == TableHeaders()


def testACellReadFromTheFileIsNotMovedIntoTheHeaders() -> None:
    table = pybers.open(findDocumentPath("20-formula-shapes")).table("Table 2")
    with pytest.raises(pybers.ReferenceError) as raised:
        table.headersSet(headerRows=1)
    assert str(raised.value).startswith(
        "Sheet 1::Table 2::A1 would move into or out of the headers, and it holds a "
        "record read from the file"
    )
    assert table.headers == TableHeaders()


def testAFooterOverLinesHoldingNoRecordIsSetOnATableNumbersSaved(
    tmp_path: Path,
) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    document = pybers.open(working)
    document.table("Table 2").headersSet(footerRows=2)
    document.save()
    assert pybers.open(working).table("Table 2").headers == TableHeaders(footerRows=2)


def testSettingTheHeadersAlreadyThereWritesNothing(tmp_path: Path) -> None:
    working = copyDocument("40-table-bands", tmp_path)
    document = pybers.open(working)
    table = document.table("Table 1")
    assert table.headersSet(headerRows=5) == table.headers
    document.save(tmp_path / "saved.numbers")
    reread = pybers.open(tmp_path / "saved.numbers").table("Table 1")
    assert reread.headers == TableHeaders(5, 5, 5)


def testACreatedTablesHeadersSurviveASave(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    document.sheet().tableAdd("Headers", 6, 4).headersSet(
        headerRows=1, headerColumns=2, footerRows=1
    )
    document.save(tmp_path / "headed.numbers")
    reread = pybers.open(tmp_path / "headed.numbers").table("Headers")
    assert reread.headers == TableHeaders(1, 2, 1)


@pytest.mark.parametrize(("edit", "headers"), [
    (lambda table: table.rowAdd(2), TableHeaders(3, 1, 1)),
    (lambda table: table.rowAdd(1), TableHeaders(3, 1, 1)),
    (lambda table: table.rowAdd(3), TableHeaders(2, 1, 1)),
    (lambda table: table.rowAdd(6), TableHeaders(2, 1, 2)),
    (lambda table: table.rowAdd(7), TableHeaders(2, 1, 2)),
    (lambda table: table.rowRemove(2), TableHeaders(1, 1, 1)),
    (lambda table: table.rowRemove(6), TableHeaders(2, 1, 0)),
    (lambda table: table.columnAdd(1), TableHeaders(2, 2, 1)),
    (lambda table: table.columnRemove(1), TableHeaders(2, 0, 1)),
    (lambda table: table.columnAdd(3), TableHeaders(2, 1, 1)),
])
def testAStructuralEditMovesTheHeadersAsNumbersDoes(
    edit: object, headers: TableHeaders
) -> None:
    table = buildTable()
    table.headersSet(headerRows=2, headerColumns=1, footerRows=1)
    edit(table)  # type: ignore[operator]
    assert table.headers == headers


def testBandsMayLeaveExactlyOneRowAndOneColumnOutside() -> None:
    table = pybers.create("en_US").sheet().tableAdd("Headers", 8, 4)
    assert table.headersSet(headerRows=3, headerColumns=3, footerRows=4) == (
        TableHeaders(3, 3, 4)
    )


def testRemovingTheLastRowOutsideTheBandsIsRefused() -> None:
    table = buildTable(4, 3)
    table.headersSet(headerRows=1, footerRows=2)
    with pytest.raises(pybers.ReferenceError) as raised:
        table.rowRemove(2)
    assert str(raised.value) == (
        "Removing 1 row at 2 from 'Headers' would leave no row outside the headers "
        "and footers, and Numbers keeps at least one."
    )
    assert table.rowCount == 4


def testAnEditGrowingABandPastFiveIsRefusedAsNumbersRefusesIt() -> None:
    table = buildTable(8, 2)
    table.headersSet(headerRows=5)
    with pytest.raises(pybers.ReferenceError) as raised:
        table.rowAdd(2)
    assert str(raised.value) == (
        "Adding 1 row at 2 to 'Headers' would make 6 header rows, and Numbers allows "
        "at most 5."
    )
    assert (table.rowCount, table.headers) == (8, TableHeaders(headerRows=5))


def testTheJsonFormCarriesTheBands() -> None:
    table = buildTable()
    table.headersSet(headerRows=1, footerRows=2)
    form = pybers.formatJsonForm(table)
    assert '"headers": {\n      "headerRows": 1,' in form
    reread = pybers.parseJsonForm(form)
    assert isinstance(reread, pybers.Table)
    assert reread.headers == table.headers


def testAScriptSelectsTheHeaderItSet() -> None:
    table = buildTable(4, 3)
    table.headersSet(headerRows=1)
    assert [str(each.address) for each in table.select(":header")] == [
        "A1", "B1", "C1"
    ]

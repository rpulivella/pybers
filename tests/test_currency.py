#!/usr/bin/env python3
"""\
A currency amount, read from a cell, a formula and a custom format, and written back.

`12-number-currency` holds dollars, euros and accounting style, and
`89-currency-formats`, the golden's source, holds the same formats labeled with what was
typed. `86-custom-text-and-currency` holds a custom format with a Currency token, and
`88-formula-currency-results` the results of formulas over a euro and a dollar amount.

UPDATES
2026-10-22  Written for PYB-220.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/22"

import re
from decimal import Decimal
from pathlib import Path

import pytest
from test_cell_value_kinds import openFirstTable, readFormatEntry, writeAndReopen
from test_cli_set import runSetCommand
from test_writer import listArchiveDifferences, readRecordAt

import pybers
from conftest import copyDocument, findDocumentPath
from pybers import CurrencyAmount, CurrencyError, currencies, findCurrency
from pybers._persistence import readPackage
from pybers.table.series import findSeriesContinuation

sourceRoot: Path = Path(__file__).resolve().parent.parent / "src" / "pybers"
goldenDirectory: Path = Path(__file__).resolve().parent / "golden"
goldenName: str = "12-currency-written-by-pybers"


def readFirstTable(stem: str) -> pybers.Table:
    """Return the first table of a document as a fresh read finds it."""
    return openFirstTable(findDocumentPath(stem))[1]


# ── AC 1: one home for the currencies ───────────────────────────────────────


def testTheThirtySevenCurrenciesNumbersOffersAreListedOnce() -> None:
    codes = [currency.code for currency in currencies]
    assert len(codes) == 37
    assert len(set(codes)) == 37
    assert all(re.fullmatch(r"[A-Z]{3}", code) for code in codes)
    assert findCurrency("EUR").name == "Euro"


def testACurrencyNumbersDoesNotOfferIsRefusedNamingThoseItDoes() -> None:
    with pytest.raises(CurrencyError, match="It offers AED, ARS"):
        findCurrency("XYZ")


# ── AC 4 and 6: no second table, and no rates ───────────────────────────────


def testNoOtherModuleCarriesATableOfCurrencyCodes() -> None:
    codes = {currency.code for currency in currencies}
    for path in sourceRoot.rglob("*.py"):
        if path.name == "currency.py" or "_generated" in path.parts:
            continue
        named = {code for code in codes if f'"{code}"' in path.read_text()}
        assert len(named) < 3, f"{path} names {sorted(named)}"


def testTheCurrencyModuleHoldsNoExchangeRate() -> None:
    from pybers import currency

    assert not [name for name in dir(currency) if "rate" in name.casefold()]
    with pytest.raises(CurrencyError):
        CurrencyAmount(Decimal(1), "EUR") + CurrencyAmount(Decimal(1), "USD")


# ── AC 9: arithmetic within one currency ────────────────────────────────────


def testAmountsInOneCurrencyAddSubtractAndCompare() -> None:
    euros = CurrencyAmount(Decimal("1234.5"), "EUR")
    ten = CurrencyAmount(Decimal("10"), "EUR")
    assert euros + ten == CurrencyAmount(Decimal("1244.5"), "EUR")
    assert euros - ten == CurrencyAmount(Decimal("1224.5"), "EUR")
    assert euros > ten
    assert sorted([euros, ten]) == [ten, euros]


def testAnAmountMultipliesAndDividesByANumber() -> None:
    euros = CurrencyAmount(Decimal("1234.5"), "EUR")
    assert euros * 2 == 2 * euros == CurrencyAmount(Decimal("2469.0"), "EUR")
    assert euros / 2 == CurrencyAmount(Decimal("617.25"), "EUR")
    assert -euros == CurrencyAmount(Decimal("-1234.5"), "EUR")


@pytest.mark.parametrize("operation", ["add", "subtract", "compare"])
def testMixingTwoCurrenciesIsRefusedNamingBoth(operation: str) -> None:
    euros = CurrencyAmount(Decimal(5), "EUR")
    dollars = CurrencyAmount(Decimal(5), "USD")
    act = {"add": lambda: euros + dollars, "subtract": lambda: euros - dollars,
           "compare": lambda: euros < dollars}[operation]
    with pytest.raises(CurrencyError, match="EUR and USD"):
        act()


def testAFloatAmountIsRefused() -> None:
    with pytest.raises(CurrencyError, match="float"):
        CurrencyAmount(1.5, "EUR")  # type: ignore[arg-type]


# ── AC 8, 5 and 2: reading ──────────────────────────────────────────────────


def testACurrencyCellReadsAsOneValueWithItsCode() -> None:
    table = readFirstTable("12-number-currency")
    assert table.cell("B1").value == CurrencyAmount(Decimal("1234.5"), "USD")
    assert table.cell("H1").value == CurrencyAmount(Decimal("1234.5"), "EUR")
    assert table.cell("A1").value == Decimal("1234.5")


def testACustomFormatHoldingACurrencyTokenReadsAsCurrency() -> None:
    table = readFirstTable("86-custom-text-and-currency")
    assert table.cell("D1").value == CurrencyAmount(Decimal("1234.5"), "EUR")
    assert table.cell("E1").value == CurrencyAmount(Decimal("1234.5"), "JPY")


def testAFormulasCurrencyResultReadsAsTheAmountItCameFrom() -> None:
    table = readFirstTable("88-formula-currency-results")
    euros = table.cell("A1").value
    assert isinstance(euros, CurrencyAmount)
    assert table.cell("C1").value == euros * 2
    assert table.cell("D1").value == euros * 2
    assert table.cell("E1").value == Decimal("1244.5")


# ── AC 8: writing ───────────────────────────────────────────────────────────


def testWritingACurrencyAmountSetsTheAmountAndItsCurrency(tmp_path: Path) -> None:
    working = copyDocument("12-number-currency", tmp_path)
    cell = writeAndReopen(working, "A1", CurrencyAmount(Decimal("99.5"), "CHF"))
    assert cell.value == CurrencyAmount(Decimal("99.5"), "CHF")
    entry = readFormatEntry(working, "A1").format
    assert (entry.format_type, entry.currency_code, entry.decimal_places) == (
        257, "CHF", 2
    )


def testAWrittenAmountCarriesTheBitsAFormattedAmountDoes(tmp_path: Path) -> None:
    working = copyDocument("12-number-currency", tmp_path)
    writeAndReopen(working, "A1", CurrencyAmount(Decimal("99.5"), "CHF"))
    raw = readRecordAt(working, "A1").raw
    assert (raw[1], raw[6] & 0x02, raw[7] & 0x08) == (10, 0x02, 0x08)


def testANewCurrencyKeepsTheFormatsOtherSettings(tmp_path: Path) -> None:
    working = copyDocument("12-number-currency", tmp_path)
    assert readFormatEntry(working, "D1").format.use_accounting_style
    cell = writeAndReopen(working, "D1", CurrencyAmount(Decimal("7"), "EUR"))
    assert cell.value == CurrencyAmount(Decimal("7"), "EUR")
    entry = readFormatEntry(working, "D1").format
    assert (entry.currency_code, entry.use_accounting_style) == ("EUR", True)


def testANumberWrittenIntoACurrencyCellKeepsItsCurrency(tmp_path: Path) -> None:
    working = copyDocument("12-number-currency", tmp_path)
    cell = writeAndReopen(working, "B1", Decimal("12.5"))
    assert cell.value == CurrencyAmount(Decimal("12.5"), "USD")


def testACurrencyNumbersDoesNotOfferIsRefusedOnWrite(tmp_path: Path) -> None:
    _, table = openFirstTable(copyDocument("12-number-currency", tmp_path))
    with pytest.raises(pybers.WriteError, match="not a currency Numbers offers"):
        table.cell("A1").value = CurrencyAmount(Decimal(1), "XYZ")


def testACustomFormatsCurrencyIsNotChangedSilently(tmp_path: Path) -> None:
    working = copyDocument("86-custom-text-and-currency", tmp_path)
    document, table = openFirstTable(working)
    table.cell("D1").value = CurrencyAmount(Decimal(1), "USD")
    with pytest.raises(pybers.WriteError, match="custom format"):
        document.save()


# ── AC 7: the document's locale ─────────────────────────────────────────────


def testASymbolAndItsPlacementComeFromTheDocumentsLocale() -> None:
    american = pybers.open(findDocumentPath("82-currencies"))
    italian = pybers.open(findDocumentPath("72b-date-time-zones-region"))
    assert (american.currencySymbolFind("JPY"), american.currencyPattern) == (
        "¥", "¤#,##0.00"
    )
    assert (italian.currencySymbolFind("JPY"), italian.currencyPattern) == (
        "JP¥", "#,##0.00\xa0¤"
    )
    assert american.currencySymbolFind("SEK") is None


# ── Both consumers ──────────────────────────────────────────────────────────


def testAScriptTotalsACurrencyColumn() -> None:
    table = readFirstTable("12-number-currency")
    dollars = [table.cell(address).value for address in ("B1", "C1", "D1")]
    assert sum(dollars[1:], dollars[0]) == CurrencyAmount(Decimal("3703.5"), "USD")


def testTheCommandLineWritesAndReportsACurrencyAmount(tmp_path: Path) -> None:
    working = copyDocument("20-formula-shapes", tmp_path)
    result = runSetCommand(str(working), "Table 2::B2", "1234.5 EUR", "--in-place")
    assert result.exit_code == 0
    assert "After: 1234.5 EUR (currency)" in result.stdout
    cell = pybers.open(working).cell("Table 2::B2")
    assert cell.value == CurrencyAmount(Decimal("1234.5"), "EUR")


def testAFillContinuesAmountsInOneCurrency() -> None:
    seeds = [CurrencyAmount(Decimal(1), "EUR"), CurrencyAmount(Decimal(2), "EUR")]
    continuation = findSeriesContinuation(seeds)
    assert continuation is not None
    assert continuation(4) == CurrencyAmount(Decimal(5), "EUR")


# ── The golden ──────────────────────────────────────────────────────────────

# Each written value, and the label below it saying what was written, so the golden
# labels its own contents as a measurement does.
goldenWrites: tuple[tuple[str, Decimal | CurrencyAmount | str], ...] = (
    ("A1", CurrencyAmount(Decimal("99.5"), "CHF")),
    ("A2", "written by pybers as 99.5 CHF over the plain number 1234.5"),
    ("B1", Decimal("12.5")),
    ("B2", "written by pybers as the number 12.5 into dollars, nothing else chosen"),
    ("D1", CurrencyAmount(Decimal("7"), "EUR")),
    ("D2", "written by pybers as 7 EUR over dollars, separator, accounting style"),
    ("J1", CurrencyAmount(Decimal("1000"), "GBP")),
    ("J2", "written by pybers as 1000 GBP into a cell holding nothing"),
)


def writeCurrencyGolden(into: Path) -> Path:
    """Write the golden's mutation into a fresh copy of its fixture, and return it."""
    working = copyDocument("89-currency-formats", into)
    document, table = openFirstTable(working)
    for address, value in goldenWrites:
        table.cell(address).value = value
    document.save()
    return working


def testTheCurrencyGoldenMatchesWhatThisLibraryProduces(tmp_path: Path) -> None:
    golden = goldenDirectory / f"{goldenName}.numbers"
    assert golden.is_file(), f"{golden.name} is missing; see the golden README"
    differences = listArchiveDifferences(
        readPackage(golden), readPackage(writeCurrencyGolden(tmp_path))
    )
    assert not differences, "\n  ".join(differences)


def testTheCurrencyGoldensExpectationsAreGeneratedNotWritten() -> None:
    from tools.local.lib.golden_confirm import buildExpectedToml

    golden = goldenDirectory / f"{goldenName}.numbers"
    expected = golden.with_name(f"{goldenName}.expected.toml")
    assert expected.read_text() == buildExpectedToml(golden)

#!/usr/bin/env python3
"""Currency: the currencies Numbers offers, and an amount carrying its own currency.

Numbers stores a currency amount as an ordinary decimal128 under type byte 10, and its
currency in the format the cell names, never in the value. A `CurrencyAmount` joins the
two for a caller. See findings-11-formats.md.

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

import functools
import re
from dataclasses import dataclass
from decimal import Decimal

from pybers.errors import PybersError


class CurrencyError(PybersError, ValueError):
    """A currency Numbers does not offer, or an operation mixing two currencies."""


@dataclass(frozen=True, slots=True)
class Currency:
    """One currency Numbers offers, by its ISO 4217 code and its English name."""

    code: str
    name: str


# The Currency menu and the Currency token list these, in this order, in Numbers 15.4.
currencies: tuple[Currency, ...] = (
    Currency("AUD", "Australian Dollar"),
    Currency("CAD", "Canadian Dollar"),
    Currency("HKD", "Hong Kong Dollar"),
    Currency("SGD", "Singapore Dollar"),
    Currency("TWD", "New Taiwan Dollar"),
    Currency("USD", "US Dollar"),
    Currency("EUR", "Euro"),
    Currency("CHF", "Swiss Franc"),
    Currency("SEK", "Swedish Krona"),
    Currency("DKK", "Danish Krone"),
    Currency("NOK", "Norwegian Krone"),
    Currency("MXN", "Mexican Peso"),
    Currency("GBP", "British Pound"),
    Currency("BRL", "Brazilian Real"),
    Currency("INR", "Indian Rupee"),
    Currency("KRW", "South Korean Won"),
    Currency("JPY", "Japanese Yen"),
    Currency("CNY", "Chinese Yuan"),
    Currency("IDR", "Indonesian Rupiah"),
    Currency("RUB", "Russian Ruble"),
    Currency("TRY", "Turkish Lira"),
    Currency("THB", "Thai Baht"),
    Currency("PLN", "Polish Zloty"),
    Currency("ZAR", "South African Rand"),
    Currency("ARS", "Argentine Peso"),
    Currency("SAR", "Saudi Riyal"),
    Currency("AED", "United Arab Emirates Dirham"),
    Currency("EGP", "Egyptian Pound"),
    Currency("HRK", "Croatian Kuna"),
    Currency("CZK", "Czech Koruna"),
    Currency("ILS", "Israeli New Shekel"),
    Currency("HUF", "Hungarian Forint"),
    Currency("RON", "Romanian Leu"),
    Currency("UAH", "Ukrainian Hryvnia"),
    Currency("VND", "Vietnamese Dong"),
    Currency("MYR", "Malaysian Ringgit"),
    Currency("NZD", "New Zealand Dollar"),
)

currencyCodes: frozenset[str] = frozenset(each.code for each in currencies)

# A document may hold a currency the menu does not offer, so a value takes any ISO code.
isoCodePattern: re.Pattern[str] = re.compile(r"[A-Z]{3}")


def findCurrency(code: str) -> Currency:
    """Return the currency Numbers offers under an ISO 4217 code, refusing any other."""
    for each in currencies:
        if each.code == code:
            return each
    raise CurrencyError(
        f"{code!r} is not a currency Numbers offers. It offers "
        f"{', '.join(sorted(currencyCodes))}."
    )


@functools.total_ordering
@dataclass(frozen=True, slots=True)
class CurrencyAmount:
    """An exact amount in one currency, which adds and compares only with its own.

    A `float` amount is refused, since it carries binary rounding error.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount, bool) or not isinstance(self.amount, Decimal | int):
            raise CurrencyError(
                f"An amount is a Decimal, and {self.amount!r} is a "
                f"{type(self.amount).__name__}."
            )
        object.__setattr__(self, "amount", Decimal(self.amount))
        code = self.currency
        if not isinstance(code, str) or not isoCodePattern.fullmatch(code):
            raise CurrencyError(
                f"A currency is an ISO 4217 code such as 'EUR', not {code!r}."
            )

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"

    def _currencyMatchCheck(self, other: CurrencyAmount, operation: str) -> None:
        """Refuse to combine two currencies, since no rate converts between them."""
        if other.currency != self.currency:
            raise CurrencyError(
                f"Cannot {operation} {self} and {other}: {self.currency} and "
                f"{other.currency} are different currencies."
            )

    def __add__(self, other: object) -> CurrencyAmount:
        if not isinstance(other, CurrencyAmount):
            return NotImplemented
        self._currencyMatchCheck(other, "add")
        return CurrencyAmount(self.amount + other.amount, self.currency)

    def __sub__(self, other: object) -> CurrencyAmount:
        if not isinstance(other, CurrencyAmount):
            return NotImplemented
        self._currencyMatchCheck(other, "subtract")
        return CurrencyAmount(self.amount - other.amount, self.currency)

    def __mul__(self, factor: object) -> CurrencyAmount:
        if isinstance(factor, bool) or not isinstance(factor, Decimal | int):
            return NotImplemented
        return CurrencyAmount(self.amount * factor, self.currency)

    __rmul__ = __mul__

    def __truediv__(self, divisor: object) -> CurrencyAmount:
        if isinstance(divisor, bool) or not isinstance(divisor, Decimal | int):
            return NotImplemented
        return CurrencyAmount(self.amount / divisor, self.currency)

    def __neg__(self) -> CurrencyAmount:
        return CurrencyAmount(-self.amount, self.currency)

    def __abs__(self) -> CurrencyAmount:
        return CurrencyAmount(abs(self.amount), self.currency)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CurrencyAmount):
            return NotImplemented
        self._currencyMatchCheck(other, "compare")
        return self.amount < other.amount


__all__ = [
    "Currency",
    "CurrencyAmount",
    "CurrencyError",
    "currencies",
    "currencyCodes",
    "findCurrency",
]

#!/usr/bin/env python3
"""\
A region's formatting symbols, read from macOS's own ICU as Numbers reads them.

Numbers fills `TSK.FormattingSymbolsArchive` from the ICU in `libicucore`, CLDR with
Apple's tailoring, and from two Foundation values: CoreFoundation's version number,
written as `version`, and `NSNumberFormatter`'s positive infinity symbol. Composed
this way, all 48 fields match what Numbers wrote in each of the eight regions
`findings-12-language-and-region.md` measures.

A currency's symbol is listed only where the region's differs from its ISO code, as
Numbers lists them, which is why `en_AU` holds five and `de_DE` twenty-six.

Reads the libraries through `ctypes` and runs nothing else. macOS only.

UPDATES
2026-10-28  Written for PYB-272.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/28"

import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

frameworks: Path = Path("/System/Library/Frameworks")
icuPath: Path = Path("/usr/lib/libicucore.A.dylib")
coreFoundationPath: Path = frameworks / "CoreFoundation.framework" / "CoreFoundation"
foundationPath: Path = frameworks / "Foundation.framework" / "Foundation"
objectiveCPath: Path = Path("/usr/lib/libobjc.A.dylib")

# The languages Numbers' Language menu offers, measured in Numbers 15.4. Chinese is
# left out until a measurement shows how Numbers writes its script subtag.
menuLanguages: frozenset[str] = frozenset({
    "ar", "ca", "cs", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "hr",
    "hu", "id", "it", "ja", "ko", "ms", "nb", "nl", "pl", "pt", "ro", "ru", "sk",
    "sv", "th", "tr", "uk", "vi",
})

# ICU's enumerations, from unicode/udat.h, unumberformat.h and ucurr.h.
dateStyles: dict[str, int] = {"short": 3, "medium": 2, "long": 1, "full": 0}
dateStyleNone: int = -1
nameKinds: dict[str, int] = {
    "months": 1, "standalone_months": 10, "short_months": 2,
    "standalone_short_months": 11, "weekdays": 3, "standalone_weekdays": 13,
    "short_weekdays": 4, "standalone_short_weekdays": 14, "tiny_months": 8,
    "standalone_tiny_months": 12, "tiny_weekdays": 9, "standalone_tiny_weekdays": 15,
    "quarters": 16, "standalone_quarters": 18, "short_quarters": 17,
    "standalone_short_quarters": 19, "eras": 0, "long_eras": 7,
}
# The weekday kinds, whose names ICU counts from one, Sunday.
weekdayKinds: frozenset[int] = frozenset({3, 4, 9, 13, 14, 15})
amPmKind: int = 5
numberSymbols: dict[str, int] = {
    "decimal_separator": 0, "grouping_separator": 1,
    "currency_decimal_separator": 10, "currency_grouping_separator": 17,
    "plus_sign": 7, "minus_sign": 6, "exponential_symbol": 11, "percent_symbol": 3,
    "per_mille_symbol": 12, "nan_symbol": 15,
}
numberStyles: dict[str, int] = {
    "decimal_pattern": 1, "scientific_pattern": 4, "percent_pattern": 3,
    "currency_pattern": 2,
}
decimalStyle: int = 1
currencyStyle: int = 2
# ICU's number format attributes, from unumberformat.h.
maximumFractionDigits: int = 6
minimumFractionDigits: int = 7
minimumGroupingDigits: int = 22
allCurrencyKinds: int = 0x7FFFFFFF
symbolName: int = 0
bufferLength: int = 1024
# CoreFoundation's UTF-8 encoding, from CFString.h.
utf8Encoding: int = 0x08000100

pointer, number, text = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
status: Any = ctypes.POINTER(ctypes.c_int)
type Signature = tuple[str, Any, tuple[Any, ...]]

icuSignatures: tuple[Signature, ...] = (
    ("udat_open", pointer, (number, number, text, pointer, number, pointer, number,
                            status)),
    ("udat_toPattern", number, (pointer, ctypes.c_int8, pointer, number, status)),
    ("udat_getSymbols", number, (pointer, number, number, pointer, number, status)),
    ("udat_countSymbols", number, (pointer, number)),
    ("udat_close", None, (pointer,)),
    ("unum_open", pointer, (number, pointer, number, text, pointer, status)),
    ("unum_toPattern", number, (pointer, ctypes.c_int8, pointer, number, status)),
    ("unum_getSymbol", number, (pointer, number, pointer, number, status)),
    ("unum_close", None, (pointer,)),
    ("unum_setAttribute", None, (pointer, number, number)),
    ("unum_formatDouble", number, (pointer, ctypes.c_double, pointer, number, pointer,
                                   status)),
    ("ucurr_forLocale", number, (text, pointer, number, status)),
    ("ucurr_openISOCurrencies", pointer, (ctypes.c_uint32, status)),
    ("ucurr_getName", pointer, (pointer, text, number, ctypes.POINTER(ctypes.c_int8),
                                status, status)),
    ("uenum_next", text, (pointer, status, status)),
    ("uenum_close", None, (pointer,)),
    ("unumsys_open", pointer, (text, status)),
    ("unumsys_getName", text, (pointer,)),
    ("unumsys_close", None, (pointer,)),
    ("uloc_countAvailable", number, ()),
    ("uloc_getAvailable", text, (number,)),
    ("u_getVersion", None, (pointer,)),
    ("ulocdata_getCLDRVersion", None, (pointer, status)),
)
foundationSignatures: tuple[Signature, ...] = (
    ("CFStringCreateWithCString", pointer, (pointer, text, ctypes.c_uint32)),
    ("CFStringGetCString", ctypes.c_bool, (pointer, text, number, ctypes.c_uint32)),
    ("CFRelease", None, (pointer,)),
)
objectiveCSignatures: tuple[Signature, ...] = (
    ("objc_getClass", pointer, (text,)),
    ("sel_registerName", pointer, (text,)),
    ("objc_autoreleasePoolPush", pointer, ()),
    ("objc_autoreleasePoolPop", None, (pointer,)),
)

type Field = str | tuple[str, ...] | tuple[tuple[str, str], ...]


class IcuError(RuntimeError):
    """ICU could not be read, or refused a call, on this machine."""


@dataclass(frozen=True, slots=True)
class IcuVersions:
    """The versions of the data a table is read from."""

    icu: str
    cldr: str
    coreFoundation: str


def assignSignatures(library: ctypes.CDLL, signatures: tuple[Signature, ...]) -> None:
    """Give each call a library exports its result and argument types."""
    for name, result, arguments in signatures:
        call = getattr(library, name)
        call.restype, call.argtypes = result, list(arguments)


class Icu:
    """macOS's ICU and Foundation, opened once, with the calls a table needs."""

    def __init__(self) -> None:
        """Open the libraries and declare each call's signature."""
        try:
            self.library = ctypes.CDLL(str(icuPath))
            self.foundation = ctypes.CDLL(str(coreFoundationPath))
            # Loaded for its classes, which the Objective-C runtime finds by name.
            ctypes.CDLL(str(foundationPath))
            self.objectiveC = ctypes.CDLL(str(objectiveCPath))
        except OSError as exc:
            raise IcuError(f"macOS's ICU could not be opened: {exc}.") from exc
        assignSignatures(self.library, icuSignatures)
        assignSignatures(self.foundation, foundationSignatures)
        assignSignatures(self.objectiveC, objectiveCSignatures)
        self.currencies = self.currenciesList()

    def textRead(self, call: Any, *arguments: object) -> str:
        """Return the UTF-16 text an ICU call writes after its own arguments."""
        buffer = (ctypes.c_uint16 * bufferLength)()
        failure = ctypes.c_int(0)
        length: int = call(*arguments, ctypes.addressof(buffer), bufferLength,
                           ctypes.byref(failure))
        if failure.value > 0:
            raise IcuError(f"ICU refused {call.__name__} with status {failure.value}.")
        return ctypes.string_at(buffer, 2 * length).decode("utf-16-le")

    def versionsRead(self) -> IcuVersions:
        """Return the ICU, CLDR and CoreFoundation versions this Mac carries."""
        icu, cldr = (ctypes.c_uint8 * 4)(), (ctypes.c_uint8 * 4)()
        self.library.u_getVersion(ctypes.addressof(icu))
        self.library.ulocdata_getCLDRVersion(
            ctypes.addressof(cldr), ctypes.byref(ctypes.c_int(0))
        )
        return IcuVersions(
            f"{icu[0]}.{icu[1]}", str(cldr[0]), self.foundationVersionRead()
        )

    def foundationVersionRead(self) -> str:
        """Return CoreFoundation's version number, written as Numbers writes it."""
        value = ctypes.c_double.in_dll(
            self.foundation, "kCFCoreFoundationVersionNumber"
        ).value
        return f"{value:.2f}"

    def infinitySymbolRead(self, identifier: str) -> str:
        """Return the positive infinity symbol Foundation's number formatter writes.

        Numbers takes it from `NSNumberFormatter`, which writes `+∞` where ICU and
        CoreFoundation write `∞`, so it is asked through the Objective-C runtime.
        """
        send = self.objectiveC.objc_msgSend
        pool = self.objectiveC.objc_autoreleasePoolPush()
        name = self.foundation.CFStringCreateWithCString(
            None, identifier.encode(), utf8Encoding
        )
        send.restype, send.argtypes = pointer, [pointer, pointer]
        formatter = send(
            self.classFind(b"NSNumberFormatter"), self.selectorFind(b"new")
        )
        send.argtypes = [pointer, pointer, pointer]
        locale = send(self.classFind(b"NSLocale"),
                      self.selectorFind(b"localeWithLocaleIdentifier:"), name)
        send(formatter, self.selectorFind(b"setLocale:"), locale)
        send.argtypes = [pointer, pointer]
        symbol = send(formatter, self.selectorFind(b"positiveInfinitySymbol"))
        buffer = ctypes.create_string_buffer(64)
        self.foundation.CFStringGetCString(symbol, buffer, len(buffer), utf8Encoding)
        send(formatter, self.selectorFind(b"release"))
        self.foundation.CFRelease(name)
        self.objectiveC.objc_autoreleasePoolPop(pool)
        return buffer.value.decode()

    def classFind(self, name: bytes) -> int:
        """Return an Objective-C class by name."""
        found: int = self.objectiveC.objc_getClass(name)
        return found

    def selectorFind(self, name: bytes) -> int:
        """Return an Objective-C selector by name."""
        found: int = self.objectiveC.sel_registerName(name)
        return found

    def localesList(self) -> list[str]:
        """Return the regions offered: each locale with a region, in a menu language."""
        found = []
        for position in range(self.library.uloc_countAvailable()):
            identifier = self.library.uloc_getAvailable(position).decode()
            language, _, region = identifier.partition("_")
            if language in menuLanguages and len(region) == 2 and region.isupper():
                found.append(identifier)
        return sorted(found)

    def currenciesList(self) -> list[str]:
        """Return every ISO currency code ICU knows, current or historic, sorted."""
        failure = ctypes.c_int(0)
        listing = self.library.ucurr_openISOCurrencies(
            allCurrencyKinds, ctypes.byref(failure)
        )
        codes = set()
        while code := self.library.uenum_next(
            listing, ctypes.byref(ctypes.c_int(0)), ctypes.byref(failure)
        ):
            codes.add(code.decode())
        self.library.uenum_close(listing)
        return sorted(codes)

    def currencySymbolRead(self, code: str, locale: bytes) -> str:
        """Return the symbol a region writes a currency with."""
        units = (ctypes.c_uint16 * 4)(*(ord(each) for each in code), 0)
        length, failure = ctypes.c_int(0), ctypes.c_int(0)
        found = self.library.ucurr_getName(
            ctypes.addressof(units), locale, symbolName,
            ctypes.byref(ctypes.c_int8(0)), ctypes.byref(length), ctypes.byref(failure),
        )
        return ctypes.string_at(found, 2 * length.value).decode("utf-16-le")

    def dateFormatOpen(self, locale: bytes, time: int, date: int) -> int:
        """Return an ICU date format for a region and the two styles."""
        failure = ctypes.c_int(0)
        found: int = self.library.udat_open(
            time, date, locale, None, 0, None, 0, ctypes.byref(failure)
        )
        if failure.value > 0:
            raise IcuError(f"ICU opened no date format for {locale.decode()}.")
        return found

    def patternRead(self, locale: bytes, time: int, date: int) -> str:
        """Return the pattern a date or time style writes in a region."""
        handle = self.dateFormatOpen(locale, time, date)
        pattern = self.textRead(self.library.udat_toPattern, handle, 0)
        self.library.udat_close(handle)
        return pattern

    def namesRead(self, handle: int, kind: int) -> tuple[str, ...]:
        """Return the names of one kind, weekdays counted from Sunday."""
        first = 1 if kind in weekdayKinds else 0
        return tuple(
            self.textRead(self.library.udat_getSymbols, handle, kind, position)
            for position in range(first, self.library.udat_countSymbols(handle, kind))
        )

    def numberFormatOpen(self, locale: bytes, style: int) -> int:
        """Return an ICU number format for a region and a style."""
        failure = ctypes.c_int(0)
        found: int = self.library.unum_open(
            style, None, 0, locale, None, ctypes.byref(failure)
        )
        if failure.value > 0:
            raise IcuError(f"ICU opened no number format for {locale.decode()}.")
        return found

    def numberPatternRead(self, locale: bytes, style: int) -> str:
        """Return the pattern a number style writes in a region."""
        handle = self.numberFormatOpen(locale, style)
        pattern = self.textRead(self.library.unum_toPattern, handle, 0)
        self.library.unum_close(handle)
        return pattern

    def valueFormat(
        self, identifier: str, value: float, style: int, fractionDigits: int
    ) -> str:
        """Return a number as a region shows it in a style, to a count of decimals."""
        handle = self.numberFormatOpen(identifier.encode(), style)
        for attribute in (minimumFractionDigits, maximumFractionDigits):
            self.library.unum_setAttribute(handle, attribute, fractionDigits)
        # Numbers groups a four-digit number where CLDR's minimum grouping would not.
        self.library.unum_setAttribute(handle, minimumGroupingDigits, 1)
        buffer = (ctypes.c_uint16 * bufferLength)()
        failure = ctypes.c_int(0)
        # A field position sits between the buffer and the status, unlike other calls.
        length = self.library.unum_formatDouble(
            handle, value, ctypes.addressof(buffer), bufferLength, None,
            ctypes.byref(failure),
        )
        self.library.unum_close(handle)
        if failure.value > 0:
            raise IcuError(f"ICU could not format {value} for {identifier}.")
        return ctypes.string_at(buffer, 2 * length).decode("utf-16-le")

    def numberingSystemRead(self, locale: bytes) -> str:
        """Return the digits a region writes, `latn` for 0 to 9."""
        failure = ctypes.c_int(0)
        handle = self.library.unumsys_open(locale, ctypes.byref(failure))
        name: str = self.library.unumsys_getName(handle).decode()
        self.library.unumsys_close(handle)
        return name

    def symbolsCompose(self, identifier: str) -> dict[str, Field]:
        """Return every field of a region's formatting symbols, keyed by its name."""
        locale = identifier.encode()
        found: dict[str, Field] = {
            "version": self.foundationVersionRead(),
            "calendar": "gregorian",
            "numbering_system": self.numberingSystemRead(locale),
        }
        names = self.dateFormatOpen(locale, dateStyleNone, dateStyles["short"])
        for field, kind in nameKinds.items():
            found[field] = self.namesRead(names, kind)
        found["am_symbol"], found["pm_symbol"] = self.namesRead(names, amPmKind)
        self.library.udat_close(names)
        for style, value in dateStyles.items():
            found[f"{style}_date_pattern"] = self.patternRead(
                locale, dateStyleNone, value
            )
            found[f"{style}_time_pattern"] = self.patternRead(
                locale, value, dateStyleNone
            )
        symbols = self.numberFormatOpen(locale, decimalStyle)
        for field, symbol in numberSymbols.items():
            found[field] = self.textRead(self.library.unum_getSymbol, symbols, symbol)
        self.library.unum_close(symbols)
        found["infinity_symbol"] = self.infinitySymbolRead(identifier)
        for field, numberStyle in numberStyles.items():
            found[field] = self.numberPatternRead(locale, numberStyle)
        found["currency_code"] = self.textRead(self.library.ucurr_forLocale, locale)
        found["currency_symbols"] = tuple(
            (code, shown) for code in self.currencies
            if (shown := self.currencySymbolRead(code, locale)) != code
        )
        return found


__all__ = [
    "Field",
    "Icu",
    "IcuError",
    "IcuVersions",
    "currencyStyle",
    "decimalStyle",
    "menuLanguages",
]

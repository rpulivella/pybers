#!/usr/bin/env python3
"""\
The decimal128 type: its limits, its 16-byte form, and what it refuses.

Two things are asserted that a round trip through our own codec cannot establish,
because a codec can agree with itself while both halves are wrong. Every one of the
6,091 decimal128 values in the fixture corpus re-encodes to the exact bytes Numbers
wrote, and the decoder is pinned against buffers built by hand from the layout rather
than produced by the encoder.

UPDATES
2026-09-01  Written for #2, when the codec became a type of its own.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

import decimal
from decimal import Decimal
from pathlib import Path

import pytest

from pybers._persistence import readPackage
from pybers._persistence.cells import decodeRow, offsetUnitFor
from pybers._persistence.decimal128 import (
    Decimal128,
    Decimal128Error,
    exponentBias,
    maximumBiasedExponent,
    maximumSignificantDigits,
)

fixtureDirectory: Path = Path(__file__).resolve().parent / "fixtures"

tileTypeId: int = 6002


def everyNumber(path: Path) -> list[tuple[Decimal, bytes]]:
    """Return every decimal128 in a fixture as its value and the bytes it came from."""
    from pybers._generated import TSTArchives_pb2 as tst

    found: list[tuple[Decimal, bytes]] = []
    for iwaFile in readPackage(path).iwaFiles:
        for archive in iwaFile.archives:
            for message in archive.messages:
                if message.typeId != tileTypeId:
                    continue
                tile = tst.Tile()
                tile.ParseFromString(message.data)
                for info in tile.rowInfos:
                    unit = offsetUnitFor(
                        info.has_wide_offsets, tile.should_use_wide_rows
                    )
                    for record in decodeRow(
                        info.cell_offsets, info.cell_storage_buffer, unit
                    ):
                        if isinstance(record.value, Decimal):
                            found.append((record.value, record.raw[12:28]))
    return found


# ── The limits come from the standard library, not from hand arithmetic ──────

def test_theFormatLimitsMatchTheStandardLibrary() -> None:
    """A hand-derived ceiling here was wrong once, so they are derived and pinned.

    `maximumBiasedExponent` was written as 2^14 - 1 on the reasoning that the field
    is fourteen bits wide. A biased exponent above 3 * 2^12 - 1 sets the two selector
    bits and means the other layout, so 1E+7000 encoded without complaint and read
    back as 0E-2624.
    """
    assert maximumSignificantDigits == 34
    assert exponentBias == 6176
    assert maximumBiasedExponent == 12287


# ── Decoding, pinned against buffers built from the layout by hand ───────────

def test_aValueDecodesExactlyRatherThanApproximately() -> None:
    """1234.5 is exact, which is the whole reason values are not floats.

    Built by hand rather than read from a file, so this tests the decoder and not
    the fixture: coefficient 12345 with exponent -1.
    """
    raw = (12345).to_bytes(8, "little") + ((exponentBias - 1) << 49).to_bytes(
        8, "little"
    )
    assert Decimal128.fromBytes(raw).value == Decimal("1234.5")
    assert Decimal128.fromBytes(raw).value != Decimal("1234.4999999999999")


def test_theSignIsTheTopBitRatherThanAField() -> None:
    raw = (12345).to_bytes(8, "little") + (
        (1 << 63) | ((exponentBias - 1) << 49)
    ).to_bytes(8, "little")
    assert Decimal128.fromBytes(raw).value == Decimal("-1234.5")


def test_theLargeCoefficientLayoutReadsAsZero() -> None:
    """The second BID layout decodes, and a non-canonical coefficient is zero.

    Setting both selector bits selects the form whose coefficient carries an implied
    leading `100`, which puts it past the maximum this format may hold. IEEE 754
    calls that non-canonical and gives it the value zero, so this must return a
    number rather than raising, and the number must be zero.
    """
    selector = (0x03 << 61) | (exponentBias << 47)
    raw = (0).to_bytes(8, "little") + selector.to_bytes(8, "little")
    assert Decimal128.fromBytes(raw).value == Decimal(0)


def test_aShortBufferIsRefused() -> None:
    with pytest.raises(Decimal128Error, match="16 bytes"):
        Decimal128.fromBytes(b"\x00" * 8)


@pytest.mark.parametrize("precision", [3, 6, 10, 28, 50])
def test_decodingIgnoresTheCallersDecimalContext(precision: int) -> None:
    """A regression. `scaleb` is arithmetic, so it obeyed the thread-local context.

    Under the default precision of 28 that rounded away the 34 digits decimal128
    can hold, and a caller who had set `prec=6` for their own arithmetic read
    1234567.891 out of a file as 1.23457E+6, with nothing raising. No fixture
    caught it because the most precise value in the whole corpus has 15 digits.
    """
    raw = b"\xd3\x02\x96\x49" + bytes(10) + b"\x3a\x30"
    previous = decimal.getcontext().prec
    decimal.getcontext().prec = precision
    try:
        assert Decimal128.fromBytes(raw).value == Decimal("1234567.891")
    finally:
        decimal.getcontext().prec = previous


def test_allThirtyFourDigitsSurviveADecode() -> None:
    """The format holds 34 significant digits and the decoder returns them all."""
    value = Decimal("3.141592653589793238462643383279502")
    assert len(value.as_tuple().digits) == maximumSignificantDigits
    raw = (((-33 + exponentBias) << 113) | 3141592653589793238462643383279502).to_bytes(
        16, "little"
    )
    assert Decimal128.fromBytes(raw).value == value


# ── Encoding ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    [
        "0", "-0", "1", "-1", "1.50", "0.00", "-0.001", "1234.5678",
        "1E+100", "1E-100", "9999999999999999999999999999999999",
        "-9999999999999999999999999999999999",
        "3.141592653589793238462643383279502",
        # The exact ends of the stored-exponent range. One step past either is
        # refused below, and used to encode silently to a different number.
        "1E+6111", "1E-6176",
    ],
)
def test_aValueRoundTripsThroughItsBytes(text: str) -> None:
    """Identity including trailing zeros, which carry a cell's displayed precision."""
    value = Decimal(text)
    decoded = Decimal128.fromBytes(Decimal128(value).asBytes()).value
    assert decoded == value
    assert str(decoded) == str(value), "the scale changed, so trailing zeros moved"


def test_theEncodedFormIsSixteenBytes() -> None:
    assert len(Decimal128(Decimal("1")).asBytes()) == 16


def test_everyCorpusValueReEncodesToWhatNumbersWrote() -> None:
    """The encoder reproduces Apple's own bytes, not merely a valid encoding.

    Measured on 2026-09-01 over all 6,091 decimal128 values in the fixture corpus.
    That is a far stronger statement than a round trip through our own decoder,
    which could agree with itself while both halves were wrong.
    """
    examined = 0
    for path in sorted(fixtureDirectory.glob("*.numbers")):
        for value, raw in everyNumber(path):
            examined += 1
            assert Decimal128(value).asBytes() == raw, (
                f"{path.name}: {value} did not re-encode to the bytes Numbers wrote"
            )
    assert examined > 5000, f"only {examined} values examined; the corpus shrank"


# ── Refusals, which fire at construction rather than at encode time ──────────

@pytest.mark.parametrize(
    "text, reason",
    [
        ("NaN", "not a finite number"),
        ("Infinity", "not a finite number"),
        ("-Infinity", "not a finite number"),
        ("1" * 35, "significant digits"),
        # One step outside the stored-exponent range at each end. Before the bound
        # was corrected these encoded without complaint, and 1E+7000 read back as
        # 0E-2624, because a biased exponent that high selects the other layout.
        ("1E+6112", "exponent"),
        ("1E-6177", "exponent"),
    ],
)
def test_whatCannotBeRepresentedIsRefused(text: str, reason: str) -> None:
    """Refused rather than rounded or clamped, so a lost digit is never silent."""
    with pytest.raises(Decimal128Error, match=reason):
        Decimal128(Decimal(text))


def test_theRefusalHappensWhenTheValueIsMadeNotWhenItIsWritten() -> None:
    """The reason this is a type. A save cannot fail on a number set hours earlier."""
    with pytest.raises(Decimal128Error):
        Decimal128(Decimal("1" * 40))

#!/usr/bin/env python3
"""\
IEEE-754 decimal128: the type Python does not ship, and its binary interchange form.

Numbers stores every numeric cell as decimal128, so `1234.5` is exact and routing it
through a binary float would introduce rounding error into a document that never had
any. Python has no decimal128. `decimal.Decimal` is arbitrary precision with no fixed
width, and it offers no conversion to or from the 16-byte interchange encoding at all,
so both halves are written here.

What the standard library does provide is `decimal.IEEEContext(128)`, which states the
format's arithmetic rules. Every limit below is derived from it rather than written
out, because a hand-derived limit here was wrong once already: an exponent ceiling of
2^14 - 1 let 1E+7000 encode to a value that read back as 0E-2624.

Its own module because it is not an Apple concept. `pybers.numbersfile.cells` decodes a
layout Apple never published, and this is a published international standard that
happens to be used there.

UPDATES
2026-09-01  Extracted from pybers.numbersfile.cells and given a type, for #2.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/01"

from dataclasses import dataclass
from decimal import Decimal, IEEEContext

# The format's own arithmetic rules, from the standard library rather than restated.
# `prec` is 34 significant digits, `Emax` 6144 and `Emin` -6143.
formatRules = IEEEContext(128)

# The number of decimal digits a coefficient may hold. A value needing more is
# refused rather than rounded, because silently rounding a spreadsheet number is the
# failure this library exists to avoid.
maximumSignificantDigits: int = formatRules.prec

# The largest coefficient the format may hold. Anything above it is non-canonical and
# reads as zero under IEEE 754.
maximumCoefficient: int = 10**maximumSignificantDigits - 1

# The exponent is stored biased so it can be unsigned. The bias is what maps the
# smallest stored exponent, `Emin - (prec - 1)`, onto zero.
exponentBias: int = maximumSignificantDigits - 1 - formatRules.Emin

# The largest biased exponent the common layout can carry. The field is fourteen bits
# wide, but a value whose top two bits are both set selects the other layout instead,
# so the ceiling is the format's own rather than the field's.
maximumBiasedExponent: int = (
    formatRules.Emax - (maximumSignificantDigits - 1) + exponentBias
)

# The encoded width, and the number of bits the coefficient occupies below the
# exponent in the common layout.
encodedLength: int = 16
coefficientBits: int = 113


class Decimal128Error(RuntimeError):
    """A value that decimal128 cannot represent, or bytes that are not one."""


@dataclass(frozen=True, slots=True)
class Decimal128:
    """A `Decimal` that fits IEEE-754 decimal128, together with its 16-byte form.

    The wrapper exists so the format's limits are enforced where the value is made
    rather than where it is written. A `Decimal128` that exists is one that can be
    stored, so a save cannot fail late on a number a caller set hours earlier.

    Frozen, so a value cannot be edited out of range after it has been checked.
    """

    value: Decimal

    def __post_init__(self) -> None:
        """Refuse anything decimal128 cannot hold, naming which limit was passed."""
        sign, digits, exponent = self.value.as_tuple()
        if not isinstance(exponent, int):
            raise Decimal128Error(
                f"{self.value} is not a finite number, and decimal128 as Numbers "
                "uses it has no representation for a NaN or an infinity."
            )
        if len(digits) > maximumSignificantDigits:
            raise Decimal128Error(
                f"{self.value} carries {len(digits)} significant digits, and "
                f"decimal128 holds {maximumSignificantDigits}. Round it yourself if "
                "that is what you intend, so the rounding is yours."
            )
        if not 0 <= exponent + exponentBias <= maximumBiasedExponent:
            raise Decimal128Error(
                f"{self.value} has exponent {exponent}, outside the {-exponentBias} "
                f"to {maximumBiasedExponent - exponentBias} decimal128 can carry."
            )

    @classmethod
    def fromBytes(cls, raw: bytes) -> Decimal128:
        """Decode 16 bytes of little-endian binary-integer decimal128.

        Apple stores the binary-integer (BID) form, which has two layouts selected by
        the two bits below the sign. The common one puts a 14-bit biased exponent at
        bits 126-113 and a 113-bit coefficient below it, and every value in every file
        examined uses it.

        When both selector bits are set the fields move: the exponent sits at bits
        124-111 and the coefficient gains an implied leading `100`. That form can only
        express coefficients of 2^113 or more, already past the maximum this format
        may hold, so a canonical encoder never emits it. It is decoded anyway rather
        than refused, because a reader that rejects a file over a corner the
        specification already defines is worse than one that follows it. Per IEEE 754
        a coefficient beyond the maximum is non-canonical and its value is zero.
        """
        if len(raw) < encodedLength:
            raise Decimal128Error(
                f"decimal128 needs {encodedLength} bytes, got {len(raw)}."
            )
        low = int.from_bytes(raw[:8], "little")
        high = int.from_bytes(raw[8:16], "little")
        negative = (high >> 63) & 1

        if (high >> 61) & 0x03 == 0x03:
            exponent = ((high >> 47) & 0x3FFF) - exponentBias
            coefficient = (0b100 << 111) | ((high & 0x00007FFFFFFFFFFF) << 64) | low
        else:
            exponent = ((high >> 49) & 0x3FFF) - exponentBias
            coefficient = ((high & 0x0001FFFFFFFFFFFF) << 64) | low

        if coefficient > maximumCoefficient:
            coefficient = 0

        # Built from its digit tuple rather than with `scaleb`, which is an arithmetic
        # operation and therefore obeys the caller's thread-local decimal context.
        # Under the default precision of 28 that silently rounded the 34 digits this
        # format holds, and under a caller who had set `prec=6` for their own
        # arithmetic it turned 1234567.891 on disk into 1.23457E+6 with nothing
        # raising. What a file says cannot depend on what the calling program is doing.
        return cls(
            Decimal((negative, tuple(int(d) for d in str(coefficient)), exponent))
        )

    def asBytes(self) -> bytes:
        """Encode as 16 bytes of little-endian binary-integer decimal128.

        Emits only the common layout. The other exists to express coefficients past
        the maximum this format may hold, so a canonical encoder never reaches for it.
        """
        sign, digits, exponent = self.value.as_tuple()
        coefficient = 0
        for digit in digits:
            coefficient = coefficient * 10 + digit
        combined = (
            (sign << 127)
            | ((exponent + exponentBias) << coefficientBits)
            | coefficient
        )
        return combined.to_bytes(encodedLength, "little")

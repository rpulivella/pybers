#!/usr/bin/env python3
"""\
A color: its fields, its text form, its JSON form, and every color the documents hold.

UPDATES
2026-11-06  Written for PYB-264.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/06"

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from google.protobuf.message import Message

import pybers
from conftest import allDocuments, findDocumentPath
from pybers import Color, ColorError, ColorSpace
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._persistence import readPackage
from pybers._persistence.types import ArchiveTypeError, parseArchive
from pybers.color._archive import composeColor, readColor

orange: tuple[float, float, float] = (1, 0.5, 0)


def iterateColors(message: Message) -> Iterator[tsp.Color]:
    """Yield every `TSP.Color` a message holds, however deep."""
    for descriptor, value in message.ListFields():
        if descriptor.type != descriptor.TYPE_MESSAGE:
            continue
        for each in value if descriptor.is_repeated else (value,):
            if isinstance(each, tsp.Color):
                yield each
            else:
                yield from iterateColors(each)


def listDocumentColors(path: Path) -> set[bytes]:
    """Return every distinct color a document holds, in the bytes Numbers stored."""
    found: set[bytes] = set()
    for iwaFile in readPackage(path).iwaFiles:
        for archive in iwaFile.archives:
            try:
                message = parseArchive(archive)
            except ArchiveTypeError:
                continue
            found.update(each.SerializeToString(deterministic=True)
                         for each in iterateColors(message))
    return found


# ── AC 1: a color carries its space, components, alpha and headroom ─────────


def testAColorCarriesEveryField() -> None:
    color = Color(ColorSpace.DISPLAY_P3, orange, 0.5, 2)

    assert color.colorSpace is ColorSpace.DISPLAY_P3
    assert color.components == (1.0, 0.5, 0.0)
    assert (color.alpha, color.headroom) == (0.5, 2.0)


def testEqualComponentsInDifferentSpacesCompareUnequal() -> None:
    assert (Color(ColorSpace.SRGB, orange, 1)
            != Color(ColorSpace.DISPLAY_P3, orange, 1))


def testAColorHoldsNoAssumedAlpha() -> None:
    with pytest.raises(TypeError, match="alpha"):
        Color(ColorSpace.SRGB, orange)  # type: ignore[call-arg]


def testAComponentIsHeldAsItsFloat32() -> None:
    color = Color(ColorSpace.SRGB, (0.1, 0, 0), 1)

    assert color.components[0] == Decimal("0.1")
    assert float(color.components[0]) != tsp.Color(model=tsp.Color.rgb, r=0.1).r
    assert composeColor(color).r == tsp.Color(model=tsp.Color.rgb, r=0.1).r


@pytest.mark.parametrize("number", [0.1, Decimal("0.1"), Decimal("0.10000000001")])
def testEveryNumberSpecifyingOneFloat32HoldsOneDecimal(number: float) -> None:
    color = Color(ColorSpace.DEVICE_GRAY, (number,), 1)

    assert color == Color(ColorSpace.DEVICE_GRAY, (Decimal("0.1"),), 1)
    assert isinstance(color.components[0], Decimal)


@pytest.mark.parametrize(("space", "components"), [
    (ColorSpace.SRGB, (1, 0)),
    (ColorSpace.DISPLAY_P3, (0, 0, 0, 1)),
    (ColorSpace.DEVICE_CMYK, orange),
    (ColorSpace.DEVICE_GRAY, ()),
    ("srgb", orange),
    (None, orange),
])
def testAMalformedColorIsRefused(
    space: ColorSpace, components: tuple[float, ...]
) -> None:
    with pytest.raises(ColorError):
        Color(space, components, 1)


@pytest.mark.parametrize("number", [
    float("nan"), float("inf"), 1e40, True, "1", Decimal("NaN"), Decimal("sNaN"),
    Decimal("Infinity"), Decimal("1e400"),
])
def testAComponentThatIsNoFiniteFloat32IsRefused(number: float) -> None:
    with pytest.raises(ColorError):
        Color(ColorSpace.DEVICE_GRAY, (number,), 1)


@pytest.mark.parametrize("component", [-0.1, 1.5, 255])
def testAComponentOutsideZeroToItsHeadroomIsRefused(component: float) -> None:
    with pytest.raises(ColorError, match="headroom of 1"):
        Color(ColorSpace.SRGB, (component, 0, 0), 1)


def testAComponentMayReachAHeadroomAboveOne() -> None:
    color = Color(ColorSpace.SRGB, (2.5, 0, 0), 1, 2.5)

    assert color.components[0] == 2.5


@pytest.mark.parametrize("alpha", [-0.1, 1.5, float("nan")])
def testAnAlphaOutsideZeroToOneIsRefused(alpha: float) -> None:
    with pytest.raises(ColorError, match="alpha"):
        Color(ColorSpace.DEVICE_GRAY, (1,), alpha)


@pytest.mark.parametrize("headroom", [0, -1])
def testAHeadroomAtOrBelowZeroIsRefused(headroom: float) -> None:
    with pytest.raises(ColorError, match="headroom"):
        Color(ColorSpace.DEVICE_GRAY, (1,), 1, headroom)


# ── AC 2 and 3: nothing is converted, and every stored color survives ───────


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryColorInADocumentReadsAndWritesBackIdentically(path: Path) -> None:
    for stored in listDocumentColors(path):
        archive = tsp.Color.FromString(stored)
        written = composeColor(readColor(archive)).SerializeToString(deterministic=True)
        assert written == stored, str(archive)


@pytest.mark.parametrize("archive", [
    tsp.Color(model=tsp.Color.cmyk, c=0.1, m=0.2, y=0.3, k=0.4, a=0.5, headroom=1),
    tsp.Color(model=tsp.Color.white, w=0.3, a=0.5, headroom=1),
    tsp.Color(model=tsp.Color.rgb, r=0.1, g=0.2, b=0.3, a=0.5,
              rgbspace=tsp.Color.p3, headroom=2),
], ids=["cmyk", "white", "p3-headroom"])
def testAColorOfEachModelSurvivesARoundTrip(archive: tsp.Color) -> None:
    assert composeColor(readColor(archive)) == archive


def testComposingAColorAlwaysStatesItsAlpha() -> None:
    composed = composeColor(Color.white)

    assert composed.HasField("a") and composed.HasField("headroom")


# ── AC 4: one text form in CSS syntax ───────────────────────────────────────


@pytest.mark.parametrize(("color", "text"), [
    (Color(ColorSpace.SRGB, (1, 128 / 255, 0), 1), "#ff8000ff"),
    (Color(ColorSpace.SRGB, (0, 0, 0), 0), "#00000000"),
    (Color(ColorSpace.SRGB, (0.1, 0.2, 0.3), 0.5),
     "color(srgb 0.1 0.2 0.3 / 0.5)"),
    (Color(ColorSpace.DISPLAY_P3, orange, 1),
     "color(display-p3 1 0.5 0 / 1)"),
    (Color(ColorSpace.DEVICE_CMYK, (0.1, 0, 0, 1), 0.5),
     "device-cmyk(0.1 0 0 1 / 0.5)"),
])
def testAColorPrintsAndReadsBackEqual(color: Color, text: str) -> None:
    assert str(color) == text
    assert Color.parse(text) == color


def testAGrayIsStoredAsThreeEqualSrgbComponents() -> None:
    color = Color.gray(0.5, 0.25)

    assert color == Color(ColorSpace.SRGB, (0.5, 0.5, 0.5), 0.25)
    assert composeColor(color) == tsp.Color(
        model=tsp.Color.rgb, r=0.5, g=0.5, b=0.5, a=0.25,
        rgbspace=tsp.Color.srgb, headroom=1,
    )


def testGrayTextPrintsWhatWillBeStored() -> None:
    color = Color.parse("device-gray(0.5 / 1)")

    assert color == Color.gray(0.5, 1)
    assert str(color) == "color(srgb 0.5 0.5 0.5 / 1)"


def testAGrayOnTheGridPrintsAsHex() -> None:
    assert str(Color.gray(128 / 255, 1)) == "#808080ff"


@pytest.mark.parametrize("level", [-0.1, 1.5])
def testAGrayLevelOutsideItsRangeIsRefused(level: float) -> None:
    with pytest.raises(ColorError):
        Color.gray(level, 1)


def testAStoredGrayPrintsAsTheGrayItIs() -> None:
    stored = readColor(tsp.Color(model=tsp.Color.white, w=0.5, a=1, headroom=1))

    assert stored.colorSpace is ColorSpace.DEVICE_GRAY
    assert str(stored) == "device-gray(0.5 / 1)"
    assert pybers.parseJsonForm(pybers.formatJsonForm(stored)) == stored


def testASmallComponentPrintsWithoutAnExponent() -> None:
    small = Color(ColorSpace.DEVICE_GRAY, (0.00001,), 1)

    assert str(small) == "device-gray(0.00001 / 1)"


def testEveryWholeNumberOf255thsPrintsAsHex() -> None:
    for whole in range(256):
        color = Color(ColorSpace.SRGB, (whole / 255, 0, 0), 1)
        assert str(color) == f"#{whole:02x}0000ff"
        assert Color.parse(str(color)) == color


def testAHexColorWithAlphaOffTheGridPrintsAsAFunction() -> None:
    color = Color(ColorSpace.SRGB, (1, 0, 0), 0.3)

    assert str(color) == "color(srgb 1 0 0 / 0.3)"


def testAComponentReadsBackToTheSameFloat32WhateverItsDigits() -> None:
    stored = tsp.Color(model=tsp.Color.white, w=0.123456789).w
    color = Color(ColorSpace.DEVICE_GRAY, (stored,), 1)

    assert readColor(composeColor(color)) == color
    assert composeColor(color).w == stored


@pytest.mark.parametrize(("text", "named"), [
    ("#ff8000", "#rrggbbaa"),
    ("#f80", "#rrggbbaa"),
    ("color(srgb 1 0 0)", "color(srgb r g b / a)"),
    ("color(display-p3 1 0 0)", "color(display-p3 r g b / a)"),
    ("device-cmyk(0 0 0 1)", "device-cmyk(c m y k / a)"),
    ("device-gray(0.5)", "device-gray(w / a)"),
])
def testTextLeavingOutAlphaIsRefusedNamingTheFormCarryingIt(
    text: str, named: str
) -> None:
    with pytest.raises(ColorError, match="alpha") as caught:
        Color.parse(text)
    assert named in str(caught.value)


@pytest.mark.parametrize("text", [
    "", "   ", "#", "#ggggggff", "#ff8000f", "#ff8000ff00", "#f80f", "red",
    "transparent",
    "color()", "color(srgb)", "color(srgb 1 0 / 1)", "color(srgb 1 0 0 0 / 1)",
    "color(srgb 1, 0, 0 / 1)", "color(srgb 100% 0 0 / 1)", "color(srgb none 0 0 / 1)",
    "color(srgb 1 0 0 / 1 / 1)", "color(srgb 1 0 0 /)", "color(cmyk 1 0 0 / 1)",
    "rgb(255 128 0 / 1)", "rgba(255, 128, 0, 1)", "device-gray(/ 1)",
    "device-cmyk(0 0 1 / 1)", "color(srgb 1e40 0 0 / 1)", "device-gray(0 / 2)",
])
def testTextThatIsNoColorIsRefused(text: str) -> None:
    with pytest.raises(ColorError):
        Color.parse(text)


def testTextIgnoresCaseAndSurroundingSpace() -> None:
    assert Color.parse("  #FF8000FF ") == Color.parse("#ff8000ff")
    assert Color.parse("COLOR(Display-P3 1 0 0 / 1)") == Color.parse(
        "color(display-p3 1 0 0 / 1)"
    )


def testAColorWithHeadroomIsRefusedATextFormNamingIt() -> None:
    color = Color(ColorSpace.SRGB, orange, 1, 2.5)

    with pytest.raises(ColorError, match="headroom of 2.5"):
        str(color)


# ── AC 5: Numbers stores RGB, whichever slider chose the color ──────────────


def readSliderColors() -> list[tsp.Color]:
    """Return the colors `97b-color-panel-sliders` holds, decoded."""
    return [tsp.Color.FromString(each)
            for each in listDocumentColors(findDocumentPath("97b-color-panel-sliders"))]


def testNumbersStoresEverySliderAsRgb() -> None:
    assert {each.model for each in readSliderColors()} == {tsp.Color.rgb}


@pytest.mark.parametrize(("label", "red", "space"), [
    ("the Gray Scale slider's 50%, three equal components", 0.5, tsp.Color.srgb),
    ("the CMYK slider's black, unlike RGB black", 0.103640832, tsp.Color.srgb),
    ("the Display P3 profile, as chosen", 1.0, tsp.Color.p3),
])
def testASliderColorIsStoredAsTheFindingsRecord(
    label: str, red: float, space: int
) -> None:
    assert any(
        each.rgbspace == space and each.r == pytest.approx(red, abs=1e-8)
        for each in readSliderColors()
    ), label


def testACreatedDocumentHoldsNoCmykOrGrayscaleColor(tmp_path: Path) -> None:
    path = tmp_path / "created.numbers"
    pybers.create("en_US").save(path)

    assert {tsp.Color.FromString(each).model for each in listDocumentColors(path)} == {
        tsp.Color.rgb
    }


def testACmykColorStillReadsPrintsAndSurvives() -> None:
    color = Color.parse("device-cmyk(0 0 0 1 / 1)")

    assert color.colorSpace is ColorSpace.DEVICE_CMYK
    assert str(color) == "device-cmyk(0 0 0 1 / 1)"
    assert pybers.parseJsonForm(pybers.formatJsonForm(color)) == color
    assert readColor(composeColor(color)) == color


# ── AC 6: the JSON form carries the fields ──────────────────────────────────


@pytest.mark.parametrize("color", [
    Color(ColorSpace.SRGB, (0.1, 0.2, 0.3), 0.5),
    Color(ColorSpace.DISPLAY_P3, orange, 1, 2.5),
    Color(ColorSpace.DEVICE_CMYK, (0.1, 0.2, 0.3, 0.4), 1),
    Color(ColorSpace.DEVICE_GRAY, (0.123456789,), 0.25),
], ids=["srgb", "p3-headroom", "cmyk", "white"])
def testAColorReadsBackEqualFromItsJsonForm(color: Color) -> None:
    assert pybers.parseJsonForm(pybers.formatJsonForm(color)) == color


def testTheJsonFormCarriesFieldsRatherThanText() -> None:
    color = Color(ColorSpace.SRGB, (0.1, 0, 1), 0.5)

    assert json.loads(pybers.formatJsonForm(color)) == {
        "jsonFormVersion": pybers.jsonFormVersion,
        "color": {
            "colorSpace": "srgb", "components": [0.1, 0, 1],
            "alpha": 0.5, "headroom": 1,
        },
    }


def testAJsonFormHoldingAnImpossibleColorIsRefused() -> None:
    form = json.loads(pybers.formatJsonForm(Color.parse("#ff8000ff")))
    form["color"]["colorSpace"] = "device-cmyk"

    with pytest.raises(ColorError):
        pybers.parseJsonForm(json.dumps(form))


# ── AC 7: a scenario per consumer ───────────────────────────────────────────


def testAScriptAuthorBuildsAColorAndPrintsIt() -> None:
    accent = pybers.Color(
        pybers.ColorSpace.DISPLAY_P3, orange, 1
    )

    assert str(accent) == "color(display-p3 1 0.5 0 / 1)"


def testACommandReadsAColorFromItsText() -> None:
    try:
        color = pybers.Color.parse("color(srgb 1 0.5 0)")
    except pybers.ColorError as refused:
        message = str(refused)
    else:
        raise AssertionError(f"{color} was accepted without its alpha")

    assert "color(srgb r g b / a)" in message
    assert str(pybers.Color.parse("#ff8000ff")) == "#ff8000ff"


# ── AC 9: a model Numbers stores none of is refused ─────────────────────────


@pytest.mark.parametrize(("text", "model"), [
    ("hsl(30 100% 50% / 1)", "HSL"),
    ("hwb(30 0% 0% / 1)", "HWB"),
    ("lab(50 40 59 / 1)", "Lab"),
    ("lch(50 70 60 / 1)", "LCH"),
    ("oklab(0.7 0.1 0.1 / 1)", "OKLab"),
    ("oklch(0.7 0.1 60 / 1)", "OKLCH"),
    ("color(xyz 0.1 0.2 0.3 / 1)", "XYZ"),
    ("color(xyz-d50 0.1 0.2 0.3 / 1)", "XYZ"),
])
def testAModelNumbersStoresNoneOfIsRefusedNamingWhatItStores(
    text: str, model: str
) -> None:
    with pytest.raises(ColorError, match=f"no {model} color") as caught:
        Color.parse(text)
    assert "RGB" in str(caught.value)


def testColorFunctionRefusesASpaceOnlyTheDeviceFormsSpecify() -> None:
    with pytest.raises(ColorError, match="srgb or display-p3"):
        Color.parse("color(device-gray 0.5 / 1)")


@pytest.mark.parametrize("space", ["rec2020", "a98-rgb", "prophoto-rgb", "srgb-linear"])
def testAnRgbSpaceNumbersStoresNoneOfIsRefused(space: str) -> None:
    with pytest.raises(ColorError, match="display-p3"):
        Color.parse(f"color({space} 1 0 0 / 1)")


# ── AC 10: exactly two colors are named ─────────────────────────────────────


@pytest.mark.parametrize(("token", "color", "text"), [
    ("black", Color.black, "#000000ff"),
    ("white", Color.white, "#ffffffff"),
])
def testATokenNamesAnOpaqueColorAsNumbersStoresIt(
    token: str, color: Color, text: str
) -> None:
    assert Color.parse(token) == color
    assert (str(color), color.alpha) == (text, 1.0)


def testABlackTokenIsWhatTheGrayScaleSliderStores() -> None:
    assert composeColor(Color.black) in readSliderColors()


@pytest.mark.parametrize("name", ["red", "gray", "transparent", "currentcolor"])
def testNoOtherNameIsAToken(name: str) -> None:
    with pytest.raises(ColorError):
        Color.parse(name)

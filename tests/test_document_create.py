#!/usr/bin/env python3
"""\
A document created from nothing holds only what Numbers needs, and reads back as one
empty sheet.

The floor is the one findings-10-creation.md measured for PYB-261: one preset of each
kind a person adds, into which Numbers 15.4 inserted a table, text box, shape, line,
chart, image and SVG on 2 November 2026, and one sheet in the pybers reset.

UPDATES
2026-11-03  `pybers show` prints a created document in full, for PYB-223.
2026-11-02  Written for PYB-261.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/11/02"

import uuid
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from google.protobuf.message import Message
from typer.testing import CliRunner

import pybers
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCHArchives_pb2 as tsch
from pybers._generated import TSPArchiveMessages_pb2 as tspArchive
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSSArchives_pb2 as tss
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSWPArchives_pb2 as tswp
from pybers._generated.themestyles import themeStyles
from pybers._persistence import NumbersPackage, readPackage
from pybers._persistence.difference import readTypeName
from pybers._persistence.types import archiveVersions, parseArchive
from pybers.cli._app import app

floorMembers: frozendict[str, frozendict[str, int]] = frozendict({
    "Index/Document.iwa": frozendict({
        "TN.DocumentArchive": 1, "TN.ThemeArchive": 1, "TN.SheetArchive": 1,
        "TSK.TreeNode": 2, "TSWP.StorageArchive": 6, "TST.TableStylePresetArchive": 1,
        "TST.TableStyleNetworkArchive": 1, "TSCH.ChartStylePreset": 1,
    }),
    "Index/DocumentStylesheet.iwa": frozendict({
        "TSS.StylesheetArchive": 1, "TSWP.ParagraphStyleArchive": 1,
        "TSWP.ListStyleArchive": 1, "TSWP.CharacterStyleArchive": 1,
        "TSWP.DropCapStyleArchive": 1, "TSWP.ShapeStyleArchive": 6,
        "TSD.MediaStyleArchive": 2, "TN.SheetStyleArchive": 1,
        "TST.TableStyleArchive": 1, "TST.CellStyleArchive": 1,
        "TSCH.ChartStyleArchive": 1, "TSCH.LegendStyleArchive": 1,
        "TSCH.ChartAxisStyleArchive": 1, "TSCH.ChartSeriesStyleArchive": 1,
        "TSCH.ReferenceLineStyleArchive": 1,
    }),
    "Index/Metadata.iwa": frozendict({"TSP.PackageMetadata": 1}),
})


def createSaved(tmp_path: Path, locale: str = "en_US") -> Path:
    """Return the path of a document created in a region and saved."""
    path = tmp_path / f"created-{locale}.numbers"
    pybers.create(locale).save(path)
    return path


def readBodies(package: NumbersPackage) -> dict[str, Message]:
    """Return each archive's parsed body, keyed by its type's name."""
    return {
        readTypeName(archive): parseArchive(archive)
        for member in package.iwaFiles for archive in member.archives
    }


def readWithoutIdentities(package: NumbersPackage) -> list[tuple[int, bytes]]:
    """Return every archive's body, the UUID each object is known by left out."""
    bodies = []
    for member in package.iwaFiles:
        for archive in member.archives:
            body = parseArchive(archive)
            if isinstance(body, tspArchive.PackageMetadata):
                for component in body.components:
                    for entry in component.object_uuid_map_entries:
                        entry.uuid.lower = entry.uuid.upper = 0
            encoded = body.SerializeToString(deterministic=True)
            bodies.append((archive.identifier, encoded))
    return bodies


def testACreatedDocumentReadsBackAsOneSheetHoldingNoTable(tmp_path: Path) -> None:
    document = pybers.open(createSaved(tmp_path))

    assert [sheet.name for sheet in document.sheets] == ["Sheet 1"]
    assert document.sheet(1).tables == []
    assert document.localeIdentifier == "en_US"


def testACreatedDocumentHoldsOnlyTheFloorNumbersNeeds(tmp_path: Path) -> None:
    package = readPackage(createSaved(tmp_path))

    held = {
        member.name: dict(Counter(readTypeName(archive) for archive in member.archives))
        for member in package.iwaFiles
    }
    assert held == floorMembers
    assert [member.name for member in package.otherMembers] == [
        "Metadata/DocumentIdentifier",
    ]


def testACreatedSheetPrintsInTheResetWithFitToPageOff(tmp_path: Path) -> None:
    bodies = readBodies(readPackage(createSaved(tmp_path)))

    root = bodies["TN.DocumentArchive"]
    sheet = bodies["TN.SheetArchive"]
    assert isinstance(root, tn.DocumentArchive)
    assert isinstance(sheet, tn.SheetArchive)
    assert not root.HasField("paper_id")
    assert not root.HasField("page_size")
    assert sheet.HasField("is_autofit_on") and not sheet.is_autofit_on
    assert sheet.HasField("show_page_numbers") and not sheet.show_page_numbers
    assert sheet.content_scale == 1.0


def testACreatedThemeOffersThirtySlotsOpeningWithSixGrays(tmp_path: Path) -> None:
    theme = readBodies(readPackage(createSaved(tmp_path)))["TN.ThemeArchive"]

    assert isinstance(theme, tn.ThemeArchive)
    slots = theme.super.color_presets
    assert len(slots) == 30
    assert [(slot.model, round(slot.w, 6)) for slot in slots[:6]] == [
        (tsp.Color.white, level) for level in (1.0, 0.9, 0.7, 0.5, 0.3, 0.0)
    ]
    assert all(
        slot.model == tsp.Color.rgb and slot.rgbspace == tsp.Color.srgb
        for slot in slots[6:]
    )
    assert len({(slot.r, slot.g, slot.b) for slot in slots[6:]}) == 24


def testACreatedStylesheetMapsTheShapeStylesNumbersLooksUp(tmp_path: Path) -> None:
    stylesheet = readBodies(readPackage(createSaved(tmp_path)))["TSS.StylesheetArchive"]

    assert isinstance(stylesheet, tss.StylesheetArchive)
    assert stylesheet.HasField("is_locked")
    assert sorted(entry.identifier for entry in stylesheet.identifier_to_style_map) == [
        "drawingline-0-drawinglineStyle", "svgimport-0-shapestyle",
        "text-0-paragraphstyle",
    ]


def testACreatedThemeOffersOnePresetOfEachKindAPersonAdds(tmp_path: Path) -> None:
    theme = readBodies(readPackage(createSaved(tmp_path)))["TN.ThemeArchive"]

    assert isinstance(theme, tn.ThemeArchive)
    offered = {
        field.name: len(presets)
        for descriptor, extension in theme.super.ListFields() if descriptor.is_extension
        for field, presets in extension.ListFields()
    }
    assert offered == dict.fromkeys((
        "line_style_presets", "shape_style_presets", "textbox_style_presets",
        "image_style_presets", "movie_style_presets", "drawing_line_style_presets",
        "list_style_presets", "character_style_presets", "paragraph_style_presets",
        "dropcap_style_presets", "chart_presets", "table_style_presets",
        "caption_style_presets",
    ), 1)


def testACreatedTablePresetCarriesTheReset(tmp_path: Path) -> None:
    bodies = readBodies(readPackage(createSaved(tmp_path)))

    tableStyle = bodies["TST.TableStyleArchive"]
    cellStyle = bodies["TST.CellStyleArchive"]
    text = bodies["TSWP.ParagraphStyleArchive"]
    assert isinstance(tableStyle, tst.TableStyleArchive)
    assert isinstance(cellStyle, tst.CellStyleArchive)
    assert isinstance(text, tswp.ParagraphStyleArchive)
    assert not tableStyle.table_properties.v_strokes_visible
    assert not tableStyle.table_properties.h_strokes_visible
    assert not tableStyle.table_properties.table_border_visible
    assert not cellStyle.cell_properties.text_wrap
    assert text.super.name == "pybers-base"


def testACreatedSheetIsFilledWhiteWithAnUncoloredTab(tmp_path: Path) -> None:
    style = readBodies(readPackage(createSaved(tmp_path)))["TN.SheetStyleArchive"]

    assert isinstance(style, tn.SheetStyleArchive)
    fill = style.sheet_properties.fill.color
    assert (fill.model, fill.w, fill.a) == (tsp.Color.white, 1.0, 1.0)
    assert style.sheet_properties.HasField("tab_color")


def testACreatedTablePresetOffersEveryStrokeWithNoneShown(tmp_path: Path) -> None:
    style = readBodies(readPackage(createSaved(tmp_path)))["TST.TableStyleArchive"]

    assert isinstance(style, tst.TableStyleArchive)
    properties = style.table_properties
    assert len(properties.ListFields()) == 62
    assert properties.HasField("table_body_horizontal_border_stroke")
    assert not properties.table_border_visible
    assert not properties.h_strokes_visible
    assert not properties.v_strokes_visible
    assert not properties.banded_rows


def testACreatedChartSeriesStyleStatesWhatNumbersAlwaysStates(
    tmp_path: Path,
) -> None:
    bodies = readBodies(readPackage(createSaved(tmp_path)))
    style = bodies["TSCH.ChartSeriesStyleArchive"]

    stated = [field for field, _ in style.ListFields() if field.name != "super"]
    assert len(stated) == len(themeStyles["series"])


def testACreatedChartPresetKeepsNumbersListLengths(tmp_path: Path) -> None:
    preset = readBodies(readPackage(createSaved(tmp_path)))["TSCH.ChartStylePreset"]

    assert isinstance(preset, tsch.ChartStylePreset)
    assert [len(preset.value_axis_styles), len(preset.category_axis_styles),
            len(preset.series_styles), len(preset.paragraph_styles)] == [2, 1, 6, 30]


def testACreatedDocumentStatesItsRegionAsAPersonChoosingIt(tmp_path: Path) -> None:
    root = readBodies(readPackage(createSaved(tmp_path, "de_DE")))["TN.DocumentArchive"]

    assert isinstance(root, tn.DocumentArchive)
    locale = root.super.super
    assert locale.locale_identifier == "de_DE"
    assert locale.creation_locale_identifier == "de_DE"
    assert locale.has_user_defined_locale
    assert locale.formatting_symbols.currency_code == "EUR"
    assert root.super.document_language == "de"


def testACreatedArchiveCarriesTheVersionNumbersWritesItsTypeAt(tmp_path: Path) -> None:
    package = readPackage(createSaved(tmp_path))

    for member in package.iwaFiles:
        for archive in member.archives:
            body = parseArchive(archive)
            assert archive.messages[0].version == archiveVersions[type(body)]


def testACreatedPackageRegistersOnlyItsTwoComponents(tmp_path: Path) -> None:
    metadata = readBodies(readPackage(createSaved(tmp_path)))["TSP.PackageMetadata"]

    assert isinstance(metadata, tspArchive.PackageMetadata)
    assert sorted(each.preferred_locator for each in metadata.components) == [
        "Document", "DocumentStylesheet",
    ]
    assert all(each.identifier >= 100 or each.identifier == 1
               for each in metadata.components)
    assert list(metadata.read_version) == [2, 0, 0]


def testTheDocumentIdentifierIsAFreshUppercaseUuid(tmp_path: Path) -> None:
    package = readPackage(createSaved(tmp_path))

    text = package.otherMembers[0].data.decode()
    assert text == str(uuid.UUID(text)).upper()


def testTwoDocumentsCreatedAlikeDifferOnlyInIdentityAndTimestamp(
    tmp_path: Path,
) -> None:
    directories = (tmp_path / "first", tmp_path / "second")
    for directory in directories:
        directory.mkdir()
    first, second = (readPackage(createSaved(directory)) for directory in directories)

    assert [replace(each, dateTime=()) for each in first.members] == [
        replace(each, dateTime=()) for each in second.members
    ]
    assert readWithoutIdentities(first) == readWithoutIdentities(second)
    assert first.otherMembers[0].data != second.otherMembers[0].data


def testACreatedDocumentReadBackWritesBackUnchanged(tmp_path: Path) -> None:
    path = createSaved(tmp_path)
    again = tmp_path / "again.numbers"

    pybers.open(path).save(again)

    assert path.read_bytes() == again.read_bytes()


def testACreatedDocumentSavesOnlyToAPathItIsGiven() -> None:
    document = pybers.create("en_US")

    with pytest.raises(pybers.WriteError, match="Pass a path to save"):
        document.save()


def testCreateRefusesARegionPybersDoesNotOffer() -> None:
    with pytest.raises(pybers.LocaleError, match="No region pybers offers"):
        pybers.create("xx_YY")


def testACreatedDocumentsFirstTableCreatesItsEngine(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    document.sheet(1).tableAdd("Table 1", 2, 2).cell("B1").formulaText = "=A1*3"
    path = tmp_path / "with-table.numbers"

    document.save(path)

    package = readPackage(path)
    engines = [archive for member in package.iwaFiles for archive in member.archives
               if readTypeName(archive) == "TSCE.CalculationEngineArchive"]
    root = readBodies(package)["TN.DocumentArchive"]
    assert isinstance(root, tn.DocumentArchive)
    assert [engine.identifier for engine in engines] == [
        root.super.calculation_engine.identifier
    ]
    assert pybers.open(path).sheet(1).table(1).cell("B1").formulaText == "=A1*3"


def testACreatedDocumentHoldingNoTableHoldsNoEngine(tmp_path: Path) -> None:
    root = readBodies(readPackage(createSaved(tmp_path)))["TN.DocumentArchive"]

    assert isinstance(root, tn.DocumentArchive)
    assert not root.super.HasField("calculation_engine")


def testTheShowCommandReadsACreatedDocument(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["show", str(createSaved(tmp_path))])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        "Locale: en_US", "", "Sheet: Sheet 1",
    ]

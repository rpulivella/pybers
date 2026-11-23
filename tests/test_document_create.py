#!/usr/bin/env python3
"""\
A document created from nothing holds only what Numbers needs, and reads back as one
empty sheet.

The floor is the one findings-10-creation.md measured for PYB-261: one preset of each
kind a person adds, into which Numbers 15.4 inserted a table, text box, shape, line,
chart, image and SVG on 2 November 2026, and one sheet in the pybers reset.

UPDATES
2026-11-16  A created theme keys every style Numbers adds on opening one, and its
            chart text is its own, for PYB-292.
2026-11-06  Created grays and the sheet's fill are sRGB, for PYB-264.
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
from click.testing import CliRunner
from google.protobuf.message import Message

import pybers
from conftest import findDocumentPath
from pybers._generated import TNArchives_pb2 as tn
from pybers._generated import TSCHArchives_pb2 as tsch
from pybers._generated import TSPArchiveMessages_pb2 as tspArchive
from pybers._generated import TSPMessages_pb2 as tsp
from pybers._generated import TSSArchives_pb2 as tss
from pybers._generated import TSTArchives_pb2 as tst
from pybers._generated import TSTStylePropertyArchiving_pb2 as tstStyles
from pybers._generated import TSWPArchives_pb2 as tswp
from pybers._generated.themestyles import themeStyles
from pybers._persistence import NumbersPackage, readPackage
from pybers._persistence.difference import readTypeName
from pybers._persistence.index import ArchiveIndex, findRoot
from pybers._persistence.types import archiveVersions, parseArchive
from pybers.cli._app import app

floorMembers: frozendict[str, frozendict[str, int]] = frozendict({
    "Index/Document.iwa": frozendict({
        "TN.DocumentArchive": 1, "TN.ThemeArchive": 1, "TN.SheetArchive": 1,
        "TSK.TreeNode": 2, "TSWP.StorageArchive": 6, "TST.TableStylePresetArchive": 1,
        "TST.TableStyleNetworkArchive": 1, "TSCH.ChartStylePreset": 1,
    }),
    "Index/DocumentStylesheet.iwa": frozendict({
        "TSS.StylesheetArchive": 1, "TSWP.ParagraphStyleArchive": 12,
        "TSWP.ListStyleArchive": 1, "TSWP.CharacterStyleArchive": 1,
        "TSWP.DropCapStyleArchive": 1, "TSWP.ShapeStyleArchive": 9,
        "TSD.MediaStyleArchive": 3, "TN.SheetStyleArchive": 1,
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
            if isinstance(body, tsch.ChartStylePreset):
                body.ClearField("uuid")
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
    assert [
        (round(slot.r, 6), round(slot.g, 6), round(slot.b, 6)) for slot in slots[:6]
    ] == [(level, level, level) for level in (1.0, 0.9, 0.7, 0.5, 0.3, 0.0)]
    assert all(
        slot.model == tsp.Color.rgb and slot.rgbspace == tsp.Color.srgb
        for slot in slots
    )
    assert len({(slot.r, slot.g, slot.b) for slot in slots[6:]}) == 24


def readStyleKeys(path: Path) -> dict[str, set[str]]:
    """Return the keys of a document's stylesheet, by the map holding each."""
    package = readPackage(path)
    index = ArchiveIndex(package)
    theme = index.resolve(findRoot(index).theme, tn.ThemeArchive)
    stylesheet = index.resolve(theme.super.document_stylesheet, tss.StylesheetArchive)
    maps: dict[str, set[str]] = {
        "identifier_to_style_map": {
            entry.identifier for entry in stylesheet.identifier_to_style_map
        },
    }
    for field, value in stylesheet.ListFields():
        if field.name.startswith("styles_for_"):
            maps[field.name] = {
                entry.identifier for entry in value.identifier_to_style_map
            }
    return maps


def testACreatedStylesheetKeysEveryStyleNumbersAddsOnOpeningOne(
    tmp_path: Path,
) -> None:
    measured = readStyleKeys(findDocumentPath("99-cell-fill-in-a-created-table"))
    created = readStyleKeys(createSaved(tmp_path))

    for name, keys in measured.items():
        assert keys <= created.get(name, set()), name


def readThemeArchives(path: Path) -> dict[int, bytes]:
    """Return every style, stylesheet, theme, preset and network body, by identifier."""
    themed = ("Style", "Theme", "Preset", "Network")
    return {
        archive.identifier: parseArchive(archive).SerializeToString(deterministic=True)
        for member in readPackage(path).iwaFiles for archive in member.archives
        if any(each in readTypeName(archive) for each in themed)
    }


def testNumbersOpensAndSavesACreatedDocumentChangingNoStyle() -> None:
    written = readThemeArchives(
        Path(__file__).parent / "golden" / "00-created-tables-added-by-pybers.numbers"
    )
    saved = readThemeArchives(findDocumentPath("99b-created-document-saved-unedited"))

    assert saved == written


def testACreatedStylesheetIsLockedAndCullable(tmp_path: Path) -> None:
    stylesheet = readBodies(readPackage(createSaved(tmp_path)))["TSS.StylesheetArchive"]

    assert isinstance(stylesheet, tss.StylesheetArchive)
    assert stylesheet.HasField("is_locked")
    assert stylesheet.can_cull_styles


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
        "caption_style_presets", "svg_import_style_presets",
    ), 1) | {"gradient_fill_presets": 6, "shadow_presets": 8}


def findPresetNetwork(path: Path) -> tuple[ArchiveIndex, tst.TableStyleNetworkArchive]:
    """Return a created document's index and its table preset's network."""
    index = ArchiveIndex(readPackage(path))
    theme = index.resolve(findRoot(index).theme, tn.ThemeArchive)
    preset = index.resolve(
        theme.super.Extensions[tstStyles.ThemePresetsArchive.extension]
        .table_style_presets[0],
        tstStyles.TableStylePresetArchive,
    )
    return index, index.resolve(preset.style_network, tst.TableStyleNetworkArchive)


def testACreatedTablePresetCarriesTheReset(tmp_path: Path) -> None:
    index, network = findPresetNetwork(createSaved(tmp_path))

    tableStyle = index.resolve(network.table_style, tst.TableStyleArchive)
    cellStyle = index.resolve(network.body_cell_style, tst.CellStyleArchive)
    text = index.resolve(network.body_text_style, tswp.ParagraphStyleArchive)
    assert not tableStyle.table_properties.v_strokes_visible
    assert not tableStyle.table_properties.h_strokes_visible
    assert not tableStyle.table_properties.table_border_visible
    assert not cellStyle.cell_properties.text_wrap
    assert text.super.name == "pybers-base"
    assert network.preset_id == 0 and network.HasField("preset_id")


def testATableAddedToACreatedDocumentNamesTheThemesRootStyles(tmp_path: Path) -> None:
    document = pybers.create("en_US")
    document.sheet(1).tableAdd("T", 2, 2)
    path = tmp_path / "with-table.numbers"
    document.save(path)
    index, network = findPresetNetwork(path)

    info = next(
        index.resolve(drawable, tst.TableInfoArchive)
        for drawable in index.resolve(findRoot(index).sheets[0], tn.SheetArchive)
        .drawable_infos
    )
    model = index.resolve(info.tableModel, tst.TableModelArchive)
    assert model.table_style.identifier == network.table_style.identifier
    assert model.body_cell_style.identifier == network.body_cell_style.identifier


def testACreatedChartPresetCentersTextOfItsOwnApartFromTables(tmp_path: Path) -> None:
    path = createSaved(tmp_path)
    index, network = findPresetNetwork(path)
    theme = index.resolve(findRoot(index).theme, tn.ThemeArchive)
    chart = index.resolve(
        theme.super.Extensions[tsch.ChartPresetsArchive.extension].chart_presets[0],
        tsch.ChartStylePreset,
    )

    texts = {reference.identifier for reference in chart.paragraph_styles}
    assert network.body_text_style.identifier not in texts
    for identifier in texts:
        style = index.identifierResolve(identifier, tswp.ParagraphStyleArchive)
        assert style.para_properties.alignment == (
            tswp.ParagraphStylePropertiesArchive.TATvalue2
        )
    assert chart.HasField("uuid")


def testACreatedSheetIsFilledWhiteWithAnUncoloredTab(tmp_path: Path) -> None:
    style = readBodies(readPackage(createSaved(tmp_path)))["TN.SheetStyleArchive"]

    assert isinstance(style, tn.SheetStyleArchive)
    fill = style.sheet_properties.fill.color
    assert (fill.model, fill.rgbspace) == (tsp.Color.rgb, tsp.Color.srgb)
    assert (fill.r, fill.g, fill.b, fill.a) == (1.0, 1.0, 1.0, 1.0)
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

    with pytest.raises(pybers.WriteError, match="Give a path to save it to"):
        document.save()


def testCreateRefusesARegionPybersDoesNotOffer() -> None:
    with pytest.raises(pybers.LocaleError, match="is not a region pybers offers"):
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

#!/usr/bin/env python3
"""\
The JSON Schema of the JSON form: generated from the model, committed, and obeyed.

A document is validated as any JSON reader parses it, integers as integers, since
the schema describes the text rather than the Decimals pybers reads it into.

UPDATES
2026-10-24  Written for PYB-259.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/10/24"

import json
from functools import cache
from pathlib import Path

import jsonschema
import pytest

import pybers
from conftest import allDocuments, findDocumentPath
from pybers.interchange._jsontext import writeJsonText
from pybers.interchange._schema import buildJsonFormSchema, schemaPath


@cache
def buildValidator() -> jsonschema.Draft202012Validator:
    """Return a validator for the committed schema, built once."""
    return jsonschema.Draft202012Validator(json.loads(schemaPath.read_text()))


def findSchemaError(text: str) -> str | None:
    """Return the deepest reason JSON text breaks the schema, or None when it obeys."""
    errors = buildValidator().iter_errors(json.loads(text))
    found = jsonschema.exceptions.best_match(errors)
    return None if found is None else f"{found.json_path}: {found.message}"


def testTheCommittedSchemaIsWhatTheModelGenerates() -> None:
    generated = writeJsonText(buildJsonFormSchema()) + "\n"
    assert schemaPath.read_text() == generated, (
        "The JSON form changed. Run "
        "`.venv/bin/python3 -m tools.local.jsonform_schema`, "
        "and move jsonFormVersion as docs/decisions.md requires."
    )


def testTheSchemaIsValidJsonSchema() -> None:
    jsonschema.Draft202012Validator.check_schema(json.loads(schemaPath.read_text()))


def testTheSchemaPinsTheFormsVersion() -> None:
    schema = json.loads(schemaPath.read_text())
    version = schema["$defs"]["DocumentJsonForm"]["properties"]["jsonFormVersion"]
    assert version["const"] == pybers.jsonFormVersion


@pytest.mark.parametrize("path", allDocuments, ids=lambda path: path.stem)
def testEveryDocumentObeysTheSchema(path: Path) -> None:
    assert findSchemaError(pybers.formatJsonForm(pybers.open(path))) is None


def testEveryPartObeysTheSchema() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    sheet = document.sheet("Sheet 1")
    table = sheet.table("Table 1")
    for text in (pybers.formatJsonForm(sheet), pybers.formatJsonForm(table),
                 pybers.formatJsonForm(table, "A1:A3"),
                 pybers.formatJsonForm(table.cell("A11"))):
        assert findSchemaError(text) is None


def testTheSchemaRefusesAValueOfAnotherKind() -> None:
    document = pybers.open(findDocumentPath("20-formula-shapes"))
    table = document.sheet("Sheet 1").tables[0]
    tree = json.loads(pybers.formatJsonForm(table.cell("A11")))
    tree["table"]["cells"][0]["value"] = "text in a number cell"
    assert findSchemaError(json.dumps(tree)) is not None


def testTheSchemaMarksValueCachedReadOnly() -> None:
    schema = json.loads(schemaPath.read_text())
    cell = schema["$defs"]["CellForm"]
    assert cell["properties"]["valueCached"]["readOnly"] is True
    assert "valueCached" not in cell["required"]

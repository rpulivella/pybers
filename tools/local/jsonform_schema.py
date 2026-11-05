#!/usr/bin/env python3
"""\
pybers JSON form schema

Generate the JSON Schema of pybers' JSON form from the model and write it to
src/pybers/interchange/schema.json, reporting whether it changed. A changed schema
is a new version of the form, so `jsonFormVersion` moves with it, as
`docs/decisions.md` records. `test_json_form_schema` fails until this has run.

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

from rich.console import Console

from pybers.interchange._jsontext import writeJsonText
from pybers.interchange._schema import buildJsonFormSchema, schemaPath

console: Console = Console()


def writeSchema() -> bool:
    """Write the generated schema over the committed one, and report a change."""
    generated = writeJsonText(buildJsonFormSchema()) + "\n"
    committed = schemaPath.read_text() if schemaPath.exists() else ""
    if generated == committed:
        return False
    schemaPath.write_text(generated)
    return True


def main() -> None:
    """Write the schema and say what happened."""
    if writeSchema():
        console.print(f"Wrote {schemaPath}. Move jsonFormVersion if the form changed.")
    else:
        console.print(f"{schemaPath} already matches the model.")


if __name__ == "__main__":
    main()

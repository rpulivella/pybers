#!/usr/bin/env python3
"""\
pybers protobuf schema bootstrap

Extract the iWork archive protobuf schemas that pybers builds on, from the Numbers
application binary on this machine, and report how they differ from the schemas
of numbers-parser, which is not vendored here, see CLAUDE.md.

**Why this exists rather than a vendored copy of someone else's schemas.** Apple
compiles the protobuf descriptors for its own archive format into the Numbers
binary. Those descriptors are the source of truth for the format, and dumping them
is a mechanical step. A project that vendors another project's dump inherits an
artifact it cannot regenerate, explain, or update when Apple ships a new Numbers.
pybers runs its own extraction so the schema layer is owned here, matches the
Numbers version this project actually round-trips against, and can be re-derived at
any time. See "Open architectural decisions" in CLAUDE.md for the full reasoning.

The extraction technique is not this project's invention and is not claimed as such.
It comes from `protodump.py` by Peter Sobot (2022), itself inspired by Sean Patrick
O'Brien's 2013 `proto-dump` (https://github.com/obriensp/proto-dump), and the
pipeline shape is learned from reference/numbers-parser's own Makefile. protodump is
treated the way protoc is: a third-party tool this script invokes, obtained and kept
OUTSIDE this repository. It carries a copyright line but no license statement, so it
is deliberately never vendored here.

protodump lives in workarea/bootstrap/, which is git-ignored, so it is never committed
or distributed with pybers. It additionally needs:
    .venv/bin/python3 -m pip install --upgrade protobuf tqdm

Nothing is written into the repository unless --write is passed. The default run is a
read-only report, which is also the differential check: a dump that matches the
vendored schemas corroborates both, and any difference is a finding to understand
rather than a silent divergence.

Usage:
    .venv/bin/python3 -m tools.local.protos_extract
    .venv/bin/python3 -m tools.local.protos_extract \
        --numbers "/Applications/Numbers Creator Studio.app"
    .venv/bin/python3 -m tools.local.protos_extract \
        --protodump ~/.local/share/protodump/protodump.py
    .venv/bin/python3 -m tools.local.protos_extract --write
    .venv/bin/python3 -m tools.local.protos_extract --write --preview

Runs on the repository's venv. protodump additionally requires protobuf and tqdm,
generating Python from the dumped schemas requires protoc on PATH, and the type
stubs beside it require mypy-protobuf's `protoc-gen-mypy` plugin there too.

UPDATES
2026-10-23  `--preview` names what was `--dry-run`, as the command-line design does,
            for PYB-156.
2026-10-14  Moved here from `tools/protos-extract.py`, and run as a module, for PYB-204.
2026-10-13  The repository root comes from `scripts/lib/shared.py`, for
            PYB-204.
2026-09-04  Locating Numbers moved to tools/lib/numbersapp.py for #44, so the
            function-index extractor searches the same way rather than a second
            way that drifts.
2026-08-16  Pinned encoding on both subprocess calls. text=True alone decodes with the
            ambient locale, so a context without LANG mangled the toolchain's own
            diagnostics, which are the text quoted into the RuntimeError, making the
            one explanation of a failure the thing that got corrupted.
2026-08-13  Written. Replaces the abandoned "reuse the vendored _pb2 classes" plan;
            see CLAUDE.md decision 1 for why extracting our own is the correct call.
"""
__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/13"
__usage__ = ".venv/bin/python3 -m tools.local.protos_extract [options]"

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from tools.local.lib.numbersapp import (
    NumbersApplication,
    formatApplication,
    locateNumbers,
)
from tools.local.lib.protos import (
    SchemaComparison,
    compareSchemas,
    defaultProtodumpPath,
    generatePythonModules,
    normalizeSchemaNames,
    resolveProtodumpPath,
)
from tools.workflow.lib.shared import repositoryRoot

console = Console()

# Committed, because the artifacts it produces are committed: src/pybers/protos/ and
# src/pybers/_generated/ are machine output, and an artifact whose generator is missing
# is the same opacity this project refused when it declined to vendor someone else's
# dump. It cannot run on a fresh clone: it needs a local Numbers and a separately
# obtained protodump: which is exactly why the output is committed rather than built.
#
# Where the dumped schemas and the generated Python land once --write is passed. Both
# are committed, so that installing pybers never requires a local Numbers.
schemaDirectory: Path = repositoryRoot / "src" / "pybers" / "protos"
generatedDirectory: Path = repositoryRoot / "src" / "pybers" / "_generated"

# The vendored schemas this dump is compared against. Reference only: never a source.
referenceSchemaDirectory: Path = (
    repositoryRoot / "reference" / "numbers-parser" / "src" / "protos"
)


def runProtodump(
    protodumpPath: Path, application: NumbersApplication, outputDirectory: Path
) -> None:
    """Invoke protodump to write .proto files for one application into a directory.

    Run as a subprocess rather than imported, which is the sanctioned exception in
    tools/README.md for an external toolchain: protodump exposes only an argv entry
    point, so there is no library surface to call, and keeping it behind a process
    boundary keeps a third-party script out of this tool's import graph.
    """
    outputDirectory.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            str(protodumpPath),
            str(application.bundlePath),
            str(outputDirectory),
        ],
        capture_output=True,
        # text=True alone decodes with the ambient locale, so the same run under a
        # cron or launchd context with no LANG turns an em-dash in protodump's own
        # output into mojibake, silently, without raising. That matters here because
        # this output IS the error message raised below.
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"protodump failed (exit {completed.returncode}). Its own message "
            f"follows.\n{detail}"
        )


def showComparison(comparison: SchemaComparison) -> None:
    """Print how the extracted schemas compare with the vendored reference set."""
    console.print(
        f"extracted [bold cyan]{comparison.extractedCount}[/] schemas, "
        f"reference has [bold cyan]{comparison.referenceCount}[/]"
    )
    console.print(f"  identical         [green]{comparison.identicalCount}[/]")
    console.print(f"  differing content [yellow]{len(comparison.differingContent)}[/]")
    console.print(f"  only in ours      [magenta]{len(comparison.onlyInExtracted)}[/]")
    console.print(f"  only in reference [magenta]{len(comparison.onlyInReference)}[/]")

    for label, names, tint in (
        ("differs", comparison.differingContent, "yellow"),
        ("only ours", comparison.onlyInExtracted, "magenta"),
        ("only reference", comparison.onlyInReference, "magenta"),
    ):
        for name in names:
            console.print(f"  [{tint}]{label}[/]  {name}")


def runExtract(arguments: argparse.Namespace) -> int:
    """Dump the schemas, compare them with the reference set, and optionally
    commit them."""
    application = locateNumbers(Path(arguments.numbers) if arguments.numbers else None)
    protodumpPath = resolveProtodumpPath(
        Path(arguments.protodump) if arguments.protodump else None
    )
    for line in formatApplication(application):
        console.print(line)
    console.print(f"  protodump  [dim]{escape(str(protodumpPath))}[/]")
    console.print()

    with tempfile.TemporaryDirectory(prefix="pybers-protos-") as temporaryName:
        extractedDirectory = Path(temporaryName)
        with console.status("dumping protobuf descriptors from the Numbers binary"):
            runProtodump(protodumpPath, application, extractedDirectory)
        renamed = normalizeSchemaNames(extractedDirectory)
        if renamed:
            console.print(f"normalized [cyan]{renamed}[/] dotted filenames for protoc")

        if not referenceSchemaDirectory.is_dir():
            console.print(
                f"[yellow]No reference schemas at {referenceSchemaDirectory}; "
                "skipping the differential check.[/]"
            )
        else:
            showComparison(compareSchemas(extractedDirectory, referenceSchemaDirectory))
            console.print()

        if not arguments.write:
            console.print(
                "[dim]Read-only run. Pass --write to copy the schemas into "
                f"{schemaDirectory.relative_to(repositoryRoot)} and generate Python.[/]"
            )
            return 0

        dumped = sorted(extractedDirectory.glob("*.proto"))
        if arguments.preview:
            console.print("[yellow]Preview. Nothing was written.[/]")
            console.print(
                f"would write [bold]{len(dumped)}[/] schemas to "
                f"{escape(str(schemaDirectory))}"
            )
            console.print(f"would generate Python into {generatedDirectory}")
            return 0

        schemaDirectory.mkdir(parents=True, exist_ok=True)
        for path in dumped:
            (schemaDirectory / path.name).write_text(
                path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
            )
        console.print(
            f"[green]Wrote[/] {len(dumped)} schemas to {escape(str(schemaDirectory))}"
        )

        with console.status("compiling schemas to Python with protoc"):
            moduleCount = generatePythonModules(schemaDirectory, generatedDirectory)
        console.print(
            f"[green]Generated[/] {moduleCount} modules in "
            f"{escape(str(generatedDirectory))}"
        )

    return 0


def buildParser() -> argparse.ArgumentParser:
    """Assemble the command line."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract iWork archive protobuf schemas from the local Numbers install and "
            "compare them with the vendored reference set."
        ),
    )
    parser.add_argument(
        "--numbers",
        default=None,
        help="Numbers bundle path (searched for if omitted; the bundle may be renamed)",
    )
    parser.add_argument(
        "--protodump",
        default=None,
        help=f"path to protodump.py (default: $PROTODUMP, then {defaultProtodumpPath})",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="copy the dumped schemas into the repository "
        "(default is a read-only report)",
    )
    parser.add_argument("--preview", dest="preview", action="store_true")
    parser.set_defaults(handler=runExtract)
    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except RuntimeError as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""\
pybers protobuf schema bootstrap

Extract the iWork archive protobuf schemas that pybers builds on, from the Numbers
application binary on this machine, and report how they differ from the schemas
vendored under reference/numbers-parser/.

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
    /usr/bin/env python3 -m pip install --upgrade protobuf tqdm

Nothing is written into the repository unless --write is passed. The default run is a
read-only report, which is also the differential check: a dump that matches the
vendored schemas corroborates both, and any difference is a finding to understand
rather than a silent divergence.

Usage:
    python3 scripts/protos-extract.py
    python3 scripts/protos-extract.py --numbers "/Applications/Numbers Creator Studio.app"
    python3 scripts/protos-extract.py --protodump ~/.local/share/protodump/protodump.py
    python3 scripts/protos-extract.py --write
    python3 scripts/protos-extract.py --write --dry-run

Requires rich. protodump additionally requires protobuf and tqdm, and generating
Python from the dumped schemas requires protoc on PATH.

UPDATES
2026-08-13  Written. Replaces the abandoned "reuse the vendored _pb2 classes" plan;
            see CLAUDE.md decision 1 for why extracting our own is the correct call.
"""
__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "TBD"
__version__ = "0.1.0"
__email__ = "rpulivella@icloud.com"
__status__ = "Development"
__date__ = "2026/08/13"
__usage__ = "python3 scripts/protos-extract.py [options]"

import argparse
import os
import plistlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

console = Console()

# Committed, because the artifacts it produces are committed: src/pybers/protos/ and
# src/pybers/_generated/ are machine output, and an artifact whose generator is missing
# is the same opacity this project refused when it declined to vendor someone else's
# dump. It cannot run on a fresh clone — it needs a local Numbers and a separately
# obtained protodump — which is exactly why the output is committed rather than built.
repositoryRoot: Path = Path(__file__).resolve().parent.parent

# Where the dumped schemas and the generated Python land once --write is passed. Both
# are committed, so that installing pybers never requires a local Numbers.
schemaDirectory: Path = repositoryRoot / "src" / "pybers" / "protos"
generatedDirectory: Path = repositoryRoot / "src" / "pybers" / "_generated"

# The vendored schemas this dump is compared against. Reference only — never a source.
referenceSchemaDirectory: Path = (
    repositoryRoot / "reference" / "numbers-parser" / "src" / "protos"
)

# protodump stays in workarea/, which is git-ignored and therefore never committed,
# published, or distributed — the whole of the licensing concern, since that file
# carries a copyright line but no license statement. This script is committed; the
# third-party tool it invokes is not.
# Overridable with --protodump or the PROTODUMP environment variable.
defaultProtodumpPath: Path = repositoryRoot / "workarea" / "bootstrap" / "protodump.py"

# Numbers is normally here, but the bundle can be renamed on disk, so a missing path
# triggers a search by bundle contents rather than an immediate failure.
defaultNumbersPath: Path = Path("/Applications/Numbers.app")

applicationSearchDirectories: tuple[Path, ...] = (
    Path("/Applications"),
    Path("/System/Applications"),
    Path.home() / "Applications",
)


@dataclass(frozen=True)
class NumbersApplication:
    """A located Numbers install and the identity read from its bundle."""

    bundlePath: Path
    executablePath: Path
    version: str
    build: str
    bundleIdentifier: str


@dataclass(frozen=True)
class SchemaComparison:
    """How a freshly dumped set of schemas differs from the vendored reference set."""

    extractedCount: int
    referenceCount: int
    onlyInExtracted: tuple[str, ...]
    onlyInReference: tuple[str, ...]
    differingContent: tuple[str, ...]
    identicalCount: int


def readBundleIdentity(bundlePath: Path) -> NumbersApplication | None:
    """Return the identity of a Numbers install, or None when the bundle is not one.

    Matched on the executable name rather than the bundle identifier, because the
    identifier differs between Apple's macOS and iOS builds and a renamed bundle
    keeps its executable name while losing its filename.
    """
    informationPath = bundlePath / "Contents" / "Info.plist"
    if not informationPath.is_file():
        return None

    try:
        information = plistlib.loads(informationPath.read_bytes())
    except (plistlib.InvalidFileException, ValueError):
        return None

    if information.get("CFBundleExecutable") != "Numbers":
        return None

    executablePath = bundlePath / "Contents" / "MacOS" / "Numbers"
    if not executablePath.is_file():
        return None

    return NumbersApplication(
        bundlePath=bundlePath,
        executablePath=executablePath,
        version=str(information.get("CFBundleShortVersionString", "unknown")),
        build=str(information.get("CFBundleVersion", "unknown")),
        bundleIdentifier=str(information.get("CFBundleIdentifier", "unknown")),
    )


def locateNumbers(requestedPath: Path | None) -> NumbersApplication:
    """Find the Numbers install to dump from, searching only if it is not where expected.

    An explicit --numbers path is trusted and its failure is loud. Otherwise the usual
    location is tried first, then every application bundle is inspected, because the
    bundle is sometimes renamed on disk and its filename cannot be relied upon.
    """
    if requestedPath is not None:
        located = readBundleIdentity(requestedPath)
        if located is None:
            raise RuntimeError(
                f"{requestedPath} is not a Numbers application bundle. Expected "
                "Contents/MacOS/Numbers and a matching Info.plist."
            )
        return located

    located = readBundleIdentity(defaultNumbersPath)
    if located is not None:
        return located

    for directory in applicationSearchDirectories:
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.glob("*.app")):
            located = readBundleIdentity(candidate)
            if located is not None:
                return located

    raise RuntimeError(
        "Could not find a Numbers install. Searched "
        f"{', '.join(str(d) for d in applicationSearchDirectories)}. Pass --numbers "
        "with the bundle path if it lives elsewhere."
    )


def resolveProtodumpPath(requestedPath: Path | None) -> Path:
    """Return the path to protodump.py, failing loudly with instructions when absent.

    Never vendored into this repository: it carries a copyright line but no license
    statement, so it is obtained and kept outside the tree. See the module docstring.
    """
    candidates = [
        requestedPath,
        Path(os.environ["PROTODUMP"]) if os.environ.get("PROTODUMP") else None,
        defaultProtodumpPath,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate

    raise RuntimeError(
        "protodump.py was not found. It is deliberately not vendored in this repo — "
        f"obtain it once and place it at {defaultProtodumpPath}, or pass --protodump / "
        "set PROTODUMP. See this script's docstring for the provenance and the two "
        "packages it needs (protobuf, tqdm)."
    )


def runProtodump(
    protodumpPath: Path, application: NumbersApplication, outputDirectory: Path
) -> None:
    """Invoke protodump to write .proto files for one application into a directory.

    Run as a subprocess rather than imported, which is the sanctioned exception in
    scripts/README.md for an external toolchain: protodump exposes only an argv entry
    point, so there is no library surface to call, and keeping it behind a process
    boundary keeps a third-party script out of this tool's import graph.
    """
    outputDirectory.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, str(protodumpPath), str(application.bundlePath), str(outputDirectory)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"protodump failed (exit {completed.returncode}). Its own message follows.\n{detail}"
        )


def normalizeSchemaNames(directory: Path) -> int:
    """Rename dotted schema filenames to underscores and fix the imports that name them.

    protodump writes the descriptor's own path, so files arrive as
    `TSCE.CalculationEngine.proto`. protoc cannot import a name containing dots, so
    each file is renamed to `TSCE_CalculationEngine.proto` and every `import "..."`
    line referring to an old name is rewritten. The need for this step was learned
    from reference/numbers-parser's Makefile; the transformation itself is two string
    substitutions and is implemented here rather than taking on a second dependency.
    """
    replacements: dict[str, str] = {}
    for oldPath in sorted(directory.glob("*.proto")):
        newName = oldPath.name[: -len(".proto")].replace(".", "_") + ".proto"
        if newName != oldPath.name:
            replacements[oldPath.name] = newName
            oldPath.rename(directory / newName)

    if not replacements:
        return 0

    for schemaPath in sorted(directory.glob("*.proto")):
        original = schemaPath.read_text(encoding="utf-8", errors="replace")
        rewritten = original
        for oldName, newName in replacements.items():
            rewritten = rewritten.replace(f'import "{oldName}";', f'import "{newName}";')
        if rewritten != original:
            schemaPath.write_text(rewritten, encoding="utf-8")

    return len(replacements)


def compareSchemas(extractedDirectory: Path, referenceDirectory: Path) -> SchemaComparison:
    """Compare two directories of .proto files by name and by content.

    This is the point of the default run: a dump matching the vendored schemas
    corroborates both, while a difference is a real finding — most likely a Numbers
    version that moved on from whatever the vendored copy was taken from.
    """
    extracted = {path.name: path for path in extractedDirectory.glob("*.proto")}
    reference = {path.name: path for path in referenceDirectory.glob("*.proto")}

    shared = sorted(set(extracted) & set(reference))
    differing = [
        name
        for name in shared
        if extracted[name].read_text(encoding="utf-8", errors="replace")
        != reference[name].read_text(encoding="utf-8", errors="replace")
    ]

    return SchemaComparison(
        extractedCount=len(extracted),
        referenceCount=len(reference),
        onlyInExtracted=tuple(sorted(set(extracted) - set(reference))),
        onlyInReference=tuple(sorted(set(reference) - set(extracted))),
        differingContent=tuple(differing),
        identicalCount=len(shared) - len(differing),
    )


def generatePythonModules(schemaSource: Path, outputDirectory: Path) -> int:
    """Compile the schemas to Python and make their cross-imports package-relative.

    protoc writes a flat `import TSTArchives_pb2` at the top of each module, which
    only resolves when the output directory is itself on sys.path. Inside a package
    it fails, so every import naming a module generated here is rewritten to its full
    dotted path. reference/numbers-parser does the same with a blunt `^import T`
    substitution; matching against the actual generated names instead means a schema
    that does not begin with T is still handled, and an unrelated import is not.
    """
    schemas = sorted(schemaSource.glob("*.proto"))
    if not schemas:
        raise RuntimeError(f"No .proto files to compile in {schemaSource}.")

    outputDirectory.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "protoc",
            f"--proto_path={schemaSource}",
            f"--python_out={outputDirectory}",
            *[str(path) for path in schemas],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"protoc failed (exit {completed.returncode}).\n{detail}")

    generated = sorted(outputDirectory.glob("*_pb2.py"))
    moduleNames = {path.stem for path in generated}
    packagePath = f"{outputDirectory.parent.name}.{outputDirectory.name}"

    for modulePath in generated:
        original = modulePath.read_text(encoding="utf-8")
        rewritten = original
        for moduleName in moduleNames:
            rewritten = rewritten.replace(
                f"\nimport {moduleName} as ", f"\nimport {packagePath}.{moduleName} as "
            )
        if rewritten != original:
            modulePath.write_text(rewritten, encoding="utf-8")

    (outputDirectory / "__init__.py").write_text(
        '"""Generated protobuf modules. Do not edit — see workarea/bootstrap/."""\n',
        encoding="utf-8",
    )
    return len(generated)


def showApplication(application: NumbersApplication) -> None:
    """Print the located Numbers install."""
    console.print(f"[bold]Numbers {application.version}[/] [dim](build {application.build})[/]")
    console.print(f"  bundle     [cyan]{application.bundlePath}[/]")
    console.print(f"  identifier [dim]{application.bundleIdentifier}[/]")


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


def cmdExtract(arguments: argparse.Namespace) -> int:
    """Dump the schemas, compare them with the reference set, and optionally commit them."""
    application = locateNumbers(Path(arguments.numbers) if arguments.numbers else None)
    protodumpPath = resolveProtodumpPath(
        Path(arguments.protodump) if arguments.protodump else None
    )
    showApplication(application)
    console.print(f"  protodump  [dim]{protodumpPath}[/]")
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
        if arguments.dryRun:
            console.print("[yellow]Dry run — nothing was written.[/]")
            console.print(f"would write [bold]{len(dumped)}[/] schemas to {schemaDirectory}")
            console.print(f"would generate Python into {generatedDirectory}")
            return 0

        schemaDirectory.mkdir(parents=True, exist_ok=True)
        for path in dumped:
            (schemaDirectory / path.name).write_text(
                path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
            )
        console.print(f"[green]Wrote[/] {len(dumped)} schemas to {schemaDirectory}")

        with console.status("compiling schemas to Python with protoc"):
            moduleCount = generatePythonModules(schemaDirectory, generatedDirectory)
        console.print(f"[green]Generated[/] {moduleCount} modules in {generatedDirectory}")

    return 0


def buildParser() -> argparse.ArgumentParser:
    """Assemble the command line."""
    parser = argparse.ArgumentParser(
        prog="protos-extract.py",
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
        help="copy the dumped schemas into the repository (default is a read-only report)",
    )
    parser.add_argument("--dry-run", dest="dryRun", action="store_true")
    parser.set_defaults(handler=cmdExtract)
    return parser


def main() -> int:
    """Parse the command line and dispatch, reporting failures without a traceback."""
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""\
The schema dump compared with the vendored set, and the Python generated from it.

UPDATES
2026-10-14  Moved here from `protos_extract.py`, which keeps its command line,
            for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/08/13"

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.workflow.lib.shared import repositoryRoot

# protodump stays in workarea/, which is git-ignored and therefore never committed,
# published, or distributed: the whole of the licensing concern, since that file
# carries a copyright line but no license statement. This script is committed; the
# third-party tool it invokes is not.
# Overridable with --protodump or the PROTODUMP environment variable.
defaultProtodumpPath: Path = repositoryRoot / "workarea" / "bootstrap" / "protodump.py"


@dataclass(frozen=True)
class SchemaComparison:
    """How a freshly dumped set of schemas differs from the vendored reference set."""

    extractedCount: int
    referenceCount: int
    onlyInExtracted: tuple[str, ...]
    onlyInReference: tuple[str, ...]
    differingContent: tuple[str, ...]
    identicalCount: int


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
        "protodump.py was not found. It is deliberately not vendored in this repo, "
        f"obtain it once and place it at {defaultProtodumpPath}, or pass --protodump / "
        "set PROTODUMP. See this script's docstring for the provenance and the two "
        "packages it needs (protobuf, tqdm)."
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
            rewritten = rewritten.replace(
                f'import "{oldName}";', f'import "{newName}";'
            )
        if rewritten != original:
            schemaPath.write_text(rewritten, encoding="utf-8")

    return len(replacements)


def compareSchemas(
    extractedDirectory: Path, referenceDirectory: Path
) -> SchemaComparison:
    """Compare two directories of .proto files by name and by content.

    This is the point of the default run: a dump matching the vendored schemas
    corroborates both, while a difference is a real finding, most likely a Numbers
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
            # Type stubs come out of the SAME invocation deliberately. Generating
            # them separately would be a step someone forgets, and a stale stub is
            # worse than none: it reports errors for fields that do exist. Requires
            # the `protoc-gen-mypy` plugin from mypy-protobuf on PATH.
            f"--mypy_out=quiet:{outputDirectory}",
            *[str(path) for path in schemas],
        ],
        capture_output=True,
        # Pinned for the same reason as the protodump call above: protoc's diagnostics
        # are quoted verbatim into the RuntimeError below, so a locale-dependent decode
        # would corrupt the one thing that explains the failure.
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"protoc failed (exit {completed.returncode}).\n{detail}")

    generated = sorted(outputDirectory.glob("*_pb2.py"))
    stubs = {path.stem for path in outputDirectory.glob("*_pb2.pyi")}
    missing = sorted(path.stem for path in generated if path.stem not in stubs)
    if missing:
        raise RuntimeError(
            f"protoc produced no type stub for {len(missing)} module(s): "
            f"{', '.join(missing[:5])}. Is protoc-gen-mypy on PATH?"
        )
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
        '"""Generated protobuf modules, compiled from src/pybers/protos/, whose README '
        'records their origin. Do not edit."""\n',
        encoding="utf-8",
    )
    return len(generated)

#!/usr/bin/env python3
"""\
pybers function index map

Derive the map from a Numbers formula function index to its name, by reading the
compiled code of the Numbers on this machine, and report how it differs from the
map committed at src/pybers/_generated/functions.py.

**Why the binary is the only source.** A `.numbers` package stores a function call
as a bare `uint32` and nothing else. No name appears in the archives, in the
schemas, or anywhere in the package, so a name has to come from the application
that assigns the numbers. Excel's older binary format numbers functions the same
way and Microsoft publishes that table as the `Ftab` in `[MS-XLS]`, but the
numbering disagrees completely: `SUM` is 4 there and 168 here, so borrowing it
yields plausible wrong functions rather than a failure.

**This reads the binary. It never runs it.** Nothing here loads, links, executes
or modifies any part of Numbers; the application file is opened read-only and
parsed as data. The extraction technique, finding the indices in the compiled
code rather than in any published table, comes from the numbers-parser project
and is not claimed as this project's invention.

The names live in `TSCEFormulaCreationMagic`, a C++ class carrying one method per
function, and each method loads its index into a register before handing it to a
node builder. Three code shapes carry it, all three measured on Numbers 15.3.1:

    function_Narg       `movz w0, #index` then a call to `function_<N>arg`
    appendFunctionElement   `movz w1, #index` then a direct call to the builder,
                            emitted for the lazily evaluated functions such as IF
    closureIndexField   `movz w8, #index` stored as a halfword into a closure the
                        volatile functions such as PI, ROW and TODAY build instead

**What the map does not cover, and why that is reported rather than hidden.**
`TSCEFormulaCreationMagic` is an authoring helper, not the function registry, so
a function Numbers implements but never authors through it has no method here and
therefore no index this script can read. Every run prints those names. On
15.3.1 that is 26 of 350, none of them common, and `--gaps` lists them.

Numbers' own localized function list decides which extracted names are real. A
method whose name is absent from `en.lproj/TSCalculationEngine.strings` is an
internal spelling rather than a function, which is how `SHOW` and
`RANGE.TRACKING.FORMULA` are excluded without a hand-maintained list to go stale.

Output is committed for the same reason the schemas are: `pip install pybers` has
no Numbers to read. Nothing is written unless --write is passed; the default run
is a read-only report and the differential check at once.

Usage:
    python3 scripts/functions-extract.py
    python3 scripts/functions-extract.py --gaps
    python3 scripts/functions-extract.py --numbers "/Applications/Numbers.app"
    python3 scripts/functions-extract.py --write
    python3 scripts/functions-extract.py --write --dry-run

Requires rich. Needs no other tooling: the Mach-O parsing and the instruction
decoding are both done here, so there is no objdump, no c++filt, and no
architecture-specific toolchain to install.

UPDATES
2026-09-04  Written for #44.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"
__usage__ = "python3 scripts/functions-extract.py [options]"

import argparse
import ast
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from numbersapp import NumbersApplication, locateNumbers
from rich.console import Console
from rich.markup import escape

try:
    from rich_argparse import RichHelpFormatter
except ImportError:  # rich_argparse is optional, per scripts/README.md
    RichHelpFormatter = argparse.HelpFormatter  # type: ignore[assignment,misc]

console: Console = Console()

repositoryRoot: Path = Path(__file__).resolve().parent.parent

# Committed, so that naming a function never needs a local Numbers.
generatedPath: Path = repositoryRoot / "src" / "pybers" / "_generated" / "functions.py"

# The calculation engine ships inside the tables framework rather than beside it:
# TSCalculationEngine.framework is a 117 KB shim and the formula code is here.
frameworkName: str = "TSTables"

# Numbers' own function list, which decides which extracted name is a real
# function. Read from the English localization because the map is the canonical
# spelling rather than a display string.
stringsTableName: str = "TSCalculationEngine"

# The known-good pairs every run is checked against. A change here is a finding
# about Numbers; a mismatch is a defect in this script.
knownPairs: dict[str, int] = {"SUM": 168, "IF": 62, "SUMIFS": 231, "ROUND": 126}

machO64Magic: int = 0xFEEDFACF
fatMagic: int = 0xCAFEBABE
fatMagic64: int = 0xCAFEBABF
cpuTypeArm64: int = 0x0100000C

segment64Command: int = 0x19
symbolTableCommand: int = 0x02

nlistSize: int = 16
sectionSize: int = 80

# AArch64 instruction encodings, masked to the fields that identify them.
movzMask: int = 0xFF800000
movzValue: int = 0x52800000
storeHalfwordMask: int = 0xFFC00000
storeHalfwordValue: int = 0x79000000
branchLinkMask: int = 0xFC000000
branchLinkValue: int = 0x94000000
branchLinkOffsetMask: int = 0x03FFFFFF
branchLinkSignBit: int = 0x02000000
branchLinkRange: int = 0x04000000

# `_ZN24TSCEFormulaCreationMagic<length><NAME>E<arguments>`, an Itanium nested
# name whose one variable part is a length-prefixed identifier. Matched rather
# than demangled, because a general demangler for this one shape is a dependency
# that would earn nothing.
magicMethod: re.Pattern[str] = re.compile(
    r"^__ZN24TSCEFormulaCreationMagic(\d+)([A-Za-z0-9_]+)E"
)

# Helpers taking a TSCEFunctionIndex as their first argument, one per arity.
argumentHelper: str = "__ZN24TSCEFormulaCreationMagic13function_"
nodeBuilder: str = "__ZN22TSCEASTFunctionElement21appendFunctionElement"


class ExtractionError(RuntimeError):
    """The binary could not be read, or carries nothing this script recognizes."""


@dataclass(frozen=True)
class MachOImage:
    """One architecture slice, and the two tables this script reads from it."""

    data: bytes
    textAddress: int
    textOffset: int
    textSize: int
    symbols: dict[int, str]

    def bodyOf(self, address: int, end: int) -> bytes:
        """Return the instruction bytes of one function, given its bounds."""
        return self.data[
            self.textOffset + address - self.textAddress :
            self.textOffset + end - self.textAddress
        ]


@dataclass(frozen=True)
class FunctionMap:
    """An extracted index map, and everything a reader needs to judge it."""

    names: dict[int, str]
    mechanisms: dict[str, str]
    unnamed: tuple[str, ...]
    composite: tuple[str, ...]
    uncovered: tuple[str, ...]
    version: str
    build: str


@dataclass(frozen=True)
class MapComparison:
    """How a freshly extracted map differs from the committed one."""

    added: tuple[tuple[int, str], ...]
    removed: tuple[tuple[int, str], ...]
    renamed: tuple[tuple[int, str, str], ...]
    unchangedCount: int


def arm64Slice(binary: Path) -> bytes:
    """Return the arm64 slice of a Mach-O file, which may be universal or thin.

    Universal binaries are big-endian in their own header, which is the one place
    in this file where byte order is not native.
    """
    data = binary.read_bytes()
    if struct.unpack_from("<I", data, 0)[0] == machO64Magic:
        return data
    magic = struct.unpack_from(">I", data, 0)[0]
    if magic not in (fatMagic, fatMagic64):
        raise ExtractionError(f"{binary} is not a Mach-O file (magic {magic:#x}).")

    wide = magic == fatMagic64
    count = struct.unpack_from(">I", data, 4)[0]
    entrySize = 32 if wide else 20
    for index in range(count):
        base = 8 + index * entrySize
        cpuType = struct.unpack_from(">i", data, base)[0]
        if cpuType != cpuTypeArm64:
            continue
        if wide:
            offset, size = struct.unpack_from(">2Q", data, base + 8)
        else:
            offset, size = struct.unpack_from(">2I", data, base + 8)
        return data[offset : offset + size]

    raise ExtractionError(f"{binary} carries no arm64 slice.")


def readImage(binary: Path) -> MachOImage:
    """Parse the executable text and the symbol table out of one Mach-O slice."""
    data = arm64Slice(binary)
    if struct.unpack_from("<I", data, 0)[0] != machO64Magic:
        raise ExtractionError(f"{binary} is not a 64-bit Mach-O image.")

    commandCount = struct.unpack_from("<I", data, 16)[0]
    offset = 32
    textAddress = textOffset = textSize = 0
    symbolOffset = symbolCount = stringOffset = stringSize = 0

    for _ in range(commandCount):
        command, commandSize = struct.unpack_from("<2I", data, offset)
        if command == segment64Command:
            segmentName = data[offset + 8 : offset + 24].rstrip(b"\0").decode()
            sectionCount = struct.unpack_from("<I", data, offset + 64)[0]
            cursor = offset + 72
            for _section in range(sectionCount):
                sectionName = data[cursor : cursor + 16].rstrip(b"\0").decode()
                if (segmentName, sectionName) == ("__TEXT", "__text"):
                    textAddress, textSize = struct.unpack_from("<2Q", data, cursor + 32)
                    textOffset = struct.unpack_from("<I", data, cursor + 48)[0]
                cursor += sectionSize
        elif command == symbolTableCommand:
            symbolOffset, symbolCount, stringOffset, stringSize = struct.unpack_from(
                "<4I", data, offset + 8
            )
        offset += commandSize

    if not textSize or not symbolCount:
        raise ExtractionError(
            f"{binary} carries no __TEXT,__text section or no symbol table."
        )

    stringTable = data[stringOffset : stringOffset + stringSize]
    symbols: dict[int, str] = {}
    for index in range(symbolCount):
        nameIndex, _type, _section, _description, value = struct.unpack_from(
            "<IBBHQ", data, symbolOffset + index * nlistSize
        )
        end = stringTable.find(b"\0", nameIndex)
        symbols[value] = stringTable[nameIndex:end].decode("ascii", "replace")

    return MachOImage(data, textAddress, textOffset, textSize, symbols)


def methodName(symbol: str) -> str | None:
    """Return the function name a mangled method carries, or None for anything else.

    The arity suffix is deliberately discarded: arity belongs to the call and one
    function has as many overloads as it has argument counts.
    """
    matched = magicMethod.match(symbol)
    if matched is None:
        return None
    name = matched.group(2)[: int(matched.group(1))]
    return None if name.startswith("function_") else name


def indexInBody(
    body: bytes, address: int, helpers: set[int], builders: set[int]
) -> tuple[int, str] | None:
    """Return the function index one method loads, and which shape carried it.

    A single forward pass, tracking only immediates loaded by `movz`, which is
    every shape Numbers uses to name an index. A call clears the tracked
    registers, since the AArch64 procedure call standard permits a callee to
    destroy them and a stale value read across a call would be a plausible
    wrong number.
    """
    registers: dict[int, int] = {}
    fromClosure: int | None = None

    for position in range(0, len(body) & ~3, 4):
        word = struct.unpack_from("<I", body, position)[0]
        if word & movzMask == movzValue:
            shift = ((word >> 21) & 3) * 16
            registers[word & 0x1F] = ((word >> 5) & 0xFFFF) << shift
        elif word & storeHalfwordMask == storeHalfwordValue:
            # A volatile function stores its index into the closure it builds
            # instead of passing it, so the halfword store is the only carrier.
            fromClosure = registers.get(word & 0x1F, fromClosure)
        elif word & branchLinkMask == branchLinkValue:
            displacement = word & branchLinkOffsetMask
            if displacement & branchLinkSignBit:
                displacement -= branchLinkRange
            target = address + position + (displacement << 2)
            if target in helpers and 0 in registers:
                return registers[0], "function_Narg"
            if target in builders and 1 in registers:
                return registers[1], "appendFunctionElement"
            registers = {}

    if fromClosure is not None:
        return fromClosure, "closureIndexField"
    return None


def extractCandidates(image: MachOImage) -> dict[str, list[tuple[int, str]]]:
    """Return every index each authoring method emits, and how each was carried.

    A name emitting more than one distinct index is not a function but an internal
    helper that builds one of several formulas, so every emission is kept rather
    than the first.
    """
    helpers = {a for a, n in image.symbols.items() if n.startswith(argumentHelper)}
    builders = {a for a, n in image.symbols.items() if n.startswith(nodeBuilder)}
    if not helpers or not builders:
        raise ExtractionError(
            "Neither TSCEFormulaCreationMagic::function_<N>arg nor "
            "TSCEASTFunctionElement::appendFunctionElement is present. This "
            "Numbers does not build formulas the way this script reads."
        )

    ordered = sorted(
        address
        for address in image.symbols
        if image.textAddress <= address < image.textAddress + image.textSize
    )
    candidates: dict[str, list[tuple[int, str]]] = {}
    for position, address in enumerate(ordered):
        name = methodName(image.symbols[address])
        if name is None:
            continue
        end = (
            ordered[position + 1]
            if position + 1 < len(ordered)
            else image.textAddress + image.textSize
        )
        found = indexInBody(image.bodyOf(address, end), address, helpers, builders)
        if found is not None:
            candidates.setdefault(name, []).append(found)
    return candidates


def displayName(symbolName: str) -> str:
    """Return the spelling Numbers uses for a method named in C++.

    A leading underscore avoids a collision with a macro, `_MAX` being `MAX`, and
    an interior underscore stands for the dot in a name such as `REFERENCE.NAME`.
    """
    return symbolName.lstrip("_").replace("_", ".")


def buildMap(application: NumbersApplication) -> FunctionMap:
    """Extract the index map, validated against Numbers' own function list."""
    image = readImage(application.frameworkBinary(frameworkName))
    candidates = extractCandidates(image)
    known = set(application.localizedStrings(stringsTableName))

    names: dict[int, str] = {}
    mechanisms: dict[str, str] = {}
    unnamed: list[str] = []
    composite: list[str] = []
    claimed: dict[int, str] = {}

    for symbolName, emissions in sorted(candidates.items()):
        display = displayName(symbolName)
        if len({index for index, _shape in emissions}) != 1:
            composite.append(display)
            continue
        if display not in known:
            unnamed.append(display)
            continue
        index, shape = emissions[0]
        if index in claimed:
            raise ExtractionError(
                f"Function index {index} is claimed by both {claimed[index]} and "
                f"{display}. Numbers' own function list rejects an internal "
                "spelling, so two survivors mean the validation no longer holds."
            )
        claimed[index] = display
        names[index] = display
        mechanisms[display] = shape

    covered = set(names.values())
    uncovered = sorted(
        name
        for name in known
        if re.fullmatch(r"[A-Z][A-Z0-9.]*", name) and name not in covered
    )

    for name, expected in knownPairs.items():
        if names.get(expected) != name:
            raise ExtractionError(
                f"Index {expected} read as {names.get(expected)!r} rather than "
                f"{name}. These four pairs are measured against real documents in "
                "tests/fixtures, so a disagreement is a defect in this script "
                "rather than a change in Numbers."
            )

    return FunctionMap(
        names=names,
        mechanisms=mechanisms,
        unnamed=tuple(sorted(unnamed)),
        composite=tuple(sorted(composite)),
        uncovered=tuple(uncovered),
        version=application.version,
        build=application.build,
    )


def readCommitted(path: Path) -> dict[int, str]:
    """Return the committed map, or an empty one when it has not been written yet.

    Read as a literal rather than imported, so that comparing depends neither on
    pybers being installed nor on running the file this script is about to
    overwrite.
    """
    if not path.is_file():
        return {}
    for statement in ast.parse(path.read_text(), str(path)).body:
        if not isinstance(statement, ast.AnnAssign | ast.Assign):
            continue
        targets = (
            [statement.target] if isinstance(statement, ast.AnnAssign)
            else statement.targets
        )
        named = any(
            isinstance(target, ast.Name) and target.id == "functionNames"
            for target in targets
        )
        if not named or statement.value is None:
            continue
        committed = ast.literal_eval(statement.value)
        return {int(key): str(value) for key, value in committed.items()}
    raise ExtractionError(f"{path} defines no functionNames dictionary.")


def compareMaps(extracted: dict[int, str], committed: dict[int, str]) -> MapComparison:
    """Report what a regeneration would change, which is what makes it reviewable."""
    added = tuple(
        (index, name) for index, name in sorted(extracted.items())
        if index not in committed
    )
    removed = tuple(
        (index, name) for index, name in sorted(committed.items())
        if index not in extracted
    )
    renamed = tuple(
        (index, committed[index], name)
        for index, name in sorted(extracted.items())
        if index in committed and committed[index] != name
    )
    unchanged = sum(
        1 for index, name in extracted.items() if committed.get(index) == name
    )
    return MapComparison(added, removed, renamed, unchanged)


def renderModule(functionMap: FunctionMap) -> str:
    """Return the source of the generated module, one line per function."""
    entries = "\n".join(
        f'    {index}: "{name}",'
        for index, name in sorted(functionMap.names.items())
    )
    return f'''#!/usr/bin/env python3
"""\\
Numbers formula function indices and their names. Machine output, do not edit.

Written by scripts/functions-extract.py from Numbers {functionMap.version}
(build {functionMap.build}). A correction made here is destroyed by the next
extraction; correct the extractor instead.

{len(functionMap.names)} of the {len(functionMap.names) + len(functionMap.uncovered)} \
functions Numbers names are covered. The rest are
implemented without an authoring method to read an index from, and a formula
calling one keeps its index rather than gaining a name.
"""

functionNames: dict[int, str] = {{
{entries}
}}
'''


def showApplication(application: NumbersApplication) -> None:
    """Print the Numbers this run read from."""
    console.print(
        f"[bold]Numbers {escape(application.version)}[/] "
        f"(build {escape(application.build)})"
    )
    console.print(f"  bundle     {escape(str(application.bundlePath))}")


def showMap(functionMap: FunctionMap, showGaps: bool) -> None:
    """Print what was extracted, and what Numbers names that it could not reach."""
    counts: dict[str, int] = {}
    for mechanism in functionMap.mechanisms.values():
        counts[mechanism] = counts.get(mechanism, 0) + 1
    total = len(functionMap.names) + len(functionMap.uncovered)

    console.print(
        f"\n[bold]{len(functionMap.names)}[/] of {total} named functions carry an "
        f"index this run could read."
    )
    for mechanism, count in sorted(counts.items()):
        console.print(f"  {count:>4}  {escape(mechanism)}")
    console.print(
        f"  {len(functionMap.unnamed):>4}  dropped, absent from Numbers' own "
        "function list"
    )
    if functionMap.unnamed:
        console.print(
            f"        {escape(', '.join(functionMap.unnamed))}", highlight=False
        )
    console.print(
        f"  {len(functionMap.composite):>4}  dropped, emitting more than one index"
    )
    if functionMap.composite:
        console.print(
            f"        {escape(', '.join(functionMap.composite))}", highlight=False
        )
    console.print(
        f"  {len(functionMap.uncovered):>4}  named by Numbers with no authoring "
        "method to read"
    )
    if showGaps and functionMap.uncovered:
        console.print(
            f"        {escape(', '.join(functionMap.uncovered))}", highlight=False
        )
    elif functionMap.uncovered:
        console.print("        pass --gaps to list them")

    console.print("\n[bold]Known pairs[/], each measured against a real document:")
    for name, index in knownPairs.items():
        console.print(f"  {index:>4}  {escape(name)}")


def showComparison(comparison: MapComparison, path: Path) -> None:
    """Print how the extracted map differs from the committed one."""
    console.print(f"\n[bold]Against {escape(str(path.relative_to(repositoryRoot)))}[/]")
    if not path.is_file():
        console.print("  [yellow]not written yet[/]")
        return
    console.print(f"  {comparison.unchangedCount} unchanged")
    for index, name in comparison.added:
        console.print(f"  [green]added[/]    {index:>4}  {escape(name)}")
    for index, name in comparison.removed:
        console.print(f"  [red]removed[/]  {index:>4}  {escape(name)}")
    for index, was, now in comparison.renamed:
        console.print(
            f"  [yellow]renamed[/]  {index:>4}  {escape(was)} -> {escape(now)}"
        )
    if not (comparison.added or comparison.removed or comparison.renamed):
        console.print("  [green]identical[/]")


def main() -> int:
    """Parse arguments, extract the map, report it, and write it when asked."""
    parser = argparse.ArgumentParser(
        prog="functions-extract.py",
        description=(
            "Derive the Numbers formula function index map from the application "
            "binary, and report how it differs from the committed one."
        ),
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("--numbers", help="path to the Numbers application bundle")
    parser.add_argument(
        "--gaps",
        action="store_true",
        help="list the functions Numbers names that carry no readable index",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"write {generatedPath.relative_to(repositoryRoot)}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --write, print what would be written and write nothing",
    )
    arguments = parser.parse_args()

    try:
        application = locateNumbers(
            Path(arguments.numbers) if arguments.numbers else None
        )
        functionMap = buildMap(application)
    except (ExtractionError, FileNotFoundError, RuntimeError) as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1

    showApplication(application)
    showMap(functionMap, arguments.gaps)
    comparison = compareMaps(functionMap.names, readCommitted(generatedPath))
    showComparison(comparison, generatedPath)

    if not arguments.write:
        console.print(
            "\nRead-only run. Pass --write to update "
            f"{generatedPath.relative_to(repositoryRoot)}."
        )
        return 0

    source = renderModule(functionMap)
    if arguments.dry_run:
        console.print("\n[bold]Would write[/]")
        console.print(source, markup=False, highlight=False)
        return 0

    generatedPath.parent.mkdir(parents=True, exist_ok=True)
    generatedPath.write_text(source)
    console.print(
        f"\n[green]Wrote[/] {escape(str(generatedPath.relative_to(repositoryRoot)))}, "
        f"{len(functionMap.names)} functions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

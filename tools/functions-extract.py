#!/usr/bin/env python3
"""\
pybers function table

Derive the table of Numbers formula functions, each with its index, its name and
the argument counts it accepts, by reading the compiled code of the Numbers on
this machine. Report how it differs from the table committed at
src/pybers/_generated/functions.py.

**Why the binary is the only source.** A `.numbers` package stores a function
call as a bare `uint32` and an argument count, and nothing else. No name and no
signature appears in the archives, in the schemas, or anywhere in the package.
Excel's older binary format numbers its functions the same way and Microsoft
publishes that table as the `Ftab` in `[MS-XLS]`, but the numbering disagrees
completely: `SUM` is 4 there and 168 here, so borrowing it yields plausible
wrong functions rather than a failure.

**This reads the binary. It never runs it.** Nothing here loads, links, executes
or modifies any part of Numbers. The technique of finding the values in compiled
code rather than in a published table comes from the numbers-parser project and
is not claimed as this project's invention.

Three readings, two of them independent, all measured on Numbers 15.4:

    names       every `TSCEFunction_<NAME>` class declares `+functionIndex` as a
                two-instruction method returning its index. 387 classes.
    corroborant `TSCEFormulaCreationMagic` carries one authoring method per
                function, loading the index before a call. It reaches fewer
                functions and exists here to disagree if either reading is
                wrong.
    arity       one 133 KB function builds every `TSCEFunctionSpec`, sending
                `specWithFunctionName:minArgs:maxArgs:...` with the counts as
                literal immediates. 385 calls across eight selector variants.

**A repeating group makes the maximum a floor rather than a ceiling.** `SUM`
declares a maximum of two with a repeating group of one, which is how a document
holding an eight-argument `SUM` is legal. Reading `maxArgs` as a hard limit
rejects real formulas, measured against the documents 2026-09-04.

Numbers' own localized function list decides which extracted names are real. A
class whose name is absent from `en.lproj/TSCalculationEngine.strings` is an
internal spelling rather than a function, which is how `SHOW` and
`RANGE.TRACKING.FORMULA` are excluded without a hand-maintained list to go stale.

Output is committed for the same reason the schemas are: `pip install pybers` has
no Numbers to read. Nothing is written unless --write is passed.

Usage:
    python3 tools/functions-extract.py
    python3 tools/functions-extract.py --gaps
    python3 tools/functions-extract.py --numbers "/Applications/Numbers.app"
    python3 tools/functions-extract.py --write
    python3 tools/functions-extract.py --write --dry-run

Requires rich. Needs no other tooling: the Mach-O parsing and the AArch64
decoding are both Python, so there is no objdump, no c++filt and no
architecture-specific toolchain to install.

UPDATES
2026-10-12  The registry is found by its calls to the spec factories, since
            Numbers 15.4 no longer loads the spec class's address, for PYB-139.
2026-09-04  Names moved to the Objective-C metadata and arity added, for #44.
            The authoring methods reach 324 functions and the classes 346, so
            the first reading became the cross-check rather than the source.
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
__usage__ = "python3 tools/functions-extract.py [options]"

import argparse
import ast
import re
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lib.machoreader import Image, MachOError
from lib.numbersapp import NumbersApplication, locateNumbers
from rich.console import Console
from rich.markup import escape

try:
    from rich_argparse import RichHelpFormatter
except ImportError:  # rich_argparse is optional, per tools/README.md
    RichHelpFormatter = argparse.HelpFormatter  # type: ignore[assignment,misc]

console: Console = Console()

repositoryRoot: Path = Path(__file__).resolve().parent.parent

# Committed, so that naming a function never needs a local Numbers.
generatedPath: Path = repositoryRoot / "src" / "pybers" / "_generated" / "functions.py"

# The calculation engine ships inside the tables framework rather than beside it:
# TSCalculationEngine.framework is a 117 KB shim and the formula code is here.
frameworkName: str = "TSTables"

# Numbers' own function list, which decides which extracted name is a real
# function. Read from the English localization because the table records the
# canonical spelling rather than a display string.
stringsTableName: str = "TSCalculationEngine"

# Measured against real documents in tests/measurements, so a mismatch here is a
# defect in this script rather than a change in Numbers.
knownPairs: dict[str, int] = {"SUM": 168, "IF": 62, "SUMIFS": 231, "ROUND": 126}

functionClassPrefix: str = "TSCEFunction_"
indexSelector: str = "functionIndex"
specSelectorPrefix: str = "specWithFunctionName:"

# `_ZN24TSCEFormulaCreationMagic<length><NAME>E<arguments>`, matched rather than
# demangled because a general demangler for one shape earns nothing.
magicMethod: re.Pattern[str] = re.compile(
    r"^__ZN24TSCEFormulaCreationMagic(\d+)([A-Za-z0-9_]+)E"
)
argumentHelper: str = "__ZN24TSCEFormulaCreationMagic13function_"
nodeBuilder: str = "__ZN22TSCEASTFunctionElement21appendFunctionElement"

# A name Numbers lists as a function looks like this, which keeps error-message
# keys and interface strings out of the coverage count.
functionNamePattern: re.Pattern[str] = re.compile(r"[A-Z][A-Z0-9.]*")

# AArch64 encodings, masked to the fields that identify them. The move mask spans
# both widths, because a zero argument is loaded with the 64-bit form and reading
# only the 32-bit one leaves a stale register behind, which is what made PI first
# read as taking two arguments.
moveMask: int = 0x7F800000
moveValue: int = 0x52800000
moveZeroMask: int = 0xFFFFFFE0
moveZeroValue: int = 0x2A1F03E0
storeHalfwordMask: int = 0xFFC00000
storeHalfwordValue: int = 0x79000000
branchLinkMask: int = 0xFC000000
branchLinkValue: int = 0x94000000
branchLinkOffsetMask: int = 0x03FFFFFF
branchLinkSignBit: int = 0x02000000
branchLinkRange: int = 0x04000000
addressPageMask: int = 0x9F000000
addressPageValue: int = 0x90000000
addImmediateMask: int = 0xFF800000
addImmediateValue: int = 0x91000000
loadRegisterMask: int = 0xFFC00000
loadRegisterValue: int = 0xF9400000
returnInstruction: int = 0xD65F03C0
stubBlockMask: int = ~0x1F

# Argument registers, fixed across all eight spec selector variants: the name is
# always the first argument and the two counts follow it. Only the fourth moves,
# which is why the selector is read rather than assumed.
nameRegister: int = 2
minimumRegister: int = 3
maximumRegister: int = 4
repeatingRegister: int = 5


class ExtractionError(RuntimeError):
    """The binary could not be read, or carries nothing this script recognizes."""


@dataclass(frozen=True)
class NumbersFunction:
    """One function as Numbers declares it: name, index and argument counts.

    `index` is absent for a function the format stores as its own node types
    rather than as an indexed call. `availability` is one of three: offered in
    the function browser, reserved with an index and no argument spec, or
    internal, which Numbers uses itself and does not offer.
    """

    name: str
    index: int | None
    minimumArguments: int
    maximumArguments: int
    repeatingGroupSize: int
    availability: str = "offered"

    @property
    def reserved(self) -> bool:
        """Report whether Numbers declares this and refuses the name."""
        return self.availability == "reserved"

    @property
    def unbounded(self) -> bool:
        """Report whether a repeating group removes the maximum entirely."""
        return self.repeatingGroupSize > 0


@dataclass(frozen=True)
class FunctionTable:
    """An extracted table, and everything a reader needs to judge it."""

    functions: dict[str, NumbersFunction]
    uncovered: tuple[str, ...]
    corroborated: int
    disagreements: tuple[tuple[str, int, int], ...]
    version: str
    build: str


@dataclass(frozen=True)
class TableComparison:
    """How a freshly extracted table differs from the committed one."""

    added: tuple[NumbersFunction, ...]
    removed: tuple[NumbersFunction, ...]
    changed: tuple[tuple[NumbersFunction, NumbersFunction], ...]
    unchangedCount: int


def movedImmediate(word: int) -> tuple[int, int] | None:
    """Return the register and value one immediate move writes, or None."""
    if word & moveMask == moveValue:
        return word & 0x1F, ((word >> 5) & 0xFFFF) << (((word >> 21) & 3) * 16)
    if word & moveZeroMask == moveZeroValue:
        return word & 0x1F, 0
    return None


def branchTarget(word: int, address: int) -> int | None:
    """Return where a `bl` goes, or None when the word is not one."""
    if word & branchLinkMask != branchLinkValue:
        return None
    offset = word & branchLinkOffsetMask
    if offset & branchLinkSignBit:
        offset -= branchLinkRange
    return address + (offset << 2)


def pageAddress(word: int, address: int) -> int:
    """Return the page an `adrp` names, sign-extended as the encoding requires."""
    immediate = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
    if immediate & (1 << 20):
        immediate -= 1 << 21
    return (address & ~0xFFF) + (immediate << 12)


def indexFromClasses(image: Image) -> dict[str, int]:
    """Return every function name and index Numbers declares on its own classes.

    Each `TSCEFunction_<NAME>` class implements `+functionIndex` as one immediate
    move and a return, so the value is a declaration rather than an inference.
    """
    found: dict[str, int] = {}
    for name, objectiveClass in image.objectiveCClasses().items():
        if not name.startswith(functionClassPrefix):
            continue
        implementation = objectiveClass.classMethods.get(indexSelector)
        if implementation is None:
            continue
        offset = image.fileOffset(implementation)
        if offset is None or offset + 8 > len(image.data):
            continue
        word, following = struct.unpack_from("<2I", image.data, offset)
        moved = movedImmediate(word)
        if moved is None or moved[0] != 0 or following != returnInstruction:
            continue
        found[name[len(functionClassPrefix):]] = moved[1]
    if not found:
        raise ExtractionError(
            f"No {functionClassPrefix}* class declares +{indexSelector} as a "
            "constant. This Numbers does not describe its functions the way this "
            "script reads."
        )
    return found


def indexInBody(
    image: Image, address: int, end: int, helpers: set[int], builders: set[int]
) -> int | None:
    """Return the index one authoring method loads, across its three shapes."""
    text = image.sections["__TEXT,__text"]
    body = image.data[
        text.offset + address - text.address : text.offset + end - text.address
    ]
    registers: dict[int, int] = {}
    fromClosure: int | None = None
    for position in range(0, len(body) & ~3, 4):
        word = struct.unpack_from("<I", body, position)[0]
        moved = movedImmediate(word)
        if moved is not None:
            registers[moved[0]] = moved[1]
            continue
        if word & storeHalfwordMask == storeHalfwordValue:
            # A volatile function stores its index into the closure it builds
            # instead of passing it, so the halfword store is the only carrier.
            fromClosure = registers.get(word & 0x1F, fromClosure)
            continue
        target = branchTarget(word, address + position)
        if target is None:
            continue
        if target in helpers and 0 in registers:
            return registers[0]
        if target in builders and 1 in registers:
            return registers[1]
        registers = {}
    return fromClosure


def indexFromAuthoringMethods(image: Image) -> dict[str, int]:
    """Return the indices the authoring helper class carries, for corroboration.

    Reaches fewer functions than the classes do, and exists so that two readings
    of one binary can disagree rather than one being trusted alone.
    """
    helpers = {a for a, n in image.symbols.items() if n.startswith(argumentHelper)}
    builders = {a for a, n in image.symbols.items() if n.startswith(nodeBuilder)}
    if not helpers or not builders:
        return {}

    text = image.sections["__TEXT,__text"]
    ordered = sorted(
        address
        for address in image.symbols
        if text.address <= address < text.address + text.size
    )
    emitted: dict[str, set[int]] = {}
    for position, address in enumerate(ordered):
        matched = magicMethod.match(image.symbols[address])
        if matched is None:
            continue
        name = matched.group(2)[:int(matched.group(1))]
        if name.startswith("function_"):
            continue
        end = (
            ordered[position + 1]
            if position + 1 < len(ordered)
            else text.address + text.size
        )
        found = indexInBody(image, address, end, helpers, builders)
        if found is not None:
            emitted.setdefault(name, set()).add(found)
    # A name emitting several indices is an internal helper that builds one of
    # several formulas rather than a function, so it corroborates nothing.
    return {
        name: next(iter(values))
        for name, values in emitted.items()
        if len(values) == 1
    }


def specFactories(image: Image) -> dict[int, bool]:
    """Return each spec factory stub, and whether it carries a repeating group.

    Read from the stub's own selector load rather than assumed, so a renamed or
    reordered selector fails here instead of shifting every argument by one.
    """
    stubs = image.sections.get("__TEXT,__objc_stubs")
    if stubs is None:
        raise ExtractionError("No __objc_stubs section; the spec sends are unreadable.")
    pages: dict[int, int] = {}
    factories: dict[int, bool] = {}
    for step in range(0, stubs.size, 4):
        word = struct.unpack_from("<I", image.data, stubs.offset + step)[0]
        address = stubs.address + step
        if word & addressPageMask == addressPageValue:
            pages[word & 0x1F] = pageAddress(word, address)
        elif word & loadRegisterMask == loadRegisterValue:
            base = pages.get((word >> 5) & 0x1F)
            if base is None:
                continue
            selector = image.stringAt(
                image.pointerAt(base + (((word >> 10) & 0xFFF) * 8))
            )
            if selector and selector.startswith(specSelectorPrefix):
                # Every stub is one aligned block, so masking the address gives
                # its entry point, which is what a call site branches to.
                factories[address & stubBlockMask] = "repeatingGroupSize:" in selector
    if not factories:
        raise ExtractionError(
            f"No stub sends a {specSelectorPrefix}... selector, so the argument "
            "counts cannot be read from this Numbers."
        )
    return factories


def specRegistry(image: Image, factories: dict[int, bool]) -> tuple[int, int]:
    """Return the extent of the function that builds every spec.

    Located by counting calls to the spec factories rather than by address,
    because it carries no symbol and its address moves with every release. In
    Numbers 15.4 it no longer loads the spec class's address directly, so a
    count of class references found nothing there.
    """
    text = image.sections["__TEXT,__text"]
    counts: Counter[int] = Counter()
    for step in range(0, text.size & ~3, 4):
        word = struct.unpack_from("<I", image.data, text.offset + step)[0]
        address = text.address + step
        if branchTarget(word, address) not in factories:
            continue
        bounds = image.functionBounds(address)
        if bounds is not None:
            counts[bounds[0]] += 1
    if not counts:
        raise ExtractionError("Nothing in this binary constructs a function spec.")
    bounds = image.functionBounds(counts.most_common(1)[0][0])
    if bounds is None:
        raise ExtractionError("The spec registry has no readable extent.")
    return bounds


def arityFromRegistry(image: Image) -> dict[str, tuple[int, int, int]]:
    """Return each function's minimum, maximum and repeating group size.

    One pass over the registry builder, tracking immediates and materialized
    addresses. Registers are deliberately not cleared at a call: the compiler
    sets a call's arguments after the last thing that could clobber them, so the
    most recent write before a send is the value being passed.
    """
    factories = specFactories(image)
    start, end = specRegistry(image, factories)
    text = image.sections["__TEXT,__text"]

    registers: dict[int, int] = {}
    pages: dict[int, int] = {}
    specs: dict[str, tuple[int, int, int]] = {}
    for address in range(start, end, 4):
        word = struct.unpack_from(
            "<I", image.data, text.offset + address - text.address
        )[0]
        moved = movedImmediate(word)
        if moved is not None:
            registers[moved[0]] = moved[1]
            pages.pop(moved[0], None)
            continue
        if word & addressPageMask == addressPageValue:
            pages[word & 0x1F] = pageAddress(word, address)
            registers.pop(word & 0x1F, None)
            continue
        if word & addImmediateMask == addImmediateValue:
            base = pages.get((word >> 5) & 0x1F)
            if base is not None:
                pages[word & 0x1F] = base + ((word >> 10) & 0xFFF)
                registers.pop(word & 0x1F, None)
            continue
        target = branchTarget(word, address)
        if target is None or target not in factories:
            continue
        name = image.constantStringAt(pages.get(nameRegister, 0))
        minimum = registers.get(minimumRegister)
        maximum = registers.get(maximumRegister)
        if name is None or minimum is None or maximum is None:
            continue
        specs[name] = (
            minimum,
            maximum,
            registers.get(repeatingRegister, 0) if factories[target] else 0,
        )
    return specs


def displayName(symbolName: str) -> str:
    """Return the spelling Numbers uses for a name written in C or C++.

    A leading underscore avoids a collision with a macro, `_MAX` being `MAX`, and
    an interior underscore stands for the dot in `REFERENCE.NAME`.
    """
    return symbolName.lstrip("_").replace("_", ".")


def buildTable(application: NumbersApplication) -> FunctionTable:
    """Extract the function table, validated against Numbers' own name list."""
    image = Image(application.frameworkBinary(frameworkName))
    declared = indexFromClasses(image)
    corroborant = indexFromAuthoringMethods(image)
    arities = arityFromRegistry(image)
    known = set(application.localizedStrings(stringsTableName))

    # The two sources spell an internal function differently, the class calling
    # it SPILL and the registry __SPILL, so specs are also indexed by the name
    # a reader would recognize.
    arityByDisplay = {displayName(key): value for key, value in arities.items()}

    functions: dict[str, NumbersFunction] = {}
    claimed: dict[int, str] = {}

    for symbolName, index in sorted(declared.items()):
        name = displayName(symbolName)
        if index in claimed:
            raise ExtractionError(
                f"Function index {index} is claimed by both {claimed[index]} and "
                f"{name}, so the extraction is reading one of them wrongly."
            )
        if name in functions:
            raise ExtractionError(
                f"Two classes both spell themselves {name}, so a name no longer "
                "identifies one function."
            )
        claimed[index] = name
        arity = (
            arities.get(name)
            or arities.get(symbolName)
            or arityByDisplay.get(name)
        )
        if name not in known:
            # Real, used by Numbers itself, and absent from the list it offers.
            # SPILL is the one measured in a document: every cell a formula
            # spills into holds SPILL($anchor), so dropping these would read a
            # spilled document as an anonymous number.
            availability = "internal"
        elif arity is None:
            # No argument spec means the parser has nothing to accept the name
            # with, which is what Numbers answers for all four of these in
            # tests/measurements/46-formula-rare-functions.
            availability = "reserved"
        else:
            availability = "offered"
        functions[name] = NumbersFunction(
            name, index, *(arity or (0, 0, 0)), availability
        )

    # A function the format stores as its own node types carries a spec and no
    # class, so it has argument counts and no index. LET and LAMBDA are both,
    # and their counts match the signatures Numbers documents in its own
    # function browser.
    for name, arity in sorted(arities.items()):
        if name in known and name not in functions:
            functions[name] = NumbersFunction(name, None, *arity)

    disagreements = tuple(
        (displayName(symbolName), index, declared[symbolName])
        for symbolName, index in sorted(corroborant.items())
        if symbolName in declared and declared[symbolName] != index
    )
    corroborated = sum(
        1 for symbolName, index in corroborant.items()
        if declared.get(symbolName) == index
    )

    uncovered = tuple(sorted(
        name for name in known
        if functionNamePattern.fullmatch(name) and name not in functions
    ))

    for name, expected in knownPairs.items():
        found = functions.get(name)
        if found is None or found.index != expected:
            raise ExtractionError(
                f"{name} read as index {found.index if found else None} rather "
                f"than {expected}. These four pairs are measured against real "
                "documents in tests/measurements, so a disagreement is a defect in "
                "this script rather than a change in Numbers."
            )

    return FunctionTable(
        functions=functions,
        uncovered=uncovered,
        corroborated=corroborated,
        disagreements=disagreements,
        version=application.version,
        build=application.build,
    )


def readCommitted(path: Path) -> dict[str, NumbersFunction] | None:
    """Return the committed table, or None when there is nothing to compare with.

    Read as a literal rather than imported, so comparing depends neither on
    pybers being installed nor on running the file about to be overwritten.
    None covers both an absent file and one written in an older shape, because
    refusing to run until the output is already correct would leave no way to
    correct it.
    """
    if not path.is_file():
        return None
    for statement in ast.parse(path.read_text(), str(path)).body:
        if not isinstance(statement, ast.AnnAssign | ast.Assign):
            continue
        targets = (
            [statement.target] if isinstance(statement, ast.AnnAssign)
            else statement.targets
        )
        named = any(
            isinstance(target, ast.Name) and target.id == "functions"
            for target in targets
        )
        if not named or statement.value is None:
            continue
        try:
            return {
                str(name): NumbersFunction(
                    str(name),
                    None if row[0] is None else int(row[0]),
                    int(row[1]), int(row[2]), int(row[3]), str(row[4]),
                )
                for name, row in ast.literal_eval(statement.value).items()
            }
        except (IndexError, TypeError, ValueError):
            # A table written in an older shape, which the next --write replaces.
            return None
    return None


def compareTables(
    extracted: dict[str, NumbersFunction], committed: dict[str, NumbersFunction]
) -> TableComparison:
    """Report what a regeneration would change, which is what makes it reviewable."""
    added = tuple(
        function for name, function in sorted(extracted.items())
        if name not in committed
    )
    removed = tuple(
        function for name, function in sorted(committed.items())
        if name not in extracted
    )
    changed = tuple(
        (committed[name], function)
        for name, function in sorted(extracted.items())
        if name in committed and committed[name] != function
    )
    unchanged = sum(
        1 for name, function in extracted.items() if committed.get(name) == function
    )
    return TableComparison(added, removed, changed, unchanged)


def renderModule(table: FunctionTable) -> str:
    """Return the source of the generated module, one line per function."""
    entries = "\n".join(
        f'    "{function.name}": ({function.index}, '
        f"{function.minimumArguments}, {function.maximumArguments}, "
        f'{function.repeatingGroupSize}, "{function.availability}"),'
        for _name, function in sorted(table.functions.items())
    )
    total = len(table.functions) + len(table.uncovered)
    return f'''#!/usr/bin/env python3
"""\\
Numbers formula functions, by index. Machine output, do not edit.

Written by tools/functions-extract.py from Numbers {table.version}
(build {table.build}). A correction made here is destroyed by the next
extraction; correct the extractor instead.

Each row is the index, the minimum argument count, the maximum, the size of the
repeating group that makes the maximum a floor rather than a ceiling, and how
the function may be used. A group of zero means the maximum is exact.

An index of None means the format stores the function as its own node types
rather than as an indexed call. Availability is one of three: offered in the
function browser, reserved with an index and no argument spec so Numbers
refuses the name, or internal, which Numbers uses itself and never offers.

{len(table.functions)} of the {total} functions Numbers names are covered.
"""

functions: dict[str, tuple[int | None, int, int, int, str]] = {{
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


def showTable(table: FunctionTable, showGaps: bool) -> None:
    """Print what was extracted, and everything it could not reach."""
    total = len(table.functions) + len(table.uncovered)
    values = table.functions.values()
    reserved = sorted(f.name for f in values if f.availability == "reserved")
    internal = sorted(f.name for f in values if f.availability == "internal")
    withoutIndex = sorted(f.name for f in values if f.index is None)
    unbounded = sum(1 for f in values if f.unbounded and not f.reserved)
    console.print(
        f"\n[bold]{len(table.functions)}[/] of {total} names Numbers lists are "
        "described here."
    )
    console.print(f"  {unbounded:>4}  accept a repeating group, so no fixed maximum")
    console.print(
        f"  {len(reserved):>4}  reserved: an index and no argument spec, so "
        "Numbers refuses the name"
    )
    if reserved:
        console.print(f"        {escape(', '.join(reserved))}", highlight=False)
    console.print(
        f"  {len(internal):>4}  internal: real and used by Numbers, never offered"
    )
    if internal:
        console.print(f"        {escape(', '.join(internal))}", highlight=False)
    console.print(
        f"  {len(withoutIndex):>4}  stored as node types rather than as an "
        "indexed call"
    )
    if withoutIndex:
        console.print(f"        {escape(', '.join(withoutIndex))}", highlight=False)
    colour = "green" if not table.disagreements else "red"
    console.print(
        f"  {table.corroborated:>4}  corroborated by the authoring methods, "
        f"[{colour}]{len(table.disagreements)} disagreement(s)[/]"
    )
    for name, wasRead, declaredAs in table.disagreements:
        console.print(
            f"        [red]{escape(name)}[/] read {wasRead}, declared {declaredAs}"
        )
    for label, names, listed in (
        ("listed by Numbers with nothing behind the name", table.uncovered, showGaps),
    ):
        console.print(f"  {len(names):>4}  {label}")
        if names and listed:
            console.print(f"        {escape(', '.join(names))}", highlight=False)
        elif names:
            console.print("        pass --gaps to list them")

    console.print("\n[bold]Known pairs[/], each measured against a real document:")
    for name, index in knownPairs.items():
        function = table.functions[name]
        bound = "unbounded" if function.unbounded else function.maximumArguments
        console.print(
            f"  {index:>4}  {escape(name)}, "
            f"{function.minimumArguments} to {bound} argument(s)"
        )


def showComparison(comparison: TableComparison | None, path: Path) -> None:
    """Print how the extracted table differs from the committed one."""
    console.print(f"\n[bold]Against {escape(str(path.relative_to(repositoryRoot)))}[/]")
    if comparison is None:
        console.print(
            "  [yellow]nothing to compare with[/], the file is absent or written "
            "in an older shape"
        )
        return
    console.print(f"  {comparison.unchangedCount} unchanged")
    for function in comparison.added:
        console.print(f"  [green]added[/]    {escape(function.name)}")
    for function in comparison.removed:
        console.print(f"  [red]removed[/]  {escape(function.name)}")
    for was, now in comparison.changed:
        console.print(
            f"  [yellow]changed[/]  {escape(now.name)}  "
            f"{was.index} {was.minimumArguments}..{was.maximumArguments}/"
            f"{was.repeatingGroupSize} {escape(was.availability)} -> "
            f"{now.index} {now.minimumArguments}..{now.maximumArguments}/"
            f"{now.repeatingGroupSize} {escape(now.availability)}"
        )
    if not (comparison.added or comparison.removed or comparison.changed):
        console.print("  [green]identical[/]")


def main() -> int:
    """Parse arguments, extract the table, report it, and write it when asked."""
    parser = argparse.ArgumentParser(
        prog="functions-extract.py",
        description=(
            "Derive the Numbers formula function table from the application "
            "binary, and report how it differs from the committed one."
        ),
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("--numbers", help="path to the Numbers application bundle")
    parser.add_argument(
        "--gaps",
        action="store_true",
        help="list the functions Numbers names that this run could not read",
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
        table = buildTable(application)
    except (ExtractionError, MachOError, FileNotFoundError, RuntimeError) as exc:
        console.print(f"[red]{escape(str(exc))}[/]")
        return 1

    showApplication(application)
    showTable(table, arguments.gaps)
    committed = readCommitted(generatedPath)
    showComparison(
        None if committed is None else compareTables(table.functions, committed),
        generatedPath,
    )

    if not arguments.write:
        console.print(
            "\nRead-only run. Pass --write to update "
            f"{generatedPath.relative_to(repositoryRoot)}."
        )
        return 0

    source = renderModule(table)
    if arguments.dry_run:
        console.print("\n[bold]Would write[/]")
        console.print(source, markup=False, highlight=False)
        return 0

    generatedPath.parent.mkdir(parents=True, exist_ok=True)
    generatedPath.write_text(source)
    console.print(
        f"\n[green]Wrote[/] {escape(str(generatedPath.relative_to(repositoryRoot)))}, "
        f"{len(table.functions)} functions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

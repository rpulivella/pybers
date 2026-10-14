#!/usr/bin/env python3
"""\
The function table read out of the Numbers binary: indices, names and argument counts.

UPDATES
2026-10-14  Moved here from `functions_extract.py`, which keeps its command line,
            for PYB-204.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"

import re
import struct
from collections import Counter

from tools.local.lib.functiontable import (
    FunctionTable,
    NumbersFunction,
)
from tools.local.lib.machoreader import Image
from tools.local.lib.numbersapp import NumbersApplication

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


def readMovedImmediate(word: int) -> tuple[int, int] | None:
    """Return the register and value one immediate move writes, or None."""
    if word & moveMask == moveValue:
        return word & 0x1F, ((word >> 5) & 0xFFFF) << (((word >> 21) & 3) * 16)
    if word & moveZeroMask == moveZeroValue:
        return word & 0x1F, 0
    return None


def findBranchTarget(word: int, address: int) -> int | None:
    """Return where a `bl` goes, or None when the word is not one."""
    if word & branchLinkMask != branchLinkValue:
        return None
    offset = word & branchLinkOffsetMask
    if offset & branchLinkSignBit:
        offset -= branchLinkRange
    return address + (offset << 2)


def findPageAddress(word: int, address: int) -> int:
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
        moved = readMovedImmediate(word)
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
        moved = readMovedImmediate(word)
        if moved is not None:
            registers[moved[0]] = moved[1]
            continue
        if word & storeHalfwordMask == storeHalfwordValue:
            # A volatile function stores its index into the closure it builds
            # instead of passing it, so the halfword store is the only carrier.
            fromClosure = registers.get(word & 0x1F, fromClosure)
            continue
        target = findBranchTarget(word, address + position)
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


def findSpecFactories(image: Image) -> dict[int, bool]:
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
            pages[word & 0x1F] = findPageAddress(word, address)
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


def findSpecRegistry(image: Image, factories: dict[int, bool]) -> tuple[int, int]:
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
        if findBranchTarget(word, address) not in factories:
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


def readArityFromRegistry(image: Image) -> dict[str, tuple[int, int, int]]:
    """Return each function's minimum, maximum and repeating group size.

    One pass over the registry builder, tracking immediates and materialized
    addresses. Registers are deliberately not cleared at a call: the compiler
    sets a call's arguments after the last thing that could clobber them, so the
    most recent write before a send is the value being passed.
    """
    factories = findSpecFactories(image)
    start, end = findSpecRegistry(image, factories)
    text = image.sections["__TEXT,__text"]

    registers: dict[int, int] = {}
    pages: dict[int, int] = {}
    specs: dict[str, tuple[int, int, int]] = {}
    for address in range(start, end, 4):
        word = struct.unpack_from(
            "<I", image.data, text.offset + address - text.address
        )[0]
        moved = readMovedImmediate(word)
        if moved is not None:
            registers[moved[0]] = moved[1]
            pages.pop(moved[0], None)
            continue
        if word & addressPageMask == addressPageValue:
            pages[word & 0x1F] = findPageAddress(word, address)
            registers.pop(word & 0x1F, None)
            continue
        if word & addImmediateMask == addImmediateValue:
            base = pages.get((word >> 5) & 0x1F)
            if base is not None:
                pages[word & 0x1F] = base + ((word >> 10) & 0xFFF)
                registers.pop(word & 0x1F, None)
            continue
        target = findBranchTarget(word, address)
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


def formatDisplayName(symbolName: str) -> str:
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
    arities = readArityFromRegistry(image)
    known = set(application.localizedStrings(stringsTableName))

    # The two sources spell an internal function differently, the class calling
    # it SPILL and the registry __SPILL, so specs are also indexed by the name
    # a reader would recognize.
    arityByDisplay = {formatDisplayName(key): value for key, value in arities.items()}

    functions: dict[str, NumbersFunction] = {}
    claimed: dict[int, str] = {}

    for symbolName, index in sorted(declared.items()):
        name = formatDisplayName(symbolName)
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
        (formatDisplayName(symbolName), index, declared[symbolName])
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

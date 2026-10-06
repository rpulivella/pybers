#!/usr/bin/env python3
"""\
Locate the Numbers install on this machine, and read its identity.

Shared by every script that extracts something from the application binary, so
that finding Numbers is one implementation rather than one per extractor. It
prints nothing and mutates nothing; a caller decides what to do with the result.

**The bundle filename cannot be relied upon.** The install this repository is
developed against is `/Applications/Numbers Creator Studio.app`, carrying bundle
identifier `com.apple.Numbers` and executable `Numbers`. A locator that trusted
`/Applications/Numbers.app` would report Numbers absent on the one machine that
has it, which is why the search falls back to inspecting bundle contents.

UPDATES
2026-09-04  Written for #44, moved out of protos-extract.py, which was the only
            caller until the function-index extractor needed the same search.
"""
from __future__ import annotations

__author__ = "Richard P Ulivella"
__copyright__ = "Copyright 2026 Richard P Ulivella"
__license__ = "Apache-2.0"
__version__ = "0.1.0"
__email__ = "pybers@richardulivella.com"
__status__ = "Development"
__date__ = "2026/09/04"
__usage__ = "imported, never run: tools/lib holds no commands"

import plistlib
from dataclasses import dataclass
from pathlib import Path

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

    def frameworkBinary(self, name: str) -> Path:
        """Return the binary of one bundled framework, by framework name.

        The iWork frameworks are versioned bundles, so the binary sits under
        `Versions/A` rather than at the top level. Raises when it is absent,
        because a caller asking for a framework by name has no fallback.
        """
        binary = (
            self.bundlePath
            / "Contents"
            / "Frameworks"
            / f"{name}.framework"
            / "Versions"
            / "A"
            / name
        )
        if not binary.is_file():
            raise FileNotFoundError(
                f"{name}.framework carries no binary at {binary}. This Numbers "
                f"is version {self.version}, and the frameworks it ships with "
                "may have been reorganized."
            )
        return binary

    def localizedStrings(self, name: str, language: str = "en") -> dict[str, str]:
        """Return one localized .strings table from the application resources.

        Read through `plistlib` because a modern .strings file is a binary
        property list rather than the old text form.
        """
        path = (
            self.bundlePath
            / "Contents"
            / "Resources"
            / f"{language}.lproj"
            / f"{name}.strings"
        )
        if not path.is_file():
            raise FileNotFoundError(f"No {name}.strings for {language} at {path}.")
        try:
            loaded = plistlib.loads(path.read_bytes())
        except (plistlib.InvalidFileException, ValueError) as exc:
            raise RuntimeError(f"{path} is not a readable strings file.") from exc
        return {str(key): str(value) for key, value in loaded.items()}


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
    """Find the Numbers install to read from, searching only if it is not where
    expected.

    An explicit path is trusted and its failure is loud. Otherwise the usual
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

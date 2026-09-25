## Ticket
Link: https://github.com/rpulivella/pybers/issues/7
Closes #7

`pip install -e ".[dev]"` in a fresh virtual environment is now enough to run `python3 -m build --wheel`. Before this, building a wheel worked only if `build` happened to be installed somewhere on the machine, which is the gap the ticket named.

The change is three lines of dependency declaration, and building a wheel for the first time settled two things nobody had checked.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

### AC 3 already passed, and is reported rather than claimed

The ticket asks that the wheel carry `LICENSE` and `NOTICE` under `dist-info/licenses/`. It already did. Nothing in this PR made that true, and it is worth recording as a measurement rather than as work: the Apache-2.0 choice in `CLAUDE.md` was made partly for the `NOTICE` file, which is where the credit to numbers-parser lives, and nobody had checked that it survives packaging. It does.

The same build settled a concern raised at the start and not in the ticket. `CLAUDE.md` chose Hatchling because setuptools omits non-Python files and fails silently doing it, and #4 grew the count of such files by 33 when the protobuf type stubs landed. The wheel carries 54 `.py`, 33 `.pyi`, 33 `.proto` and `pybers/protos/README.md`, so every one of them ships.

### AC 1 was rewritten before it was met

It asked for `build` "with an exact pin, following the grouped-comment convention the existing dependencies use", and those two clauses contradict each other: no dependency in `pyproject.toml` has ever been pinned exactly, including the runtime one. `CLAUDE.md` claimed the opposite and has been corrected rather than extended, replacing the rule with what the file has always done and the reason it is right.

A library that pins exactly makes itself uninstallable beside anything else pinning the same package differently. The choice of exact versions belongs to whoever assembles an environment, not to a dependency of it. So `build>=1.2.0`, a floor like its seven neighbors.

### How it was verified

The environment was rebuilt from nothing rather than reused, because this repository's own venv has accumulated packages all day and would prove nothing. A fresh venv with only `pip install -e ".[dev]"` failed to import `build` before the change and built a wheel after it, which is what makes AC 2 a result rather than an assumption. Both the venv and both wheels were written outside the repository, so no build artifact reached the working tree.

## Preconditions / setup for testing
None. `pip install -e ".[dev]"` now brings `build` along with the rest.

## Breaking Changes
**CI / automation / build**: The `dev` extra gains `build`. `hatchling` is deliberately not added: it belongs in `[build-system]` `requires`, where pip installs it into an isolated build environment on its own.

**Object model (public dataclass fields)**: None.

**Archive round-trip**: None. No library code changed.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] Round-trip / golden-file tests pass for any archive-layer change
- NA I added or updated pytest tests covering the change

The last item is NA because the change is three lines of dependency metadata with no code path to exercise. What would need testing is that a fresh environment can build a wheel, and that cannot run in CI without a network install of the project into a clean interpreter, which is #5's territory rather than this ticket's. It was verified by hand instead, and the method is described above.

## Screenshot(s) / video(s)
None

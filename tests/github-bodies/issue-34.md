As a maintainer I want the declared Python floor to be the version this project is built and tested on, so that `requires-python` is a supported claim rather than an untested one.

1. `pyproject.toml` declares 3.14 as the minimum, so `pip install` on an earlier interpreter is refused at resolution time rather than succeeding into a failure later.
2. Every version claim in prose agrees with it. `README.md` and `scripts/README.md` each state a floor today, and no file is left naming a version the project does not support.
3. Ruff and mypy check against the new floor without either naming a version of its own, since both already read `requires-python`.
4. The three `UP047` findings that appear in `src/pybers/model/sheet.py` at any target above 3.11 are resolved in the code by adopting the type-parameter syntax.
5. All four preflight gates pass on 3.14, with no ignore, narrowed rule set, or per-line suppression added anywhere to make that true.
6. Every dependency installs on 3.14 from a clean environment, `protobuf` included, so a fresh install succeeds at the declared floor rather than only in this developer's environment.
7. CI runs on 3.14 with no edit to `.github/workflows/preflight.yml`, which proves the version claim lives only in `pyproject.toml`.
8. Every dependency floor names a version the project runs on, in both the development environment and a clean install, rather than whatever was current when the line was written. Where a floor is derived from something mechanical, such as the protobuf gencode version, the derivation is recorded and the declared floor is stated as the separate, higher number.

## SPEC

- **Both linters follow `requires-python` and neither pins a version of its own**, so raising the floor is the whole of what moves them. Measured 2026-09-03: it fires exactly three `UP047` findings, all in `src/pybers/model/sheet.py`, and identically at py312, py313 and py314, so the trigger is leaving 3.11 rather than reaching 3.14. The tree is clean at the current floor.
- **`NamedT` at `sheet.py:75` becomes unused once those three functions carry their own type parameters**, and nothing in the selected rule set reports a stale module-level `TypeVar`, so it survives as dead code unless it is removed deliberately.
- **The 32 `from __future__ import annotations` lines are not affected.** PEP 649 makes deferred evaluation the default in 3.14, which makes them look redundant, but ruff does not flag them at py314. Removing them is a separate question rather than part of this.

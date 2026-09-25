As a maintainer I want the packaging tools declared as dependencies so that building a wheel does not depend on what happens to be installed.

1. `build` appears in the `dev` extra in `pyproject.toml` declared the way its neighbors are, as a floor rather than an exact pin, with the grouped comment the existing dependencies carry. Corrected 2026-09-02: this asked for an exact pin and for the existing convention in one sentence, and no dependency in the file has ever been pinned exactly. `CLAUDE.md` claimed otherwise and was corrected to match.
2. `pip install -e ".[dev]"` in a fresh virtual environment is enough to run `python3 -m build --wheel`.
3. The built wheel carries `LICENSE` and `NOTICE` under `dist-info/licenses/`.

## SPEC

`hatchling` does not belong in the extra. It is already declared in `[build-system]` `requires`, which is where a build backend belongs, and pip installs it into the isolated build environment automatically.

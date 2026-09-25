As a contributor I want ruff and mypy to run against this codebase so that code review
covers style and typing mechanically rather than by eye.

1. `pip install -e ".[dev]"` installs ruff and mypy.
2. `ruff check .` runs clean on the current tree.
3. `mypy` runs clean on `src/pybers/`.
4. Ruff does not report the camelCase house style as a violation.
5. Both continue to exclude `src/pybers/_generated/` and `src/pybers/protos/`, which are
   machine output and are never hand-edited.
6. The chosen rule sets are recorded in `pyproject.toml` with a comment saying why each
   is on, so a future reader does not have to guess.
7. `mypy` covers `scripts/` and rejects a call whose arguments do not match the signature
   it calls. Two such calls sat undiscovered in `scripts/pr.py` until the first pull
   request this repository opened ran one of them, and the second was on the merge path.

## SPEC

Filed as Concept because two decisions are open.

- Which ruff rule set survives this repository's conventions. `N`, the pep8-naming set,
  flags camelCase functions and variables, which this repository uses deliberately. Either
  `N` is off entirely, or its naming rules are ignored and the rest kept.
- How strictly mypy runs. The codebase carries full type hints already, so strict mode is
  plausible, and the untyped protobuf modules are excluded already.

`[tool.ruff]` and `[tool.mypy]` exist in `pyproject.toml` today but carry exclude stanzas
only, with no rule selection, and neither tool is installed. Nothing lints this code at
present.

Do not widen `scripts/standards-check.py` to cover any of this. That script checks prose,
and code linting was deliberately removed from it.

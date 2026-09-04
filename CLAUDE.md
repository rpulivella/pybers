# pybers

A clean, round-trip-tested Python library for reading and writing Apple Numbers
documents. Built in deep respect for Apple Numbers itself, the goal is for editing a
`.numbers` file programmatically to be as reliable as using Numbers by hand.

Two consumers, both from day one: a library (`import pybers`) and a CLI/TUI on top of
it. Neither `pybers.model` nor `pybers.numbersfile` may import anything front-end or
print anything. `pybers.cli` and `pybers.tui` do not exist yet.

Reasoning for settled decisions lives in `docs/decisions.md`. Format measurements live
in `tests/fixtures/findings-*.md`. **Read the findings index before designing anything**,
because several of them invalidate the obvious approach.

## Build and gates

```bash
.venv/bin/python3 -m pytest              # the suite, that exact spelling
.venv/bin/python3 scripts/pr-preflight-check.py   # all four gates, what CI runs
```

pytest alone is a partial answer. The preflight runs pytest, the prose gate, ruff and
mypy in one pass and reports all four.

## Agents

- Do not preserve backward compatibility. Remove obsolete paths rather than adding
  compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid
  speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to end and
  add each feature on top of something that already works.
- Make architectural decisions for the long term. Do not accept a stopgap.
- Write no documentation unless asked.

## Engineering approach

- Understand the owning feature and trace the full path before editing: model, reader,
  writer, the archives touched, and the calculation engine.
- For a nontrivial change, identify the source of truth, the state owner, the
  invariants, the failure behavior, and the file placement before writing code.
- Keep one authoritative owner for mutable state. Derived state is computed, or cached
  with an explicit invalidation contract.
- Reuse existing operations. Do not write a second implementation because the caller is
  the reader, the writer, a CLI, or a test.
- Place code with the feature that owns it. `pybers.numbersfile` is format
  infrastructure used by more than one feature, never a dumping ground.
- **No module under `pybers.model` may import `pybers.numbersfile` at module scope.**
  A function-local import is the only form allowed, and `sheet.py` guards its one type
  reference behind `TYPE_CHECKING`. `Document` carries archive state as well as model
  state, excluded from equality and `repr`, so saving mutates what was read.

## The format decides the design

Seven facts that make the obvious approach wrong. Each is measured; see the findings.

- **Numbers are decimal128, never `float`.** A binary float introduces rounding error
  into a document that never had any.
- **A formula is a postfix AST, not text.** There is no formula text anywhere in the
  package, so there is nothing to parse and nothing to regex.
- **A reference is a signed offset from the cell holding it**, and `$` is two booleans
  per axis. Moving a formula therefore rewrites nothing.
- **Merges are stored as formulas.** A structural edit that ignores the merge store is
  what caused the phantom-merge-anchor defect.
- **Color carries a color space**, and a **named style plus variation** is how all text
  formatting works.
- **Run indices count UTF-16 code units, not Python characters.** BMP text agrees
  exactly, which is why earlier fixtures validated and proved nothing.
- **Numbers shares style archives by reference.** Twelve styles back twenty-one shapes,
  so handing out a mutable decoded object turns one edit into a silent restyle of
  seven. The frozen-`Style` contract holds on the READ path, not only when writing.

**A wrong offset yields a wrong number, not an exception.** That is why every claim
about the format is measured against a fixture that labels its own contents.

## Correctness

- Working on the happy path is not sufficient. Enumerate the boundary, lifecycle and
  failure cases, and decide which layer owns each.
- Validate empty, zero, negative, maximum, malformed, duplicated, missing and
  unsupported inputs as applicable.
- A no-op must report accurately and must not write anything.
- Preserve document invariants on every failure path. Partial success is either
  resumable and reported as such, or rolled back.
- Carry through what is not understood. An unrecognized cell type, node type or archive
  survives a round trip rather than being dropped or interpreted.
- Never damage a document to make an operation succeed. Refuse and say exactly why.
- `RuntimeError` subclasses for internal failures, always `raise ... from exc`. No bare
  `except Exception: pass`, and no `try:`/`pass` at a boundary where failure changes the
  outcome.

## House style

- **camelCase** for functions, variables and parameters. Modules stay lowercase, classes
  PascalCase. The linter is configured for this, not against it.
- **Method names are subject first, verb last**: `rowAdd`, `cellStyleRemove`,
  `cellFormatNumberApply`. Sorting then groups everything acting on a row together. The
  subject is as specific as the method. Module-level functions keep verb-first names,
  which is why the entry point is `pybers.open`.
- **Dataclasses, never `TypedDict`.** Frozen where immutability keeps a defect out.
- Full type hints, modern syntax (`list[str]`, `X | None`), never `typing.List`.
- `pathlib.Path` exclusively, f-strings exclusively.
- Never shell out when a Python library can do the work.
- **Ticket prefix `PYB`.** `PYB-34` in prose, `PR #38` for pull requests, both parts
  always. Commit subjects keep the bare `[34]`; `Closes #34` keeps its `#`.
- Module header on every file: `#!/usr/bin/env python3`, docstring, then `__author__`
  through `__date__`. **No `# -*- coding: utf-8 -*-`**, dropped 2026-09-02, `UP009`.

## Comments and docstrings

Verbosity is this repository's standing failure. Prefer precise names and small
functions over explanation.

- **Public API, five lines maximum.** Anything re-exported through `pybers/__init__.py`
  is read in an editor tooltip: a one-line imperative summary, then at most a short why.
- **Internal, twelve lines soft limit**, and only to record a measurement, an invariant,
  or a format trap that would otherwise be rediscovered the hard way.
- **Longer than that belongs in `tests/fixtures/findings-*.md`** with a one-line pointer.
  A docstring is the wrong container for a corpus survey.
- **Comments are one line, and say why.** Never narrate code, restate a name, describe
  the current patch, leave removal breadcrumbs, or comment out code.
- Module docstrings carry a dated `UPDATES` block. No contractions anywhere.
- Remove dead code, unused state and temporary diagnostics before finishing.

## Tests

- **The base test**: read a real fixture and write it back unchanged, and the archives
  are identical.
- **Every mutation earns a golden file**: real fixture in, one mutation, confirmed once
  in real Numbers, then locked in as a permanent regression check.
- One test establishes one invariant or regression, with only the setup that makes it
  clear. Descriptive names, and no comments narrating arrange, act and assert.
- Every bug fix earns a regression test that fails for the original defect.
- Test negative paths: validation, no-op, partial failure, and invariant preservation.
- Unique temporary directories, cleaned up. Never write into `tests/fixtures/`.
- pytest functions and fixtures, not `TestCase` classes.

### Who verifies what

- **The agent owns unit tests.** Write them, run them, and run the full preflight before
  claiming anything.
- **Only Numbers can confirm a golden.** Every other test checks pybers against pybers,
  which can agree with itself while both halves are wrong. **Do not claim a golden
  passed until the user confirms it in Numbers**, and record the date and version in
  `tests/golden/README.md`.
- **Confirm with Quick Look AND Numbers.** Quick Look renders the STORED value and does
  not recalculate, so the pair separates what pybers wrote from what Numbers made of it.
  Numbers' own display can also lag its state; reselecting a cell refreshes it, so one
  screenshot is not proof.

## Writing a file

- Mutate the archives that were read rather than constructing new ones, so whatever the
  model does not yet represent survives untouched.
- Stage a complete package outside the destination and install it atomically. Unique
  temporary paths, cleaned on success and on failure alike.
- Never write into a `.numbers` file the user may have open.

## Status

`pybers.model` and `pybers.numbersfile` exist and are tested. The reader handles zip,
IWA frames, pure-Python Snappy, length-prefixed protobuf archives, cell values and
formulas. The writer writes a package back with one bounded, documented difference in
the zip envelope, and edits values, merges and formulas.

**The format is mapped; the model binding is not.** Forty-six fixtures under
`tests/fixtures/` each label their own contents, so a decode is verifiable rather than
plausible.

Apache-2.0. Hatchling, not setuptools. Dependencies are declared as floors, never pins.
This is its own repository, on `develop`.

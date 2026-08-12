# pybers

A clean, round-trip-tested Python library for reading and writing Apple Numbers
documents. Built in deep respect for Apple Numbers itself — the goal is for editing a
`.numbers` file programmatically to be as reliable as using Numbers by hand.

## Why this exists

The a renovation-budget project used a patched fork of `numbers-parser`
(vendored here at `reference/numbers-parser/`, with the rationale for each fix in
`reference/patches/`) to edit real `.numbers` files directly. Over that project we hit
four real correctness bugs in that fork:

1. `Table.write()` silently dropped a cell's `Style` (alignment, fill, font) unless a
   `preserve_format=True` flag was passed, and even then only worked after a deeper fix.
2. `set_cell_style()` assigned a `Style` object by raw Python reference, so two cells
   could share the identical mutable object — mutating one cell's style at save time
   silently corrupted an unrelated cell's formatting.
3. The row-insert helper's reference-shift regex moved *both* ends of a range token
   (`C3:C25` → `C4:C26`) when only the end nearer the insertion point should move,
   silently dropping rows from the start of `SUMIFS`-style ranges.
4. A number-format decoder crashed (`TypeError`) on certain `None`-valued fields instead
   of defaulting them.

Plus known, never-fixed gaps: fragile merged-cell handling (a phantom merge-anchor could
throw `ValueError: Value out of range` at save time), and no way to relocate a block of
cells as a unit. Patching an inherited, abandoned branch adhoc, bug by bug, is what
produced the trust problem this library exists to fix. This is a clean break, not a
continuation.

**New project, not a fork — decided.** A GitHub-style fork carries git lineage and
implies staying API-compatible with upstream `numbers-parser`; neither is true of the
approach here (dataclasses, camelCase, a dual-consumer library/CLI split, named styles).
`reference/numbers-parser/` is vendored source to study, copied in with its `.git`
history stripped (like `another project`'s `reference/ola/`), not a dependency
this project extends.

**Python, not Rust — decided.** The reverse-engineered iWork archive protobuf schemas
already exist in Python; rebuilding that reverse-engineering in Rust would re-derive the
hard part for no functional gain. The actual use case (Python scripts driving real
`.numbers` edits end-to-end) and the stated goal (`pip install pybers`) are both
Python-ecosystem targets, and `.numbers` files are small enough that this is not a
performance-bound workload. If a Rust core is ever wanted, PyO3 bindings are the path —
not a rewrite.

## Core design contract

- Read an archive → typed object model (`pybers.model`) → write it back.
- **Base test**: read a real fixture file and write it back with zero changes → output is
  byte-identical (or protobuf-equivalent) to the input.
- **Every mutation gets a golden-file test**: real fixture in, one mutation, assert
  against an expected output that's been opened once in real Numbers and confirmed
  visually correct, then locked in as a permanent regression check. Mutations to cover:
  write value, write formula, set style, insert row, delete row, merge cells, relocate a
  cell range, place/resize a graphical object, edit rich text.
- Styles are always deep-copied, never shared by reference between cells (see bug #2
  above) — enforced structurally by making `Style` a frozen dataclass (`pybers.model`).
- Merged cells are first-class model state, not an edge case.
- Row/column insert-delete will be done via a real formula AST walker, not regex, so it
  actually knows which end of a range is supposed to move (see bug #3 above).

## The object model is split by feature area, not by class

`src/pybers/model/` is a real subpackage, not one flat file — the model is expected to
keep growing (it already covers cells/tables/sheets, style, geometry, rich text, and
floating shapes) and a single file would get unwieldy fast. Split is by **cohesive
feature area**, matching this developer's own instinct elsewhere (the `_lib`/`_config`/
`_presenter` script split; `another project`'s `ui/` split by responsibility,
not by class) rather than strict one-class-per-file, which is more a Java/C#/Swift
convention than a Python one.

Current modules: `style.py` (`Style`), `geometry.py` (`Position`, `Size`), `text.py`
(`TextRun`, `Paragraph`, `RichText`), `shapes.py` (`GraphicalObject`, `TextBox`, `Image`,
`Shape`), `table.py` (`Cell`, `MergeRange`, `Table`), `sheet.py` (`Sheet`, `Workbook`).
Everything re-exports through `pybers/model/__init__.py` and then `pybers/__init__.py`,
so `import pybers; pybers.Cell` stays stable regardless of internal file layout — keep
that re-export chain intact when adding a new feature-area module.

## Two consumers — design for both

pybers has two intended consumers, and both need to work from day one of real
functionality, not be retrofitted later:

1. **A library**, imported by another app (`import pybers`).
2. **A CLI/TUI**, pybers used directly as a tool (e.g. inspecting or editing a `.numbers`
   file's structure from the terminal).

This means the existing house rule **"separate logic from presentation"** is not
optional here — it is the entire reason the two consumers can share one core. `pybers.
model` and the future `pybers.archive` must never import anything CLI/TUI-related or
print anything; a `pybers.cli` (argparse, following `scripts/README.md`'s conventions)
and/or a `pybers.tui` (Textual — see `another project` for a
reference pattern: `App` subclass with dependencies injected via `__init__` rather than
imported, to dodge circular imports; `panels.py`/`dialogs.py`/`formatters.py` split by
responsibility) sit on top as thin, separately-packaged front ends. Neither exists yet —
build the library core first, but do not let it grow an implicit dependency on either
front end while doing so.

## Open architectural decisions (not yet made)

1. **Protobuf schema reuse.** Whether to vendor/reuse the already-reverse-engineered
   low-level iWork archive protobuf schemas from `reference/numbers-parser/` (the
   `.proto`-derived classes for `TSTArchives`/`TSWPArchives`/etc.) as the substrate,
   versus rebuilding archive parsing from zero. Recommendation: reuse the schemas (years
   of real reverse-engineering work, unrelated to the four bugs above), but write an
   entirely new, tested Python API layer on top — none of those bugs lived in the
   protobuf schema itself, they lived in the higher-level read/write/style/formula logic.
   Confirm before starting `pybers.archive`.
2. **Named styles.** Bold/italic alone are insufficient — Numbers supports real named,
   reusable styles (a "Heading 1"-type named style referenced by many cells/runs, so
   editing the named style updates every place that uses it), not just inline formatting.
   The likely shape: a `NamedStyle` (a `Style` plus a `name`/id) held in a registry at the
   `Workbook` level; `Cell`/`TextRun`/`Paragraph` would then optionally hold a
   `styleRef: str | None` (the named style) plus an optional local override layered on
   top — mirroring how Numbers itself layers a named style under direct formatting. Not
   yet built — the user is preparing real examples from actual `.numbers` files to
   inspect before this gets encoded into dataclass shapes, since that shape is costly to
   redo carelessly. Also open: what text-run properties beyond bold/italic actually need
   modeling (underline, strikethrough, super/subscript, letter spacing, highlight color,
   etc.) — again, pending real examples rather than guessing the property list.

## House style

Derived from a survey of `alchemy`, `another repository`, `another repository` (flat
single-file `scripts/` tooling) and `another repository` and `REDACTED-App-Tooling/Lighting-Protocol-
Monitor` (real multi-module apps), all in `the projects directory`. Where these
disagreed, `another repository` was treated as the stronger signal — it is the most mature, most
consistent, most test-covered of the five, and the sole point of disagreement
(another project's snake_case) tracked to the Textual framework's own naming
requirements rather than a real alternate convention.

- **camelCase** for functions, variables, and parameters — confirmed as her deliberate,
  unprompted default across every repo surveyed that wasn't constrained by a framework's
  own API contract. Module/file names stay lowercase (Python import rules), classes stay
  PascalCase — both confirmed consistent everywhere.
- **Dataclasses, not `TypedDict`**, for structured data — the user's explicit call for
  this project; `TypedDict` showed up elsewhere but for reasons specific to those repos'
  own dependencies, not a rule to import here. Frozen where immutability is load-bearing
  (see `Style` above), plain where it isn't.
- Full type hints everywhere, modern syntax (`list[str]`, `X | None`, `from __future__
  import annotations`), never `typing.List`/`typing.Optional`.
- Docstring on every function/class: one-line imperative summary, then free-form *why*
  when there is one — no `Args:`/`Returns:` sections. Module docstrings carry a dated
  `UPDATES` changelog block. No contractions in docstrings/comments.
- Module header block on every file: `#!/usr/bin/env python3`, `# -*- coding: utf-8 -*-`,
  module docstring, then `__author__`/`__copyright__`/`__license__`/`__version__`/
  `__email__`/`__status__`/`__date__` (`Richard P Ulivella` / `rpulivella@icloud.com` /
  `Copyright 2026` — personal-project identity, not the client-work `REDACTED`/`rich@
  REDACTED` identity seen in another project).
- `RuntimeError` subclasses for internal failures, always `raise ... from exc` to
  preserve the chain. No bare `except Exception: pass` swallows.
- `pathlib.Path` exclusively, never `os.path`. f-strings exclusively, never `.format()`.
- "Never shell out when a Python library can do the work."

## Deliberate deviations from house style, and why

- **Real package structure (`src/pybers/`), not a flat `scripts/` directory.** None of
  the five surveyed repos are things meant to be `pip install`ed by someone else — they're
  apps or repo tooling. A publishable library needs an actual importable package;
  `another project`'s `ui/` subpackage (real `__init__.py`, real relative
  imports) is the closer precedent than the flat-`scripts/` repos.
- **pytest, not hand-rolled `test-*.py` scripts.** The scripts-only repos run
  monkeypatched test scripts as subprocesses; `another repository` already uses real pytest
  (`unittest.TestCase` classes, `test_*.py`, no `conftest.py`, no config file, mocking via
  `unittest.mock`). This project uses plain pytest functions + fixtures instead of
  `TestCase` classes — a better fit for round-trip/golden-file testing, which is the
  explicit point of this rewrite, and doesn't contradict anything observed (another repository's
  choice of `TestCase` looks incidental, not a deliberate convention).
- **`pyproject.toml`, not `requirements.txt`.** Neither `another repository` nor
  `another project` uses one — but neither is a package with build metadata to
  publish. A PyPI-published library needs `pyproject.toml`; there's no way around it.
  `another repository`'s `requirements.txt` style (exact pins, grouped section comments explaining
  each dependency) is the model for how the `dependencies` list here should read once
  real dependencies exist.

## Status

Early scaffold only. `pybers.model` (the dataclass object model, split by feature area)
exists and is tested — `pytest` is green (`python3 -m venv .venv && source .venv/bin/
activate && pip install -e ".[dev]" && pytest`, confirmed working with the system Python
framework interpreter, not a pyenv/conda shim). `pybers.archive` (real `.numbers` file
read/write) does not exist yet — that's the next real piece of work, gated on the
protobuf-schema-reuse decision above. `pybers.cli`/`pybers.tui` do not exist yet either —
see "Two consumers" above.

License: undecided, not yet set in `pyproject.toml`.

This IS now its own real repo (`git init -b develop`, under `~/code/
git-local/`, same as every other repo of this developer's) — no longer living inside the
a renovation-budget project folder. `.venv`/`__pycache__`/`.pytest_cache` are
already covered by pre-existing global sync-ignore bare-name rules; no setup needed
there. `dist`/`build`/`*.egg-info` are NOT yet ignored (none exist yet) — add a
path-scoped sync-ignore rule the moment `python -m build` (or similar) is first run,
per the standing global-CLAUDE.md rule about action-triggered ignore setup.

### GitHub setup — do this when ready to make the ticket workflow real

The full ticket/PR skill set (`/ticket-create`, `/ticket-startwork`, `/ticket-edit`,
`/release-tag`, `/pr-draft`, `/pr-review-code`, `scripts/ticket.py`) is already ported
from `another repository` and adapted for `pybers`, but is **inert** until a real GitHub repo
and Project board exist. The user will stand this up herself when told it is time; when
that moment comes, tell her to:

1. Create the GitHub repo `rpulivella/pybers` (private is fine to start).
2. `git remote add origin git@github.com:rpulivella/pybers.git`, push `develop`.
3. Create a user-owned GitHub Project (v2) board for it, with a `Status` single-select
   field carrying exactly these options in order: `Concept`, `Todo`, `In Progress`,
   `Code Review`, `Done`. Note its **Project number** (visible in its URL).
4. Update `scripts/ticket.py`'s `projectNumber` constant from the placeholder `0` to that
   real number.
5. Generate a **classic** GitHub personal access token with both `repo` and `project`
   scopes (fine-grained tokens cannot reach user-owned Project boards at all). Same
   pattern as every other repo of hers, `another repository` included.
6. Put it in a git-ignored `.dev.vars` at the repo root as `GITHUB_TOKEN=<token>`
   (already covered by `.gitignore`) — this is preferred over the system keyring, which
   prompts for a password on every run since the keyring entry belongs to `gh`, not this
   tool. `scripts/ticket.py` resolves `GITHUB_TOKEN`/`GH_TOKEN` env vars first, then
   `.dev.vars`, then the keyring, in that order.
7. Also create `.github/labels` matching `validLabels` in `scripts/ticket.py` (`feat`
   `fix` `perf` `refactor` `style` `docs` `chore`) via `gh label create` or the repo
   settings UI — the tool assumes these already exist on the repo.
8. Sanity check: `python3 scripts/ticket.py list` should return "No tickets match."
   rather than erroring, once all of the above is in place.

Once this is done, `[init]`-prefixed commits give way to real `[<N>]`-ticket-numbered
ones per `CONTRIBUTING.md`, and the full skill set goes live with no further code
changes needed.

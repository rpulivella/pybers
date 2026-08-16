# pybers

A clean, round-trip-tested Python library for reading and writing Apple Numbers
documents. Built in deep respect for Apple Numbers itself — the goal is for editing a
`.numbers` file programmatically to be as reliable as using Numbers by hand.

## Why this exists

`pybers` stands on the shoulders of
[`numbers-parser`](https://github.com/masaccio/numbers-parser) by
[masaccio](https://github.com/masaccio) — an open-source project that reverse-engineered
Apple's entirely undocumented `.numbers` archive format (the protobuf schemas, the
compression, the formula AST) from nothing. That is a rare, substantial piece of software
archaeology, and it is the actual foundation everything here depends on. Real thanks are
owed for it existing and being open source at all; nothing below should read as a
complaint about that project.

The a renovation-budget project used a fork of `numbers-parser` extended with
formula-writing support, to edit real `.numbers` files directly. Pushing that young
feature branch further, on real files, surfaced some real correctness bugs — ordinary
friction from extending a young branch, not a reflection on the project as a whole
(vendored here at `reference/numbers-parser/`, with the rationale for each fix in
`reference/patches/`):

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

Plus a couple of known, unaddressed gaps hit along the way: fragile merged-cell handling
(a phantom merge-anchor could throw `ValueError: Value out of range` at save time), and no
way to relocate a block of cells as a unit. Two of the four bugs above were actually
diagnosed, fixed, and committed back into that fork (see `reference/numbers-parser/`'s own
git history before it was vendored, and `reference/patches/` for the rest) — the intent
was always to leave things better, not just extract value.

`pybers` exists for reasons independent of any of that: this developer wanted dataclasses
instead of the existing object model, a library-and-CLI/TUI split, and first-class named
styles from the start — things worth a clean design rather than retrofitting onto
someone else's architecture. **New project, not a fork — decided.** A GitHub-style fork
carries git lineage and implies staying API-compatible with upstream; neither fits an
approach this different (dataclasses, camelCase, a dual-consumer library/CLI split, named
styles). `reference/numbers-parser/` is vendored source to study, copied in with its
`.git` history stripped (like `another project`'s `reference/ola/`), not a
dependency this project extends — and some of the fixes documented above may be worth
proposing back upstream at some point, separate from this project's own direction.

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

1. ~~**Protobuf schema reuse.**~~ **DECIDED 2026-08-13: extract our own from Numbers.app.**
   The question was framed as reuse-the-vendored-schemas versus rebuild-from-zero, and both
   framings were wrong, because `reference/numbers-parser/`'s `.proto` files are not authored
   work to reuse or re-derive. Its `Makefile` extracts them from `/Applications/Numbers.app`
   — `protodump.py` dumps the protobuf descriptors Apple compiles into the binary,
   `rename_proto_files.py` normalizes them, `protoc --python_out` generates the `_pb2.py`,
   and `src/protos/` is a git-tracked copy of that dump. Both layers are machine output over
   Apple's own binary. Extraction is not the hard part; discovering that the descriptors are
   embedded, and writing the dumper, was.

   So `pybers` runs **its own** extraction, from the same source of truth Apple ships. Three
   reasons beyond ownership: the schemas then match the Numbers version this project actually
   round-trips against, rather than whatever was installed when someone else last
   bootstrapped; the step is re-runnable when Apple ships a new Numbers, instead of waiting
   on an upstream refresh or hand-patching; and it keeps the lineage honest — the technique
   is learned from that `Makefile` (credit it in the bootstrap script's docstring) without
   copying its output. `reference/numbers-parser/src/protos/` becomes a **differential
   check**: a matching dump corroborates both, and a difference is a finding worth
   understanding rather than a silent divergence.

   Two practical constraints this imposes. Their bootstrap unsigns the app
   (`/tmp/Numbers.unsigned.app`, entitlements stripped) to read the binary, and the
   `mapping.json` step *executes* that unsigned copy — the proto dump is the benign half and
   the mapping extraction needs understanding before it is run. And because the bootstrap
   depends on a local `Numbers.app`, its **generated output must be committed** so that
   `pip install pybers` works on a machine without Numbers present.

   (Licensing was never the constraint: `reference/numbers-parser/` is MIT, Jon Connell 2021,
   so copying with attribution would have been permitted. The bar here is ownership of the
   foundation and respect for someone else's craft, which is higher than the license.)
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
there. `dist`/`build` are now path-scoped in `the sync ignore rules`, added before the
first build per the action-triggered rule; `*.egg-info` is covered globally.

**Hatchling, not setuptools — decided 2026-08-15.** `src/pybers/` holds 34 non-Python
files (33 `.proto` schemas plus their provenance README) that must ship in the wheel.
Hatchling includes everything under the package directory by default; setuptools omits
non-Python files unless `package-data` or a `MANIFEST.in` says otherwise, and fails
silently when it does — the wheel builds clean and arrives incomplete. Hatchling also
writes PEP 376 `.dist-info` into site-packages rather than scattering setuptools'
legacy `.egg-info` through the source tree. No C extensions here, so setuptools' real
strengths do not apply; its only advantage is familiarity.

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

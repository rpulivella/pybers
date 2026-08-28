# pybers

A clean, round-trip-tested Python library for reading and writing Apple Numbers
documents. Built in deep respect for Apple Numbers itself, the goal is for editing a
`.numbers` file programmatically to be as reliable as using Numbers by hand.

## Why this exists

`pybers` stands on the shoulders of
[`numbers-parser`](https://github.com/masaccio/numbers-parser) by
[masaccio](https://github.com/masaccio), an open-source project that reverse-engineered
Apple's entirely undocumented `.numbers` archive format (the protobuf schemas, the
compression, the formula AST) from nothing. That is a rare, substantial piece of software
archaeology, and it is the actual foundation everything here depends on. Real thanks are
owed for it existing and being open source at all; nothing below should read as a
complaint about that project.

A renovation-budget project used a fork of `numbers-parser` extended with
formula-writing support, to edit real `.numbers` files directly. Pushing that young
feature branch further, on real files, surfaced some real correctness bugs, ordinary
friction from extending a young branch, not a reflection on the project as a whole
(that fork is a separate checkout kept outside this repository, see the note below):

1. `Table.write()` silently dropped a cell's `Style` (alignment, fill, font) unless a
   `preserve_format=True` flag was passed, and even then only worked after a deeper fix.
2. `set_cell_style()` assigned a `Style` object by raw Python reference, so two cells
   could share the identical mutable object, mutating one cell's style at save time
   silently corrupted an unrelated cell's formatting.
3. The row-insert helper's reference-shift regex moved *both* ends of a range token
   (`C3:C25` → `C4:C26`) when only the end nearer the insertion point should move,
   silently dropping rows from the start of `SUMIFS`-style ranges.
4. A number-format decoder crashed (`TypeError`) on certain `None`-valued fields instead
   of defaulting them.

Plus a couple of known, unaddressed gaps hit along the way: fragile merged-cell handling
(a phantom merge-anchor could throw `ValueError: Value out of range` at save time), and no
way to relocate a block of cells as a unit. Two of the four bugs above were actually
diagnosed, fixed, and committed back into that fork (see its own git history, and the
patch set kept with it). The intent was always to leave things better, not just extract
value.

`pybers` exists for reasons independent of any of that: this developer wanted dataclasses
instead of the existing object model, a library-and-CLI/TUI split, and first-class named
styles from the start, things worth a clean design rather than retrofitting onto
someone else's architecture. **New project, not a fork, decided.** A GitHub-style fork
carries git lineage and implies staying API-compatible with upstream; neither fits an
approach this different (dataclasses, camelCase, a dual-consumer library/CLI split, named
styles). numbers-parser is **not vendored here** (see the note below), and it is not a
dependency this project extends. Some of the fixes documented above may be worth proposing
back upstream at some point, separate from this project's own direction.

**Python, not Rust, decided.** The reverse-engineered iWork archive protobuf schemas
already exist in Python; rebuilding that reverse-engineering in Rust would re-derive the
hard part for no functional gain. The actual use case (Python scripts driving real
`.numbers` edits end-to-end) and the stated goal (`pip install pybers`) are both
Python-ecosystem targets, and `.numbers` files are small enough that this is not a
performance-bound workload. If a Rust core is ever wanted, PyO3 bindings are the path,
not a rewrite.

### numbers-parser is NOT vendored here: removed 2026-08-27

It was, under `reference/`: 353 files, 31 MB, committed. That was a mistake and the whole
path has been **purged from git history**, not merely untracked, because this repository is
going open source and a rewrite is cheap now and impossible later.

**What it was actually used for was one lookup table.** Every decode in this project needs
`typeId` -> archive class name, and that came from numbers-parser's generated `mapping.py`.
That table is now extracted to **`workarea/archive-type-map.json`** (581 entries), which is
git-ignored, read only by the `workarea/` audit tools, and never imported by anything under
`src/`. Nothing else in the checkout was in use.

If that table is ever lost, regenerate it from
[`numbers-parser`](https://github.com/masaccio/numbers-parser), which is where it
originated and which remains the place to look when studying how upstream solved
something.

**Do not re-vendor it.** If a future need seems to call for it, extract the specific data
into `workarea/` as data, the way the type map was.

## Core design contract

- Read an archive → typed object model (`pybers.model`) → write it back.
- **Base test**: read a real fixture file and write it back with zero changes → output is
  byte-identical (or protobuf-equivalent) to the input.
- **Every mutation gets a golden-file test**: real fixture in, one mutation, assert
  against an expected output that has been opened once in real Numbers and confirmed
  visually correct, then locked in as a permanent regression check. Mutations to cover:
  write value, write formula, set style, insert row, delete row, merge cells, relocate a
  cell range, place/resize a graphical object, edit rich text.
- Styles are always deep-copied, never shared by reference between cells (see bug #2
  above), enforced structurally by making `Style` a frozen dataclass (`pybers.model`).
- Merged cells are first-class model state, not an edge case.
- Row/column insert-delete will be done via a real formula AST walker, not regex, so it
  actually knows which end of a range is supposed to move (see bug #3 above).

## The object model is split by feature area, not by class

`src/pybers/model/` is a real subpackage, not one flat file, the model is expected to
keep growing (it already covers cells/tables/sheets, style, geometry, rich text, and
floating shapes) and a single file would get unwieldy fast. Split is by **cohesive
feature area** rather than strict one-class-per-file, which is more a Java, C# and Swift
convention than a Python one.

Current modules: `style.py` (`Style`), `geometry.py` (`Position`, `Size`), `text.py`
(`TextRun`, `Paragraph`, `RichText`), `shapes.py` (`GraphicalObject`, `TextBox`, `Image`,
`Shape`), `table.py` (`Cell`, `MergeRange`, `Table`), `sheet.py` (`Sheet`, `Workbook`).
Everything re-exports through `pybers/model/__init__.py` and then `pybers/__init__.py`,
so `import pybers; pybers.Cell` stays stable regardless of internal file layout, keep
that re-export chain intact when adding a new feature-area module.

## Two consumers: design for both

pybers has two intended consumers, and both need to work from day one of real
functionality, not be retrofitted later:

1. **A library**, imported by another app (`import pybers`).
2. **A CLI/TUI**, pybers used directly as a tool (e.g. inspecting or editing a `.numbers`
   file's structure from the terminal).

This means the existing house rule **"separate logic from presentation"** is not
optional here. It is the entire reason the two consumers can share one core. `pybers.
model` and the future `pybers.archive` must never import anything CLI/TUI-related or
print anything; a `pybers.cli` (argparse, following `scripts/README.md`'s conventions)
and/or a `pybers.tui` (Textual, with dependencies injected into the `App` subclass rather
than imported, to dodge circular imports) sit on top as thin, separately-packaged front
ends. Neither exists yet,
build the library core first, but do not let it grow an implicit dependency on either
front end while doing so.

## Open architectural decisions (not yet made)

1. ~~**Protobuf schema reuse.**~~ **DECIDED 2026-08-13: extract our own from Numbers.app.**
   The question was framed as reuse-the-vendored-schemas versus rebuild-from-zero, and both
   framings were wrong, because numbers-parser's `.proto` files are not authored
   work to reuse or re-derive. Its `Makefile` extracts them from `/Applications/Numbers.app`
, `protodump.py` dumps the protobuf descriptors Apple compiles into the binary,
   `rename_proto_files.py` normalizes them, `protoc --python_out` generates the `_pb2.py`,
   and `src/protos/` is a git-tracked copy of that dump. Both layers are machine output over
   Apple's own binary. Extraction is not the hard part; discovering that the descriptors are
   embedded, and writing the dumper, was.

   So `pybers` runs **its own** extraction, from the same source of truth Apple ships. Three
   reasons beyond ownership: the schemas then match the Numbers version this project actually
   round-trips against, rather than whatever was installed when someone else last
   bootstrapped; the step is re-runnable when Apple ships a new Numbers, instead of waiting
   on an upstream refresh or hand-patching; and it keeps the lineage honest, the technique
   is learned from that `Makefile` (credit it in the bootstrap script's docstring) without
   copying its output. numbers-parser's `src/protos/` becomes a **differential
   check**: a matching dump corroborates both, and a difference is a finding worth
   understanding rather than a silent divergence.

   Two practical constraints this imposes. Their bootstrap unsigns the app
   (`/tmp/Numbers.unsigned.app`, entitlements stripped) to read the binary, and the
   `mapping.json` step *executes* that unsigned copy, the proto dump is the benign half and
   the mapping extraction needs understanding before it is run. And because the bootstrap
   depends on a local `Numbers.app`, its **generated output must be committed** so that
   `pip install pybers` works on a machine without Numbers present.

   (Licensing was never the constraint: numbers-parser is MIT, Jon Connell 2021,
   so copying with attribution would have been permitted. The bar here is ownership of the
   foundation and respect for someone else's craft, which is higher than the license.)
2. ~~**Named styles.**~~ **DECIDED 2026-08-24 by measurement, not by design.** The shape
   proposed here, a named style plus an optional local override layered on top, is
   exactly what Numbers does, confirmed against `tests/fixtures/32-named-styles.numbers`.
   Applying a named style writes a **reference** to the shared style; formatting on top of
   it writes an anonymous **variation** carrying `parent`, `is_variation` and
   `override_count`, storing only the properties that changed. Reading a cell's effective
   formatting is a walk up that chain.

   Three things the fixtures corrected, none of which was guessable:

   - **Only some style kinds can be named.** Paragraph, character and list styles carry
     names; **cell, table and sheet styles never do**, zero named out of 309 cell styles
     measured. A `NamedStyle` registry maps onto something real for text, and would be a
     pybers invention for cells. If it is offered there anyway, it must be labelled as a
     pybers concept, because a round trip cannot persist it. (Confirmed from the UI side
     by `42`: Numbers offers no cell-style concept at all, cell appearance comes only
     from literal inspector values or copy-paste.)
   - **For PARAGRAPH and LIST styles, a `name` does NOT make a style user-visible**,
     added 2026-08-26 from `42`, corrected the same day by the expanded `32`. A paragraph
     or list style appears in the styles browser only if it is registered in
     `TSS.StylesheetArchive.identifier_to_style_map`; `Object Caption` and `Object Title`
     are real, named, correctly-applied paragraph styles with no map entry and the user can
     never see or select them. So creating a usable named paragraph style is **two writes**:
     the archive with its `name`, and the stylesheet registration. Doing only the first
     fails silently in the worst way, it round-trips perfectly and is invisible forever.
     **Character styles do not follow this rule**: every named character style in the corpus,
     Numbers' own and the user's alike, is absent from the map and visible regardless. Only
     the two special ones (`Link`, `None`) are keyed. Do not generalize across style kinds.
   - **There is no unparented text style.** A cell formatted entirely by hand is still a
     *variation* of a named style. So `styleRef: str | None` should read `None` as "not
     yet resolved", never as "has no style".
   - **`override_count` counts logical properties, not fields**, a color change stores
     both `font_color` and `tsd_fill` and counts as one. Preserve it rather than
     recomputing it.

   The property-list question is likewise settled by fixtures rather than guesswork: see
   `tests/fixtures/findings-04-text.md` for what a text run actually carries, including
   the rule that Apple's synthetic superscript and small-caps must never be written when
   a real OpenType feature exists.

## House style

The conventions below are deliberate and several of them differ from what a Python
linter will assume. Follow them as written.

- **camelCase** for functions, variables, and parameters. This is deliberate and it is
  the opposite of what most Python tooling assumes, so a linter has to be configured for
  it rather than against it. Module and file names stay lowercase (Python import rules),
  and classes stay PascalCase.
- **Dataclasses, not `TypedDict`**, for structured data, the user's explicit call for
  this project; `TypedDict` showed up elsewhere but for reasons specific to those repos'
  own dependencies, not a rule to import here. Frozen where immutability is what keeps a
  defect out (see `Style` above), plain where it is not.
- Full type hints everywhere, modern syntax (`list[str]`, `X | None`, `from __future__
  import annotations`), never `typing.List`/`typing.Optional`.
- Docstring on every function/class: one-line imperative summary, then free-form *why*
  when there is one, no `Args:`/`Returns:` sections. Module docstrings carry a dated
  `UPDATES` changelog block. No contractions in docstrings/comments.
- Module header block on every file: `#!/usr/bin/env python3`, `# -*- coding: utf-8 -*-`,
  module docstring, then `__author__`/`__copyright__`/`__license__`/`__version__`/
  `__email__`/`__status__`/`__date__` (`Richard P Ulivella` / `rpulivella@icloud.com` /
  `Copyright 2026`).
- `RuntimeError` subclasses for internal failures, always `raise ... from exc` to
  preserve the chain. No bare `except Exception: pass` swallows.
- `pathlib.Path` exclusively, never `os.path`. f-strings exclusively, never `.format()`.
- "Never shell out when a Python library can do the work."

## Deliberate deviations from house style, and why

- **Real package structure (`src/pybers/`), not a flat `scripts/` directory.** None of
  the surveyed projects are meant to be `pip install`ed by someone else. They are
  apps or repo tooling. A publishable library needs an actual importable package;
  A real importable subpackage is the closer precedent than a flat `scripts/` directory.
- **pytest, not hand-rolled test scripts.** Plain pytest functions and fixtures rather
  than `TestCase` classes, which is a better fit for the round-trip and golden-file
  testing that is the explicit point of this project.
- **`pyproject.toml`, not `requirements.txt`.** A repository that is an application, not
  a package, has no build metadata to publish. A library published to PyPI needs
  `pyproject.toml`. Dependencies should be exact pins with
  grouped section comments explaining each one.

## Status

`pybers.model` (the dataclass object model, split by feature area) and `pybers.archive`
(the `.numbers` container and cell reader) both exist and are tested. Run the suite as
**`.venv/bin/python3 -m pytest`**, that exact spelling, because `.claude/settings.json`
matches permission strings as text and a grant that never fires reads as coverage.

`pybers.archive` reads a `.numbers` file end to end: zip, IWA frames, a pure-Python
Snappy decoder with no C dependency, length-prefixed protobuf archives, and cell values
including numbers, text, dates, booleans, durations and currency. It writes a package back
with one bounded, documented difference in the zip envelope, confirmed to open cleanly in
Numbers. `pybers.cli`/`pybers.tui` do not exist yet, see "Two consumers" above.

**The format is mapped; the model binding is not.** Roughly 36 real `.numbers` fixtures
live under `tests/fixtures/`, each labeling its own contents so a decode is verifiable
rather than plausible. What they established is in `tests/fixtures/FINDINGS.md`, split by
topic. **Read that before designing anything**, several findings invalidate the obvious
approach, and the format's characteristic failure is that a wrong offset yields wrong
numbers rather than an error.

The seven that change what the library must be: numbers are **decimal128** and never
`float`; formulas are a **postfix AST with relative references**, so there is no formula
text to parse and `$` is a per-axis boolean; **merges are stored as formulas** and a
structural edit that ignores the merge store is what caused the phantom-merge-anchor
defect listed above; **color carries a color space**; and a **named style plus variation**
is how all text formatting works.

The remaining two came from the fixtures for floating objects and Unicode:

**Text run indices count UTF-16 code units, not Python characters** (`36-unicode-text`). A
`StorageArchive` carries twenty-one parallel run tables, nineteen of them keyed by
`character_index`, covering character and paragraph styles, language, bidi, drop caps and
dictated-word provenance. Every one of those indices is an NSString offset. For BMP text the
two counts agree exactly, which is why the earlier rich-text fixtures validated perfectly and
proved nothing. One astral character shifts every later boundary by one, silently, producing
plausible runs with the wrong text in them. The conversion belongs at the boundary where a
run table is read or written; plain string cells need no special handling.

**Numbers shares style archives by reference between objects** (`34-shape`). Twenty-one
shapes resolve to twelve styles, one of which backs seven drawables directly and another
backs eight, two directly and six more as the `parent` their variations inherit from. So the
aliasing defect listed above is not an upstream implementation slip but a hazard the format
creates: a decoder that hands the same mutable object to every user of an archive lets one
edit silently restyle seven unrelated shapes. The frozen-`Style` contract has to hold on the
**read** path, not only when writing. Numbers itself never mutates a shared archive, it
writes a new variation and repoints the one object that changed.

License: undecided, not yet set in `pyproject.toml`.

This is its own repository, on `develop`, no longer nested inside another project.

**Hatchling, not setuptools, decided 2026-08-15.** `src/pybers/` holds 34 non-Python
files (33 `.proto` schemas plus their provenance README) that must ship in the wheel.
Hatchling includes everything under the package directory by default; setuptools omits
non-Python files unless `package-data` or a `MANIFEST.in` says otherwise, and fails
silently when it does, the wheel builds clean and arrives incomplete. Hatchling also
writes PEP 376 `.dist-info` into site-packages rather than scattering setuptools'
legacy `.egg-info` through the source tree. No C extensions here, so setuptools' real
strengths do not apply; its only advantage is familiarity.

# Decisions and their reasoning

The long form of settled calls. `CLAUDE.md` states each decision in a line or two
and points here; this file keeps the reasoning so a settled call is not
re-litigated from scratch. Nothing here is a rule. The rules are in `CLAUDE.md`.

Moved out of `CLAUDE.md` on 2026-09-04, which had grown to 357 lines with two
history sections making up 40% of it.

---

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

---

## Document is the single handle, decided 2026-08-31

`pybers.open(path)` returns a `Document`, and that one object is the whole public surface.
It holds the entire document in memory, it is what `document.save()` writes back, and
every edit a developer makes is a method on it or on something reached through it. There
is no session, no workbook, and no second noun to learn.

The alternative considered was a separate object owning the package while `Document`
stayed pure data. It buys layering purity at the price of handing the caller two things
that are always used together, which is the wrong trade for a library meant to make
editing a `.numbers` file as ordinary as opening one.

Two consequences that are easy to get wrong:

- **`Document` carries archive state, not only model state.** Saving mutates the archives
  that were read rather than constructing new ones, so that whatever the model does not
  yet represent survives untouched. That state is private, and excluded from equality and
  `repr`, so `Document` still reads as a dataclass to a caller.
- **A feature's model types never import its archive halves at module scope.**
  Whatever mechanism `Document.save()` uses to reach the writer, a function-local import
  is the only form allowed, and `sheet.py` guards its one type reference behind
  `TYPE_CHECKING`. Stated as a rule about the model's own modules because that is what is
  enforceable: importing a feature runs `pybers/__init__.py` first, which imports
  `pybers.reader`, so the persistence layer arrives regardless. The earlier wording said
  the model stays importable without it, which was never true through the ordinary path.

---

## A created sheet or table starts from the pybers reset, decided 2026-09-14

A spreadsheet built by a program serves a different purpose from one built in the
interface, so pybers does not start from Numbers' own new sheet or table. It starts from a
reset, in the sense of a CSS reset: every value stated, nothing inherited from a theme by
accident. The measurements behind it are in `docs/findings/findings-10-creation.md`.

A created **sheet** prints 1:1, with autofit off and a content scale of 1.0, because
printing at true size is Numbers' strongest use. Its margins are 1 in at top and bottom and
0.75 in at left and right, and its headers and footers are empty, with no page number. Its
background is the theme's sheet style, which fills white: a sheet without a fill was the
intent, and Numbers cannot make one, so pybers does not write one either.

A created **table** has no gridlines and no border, no header rows, columns or footer, and
no title or caption. Its text is Avenir Next Regular at 11 pt on exactly 15.5 pt, a face
every Mac and iPad carries, with wrapping off so written output never reflows a row. Cells
keep Numbers' 4 pt padding, rows are 24 pt, one exact line plus the padding with half a
point to spare, and columns are 72 pt, exactly 1 in, so a table's printed width is simple
arithmetic.

The text style is a named paragraph style, `pybers-base`, created once per document and
found again by name, so a Numbers user restyles every pybers table by editing one style.
The name leads with `pybers` so later styles sort beside it, and carries no leading `.` or
`_`, since Numbers hides neither.

---

## Dependabot advises and opens no pull request, decided 2026-10-05

Dependabot alerts report an advisory against a dependency `pyproject.toml` declares, or
against an action a workflow uses, and each alert reaches a maintainer by email.
Dependabot opens no pull request of either kind, a version update or a security update.

A version update has almost nothing to raise. `pyproject.toml` declares floors and the
repository holds no lockfile, so a new release already satisfies every requirement
without an edit. A security update arrives as a pull request with no ticket, no template
body and no CHANGELOG entry, which every other change carries and the `readiness` check
expects. Teaching the checks an exception for one bot costs more than a maintainer filing
a ticket from the alert, and keeps every change under a ticket.

The per-pull-request scan PYB-76 landed already reports an advisory against the resolved
environment in the `readiness` comment, so alerts cover the time between pull requests.
An action that falls behind with no advisory against it goes unreported, which costs
nothing while it carries no vulnerability.

No rule auto-dismisses an alert, because the dev dependencies run in CI with the
repository's token and an alert nobody reads defeats advising. Automatic dependency
submission stays off: it spends Actions minutes to find the indirect dependencies, which
the per-pull-request scan already resolves.

---

## Deliberately not here

**The protobuf-extraction and named-styles rationale was deleted, not moved**, on
2026-09-04. Every fact in it already lived somewhere better: the named-style rules in
`docs/findings/findings-06-styles.md`, and the schema provenance in
`src/pybers/protos/README.md`. A third copy would have gone stale against both.

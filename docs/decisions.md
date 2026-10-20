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
That table was extracted into a local file (581 entries) that is git-ignored, read only by
local audit tools, and never imported by anything under `src/`. Nothing else in the
checkout was in use.

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
without an edit. Security updates are off because each would arrive as a pull request
with no ticket, no template body and no CHANGELOG entry, which every other change
carries and the `readiness` check expects.

The per-pull-request scan PYB-76 landed already reports an advisory against the resolved
environment in the `readiness` comment, so alerts cover the time between pull requests.
An action that falls behind with no advisory against it goes unreported, which costs
nothing while it carries no vulnerability.

No rule auto-dismisses an alert, because the dev dependencies run in CI with the
repository's token and an alert nobody reads defeats advising. Automatic dependency
submission stays off: it spends Actions minutes to find the indirect dependencies, which
the per-pull-request scan already resolves.

---

## Writing values and formats, decided 2026-10-16

Settled for PYB-217, PYB-144 and PYB-145 across three users at once: a person at the
command line, a script through `import pybers`, and an agent holding several documents
open. Whatever serves one of them has to read the same way to the other two.

**A value's kind follows its Python type.** `Decimal` is a number, `str` text, `bool` a
boolean, `datetime` a date and time, and `timedelta` a duration. An `int` is accepted as the
exact number it names, and a `date` as midnight, which is how Numbers stores a date typed
without a time. A `float` is refused with a message naming `Decimal`, because Numbers keeps
numbers as decimal128 and a binary float carries rounding error into a document that never
had any.

**A date and time always carries a time zone.** One with none is refused, so a written
moment is never ambiguous. Whether Numbers stores a date in UTC or in some local time, and
whether it keeps a date with no time zone at all, is not measured yet; PYB-218 measures
both, and if Numbers does keep such a date, pybers represents it rather than refusing it.

**A cell that changes kind takes Numbers' Automatic format for its new kind**, as a value
typed into a fresh cell does. A boolean therefore shows TRUE or FALSE; a checkbox is a
format, chosen through formats like any other.

**A format is a value of one union, `CellFormat`**, with one frozen dataclass per family:
`CellFormatNumber`, `CellFormatNumberCustom`, `CellFormatDuration`, `CellFormatCurrency`
and the rest. `CellFormatAutomatic` and `CellFormatUnknown` are members too, so a format
nobody chose and a format pybers cannot decode are explicit values rather than `None`, and
a `match` over a cell's format is exhaustive. The names lead with `CellFormat` so the family
sorts together and never collides with text or table formatting, and `CellFormatFamily`
names the families. A small `Protocol` carries what every format shares.
Typed objects were chosen over the alternatives other libraries take, a format string as in
openpyxl or keyword options as in numbers-parser, because Numbers has no format syntax to
borrow and a misspelled keyword fails late or not at all.

**A format belongs to no document.** One read from a cell in one document applies to a
cell in another, and the writer finds or adds the matching entry in that table's format
list. Every format has one text form tagged by its family, which the command line, JSON
export and import, and an agent all use.

**A cell's kind and format always agree.** A write that would leave a format on a value it
cannot show, such as a duration format on text, is refused, naming both, unless the caller
passes `CellFormatConflict.AUTOMATIC`, which falls back to the Automatic format and reports
it. The policy is a parameter of the library and of an agent's calls, and other writes can
take it later, an import or a fill among them.

**A write reports each cell whose kind or format it changed**, before and after, and a
preview reports the same without writing. Nothing about a column is special: a write
touches the cells it names, and whether a column stays consistent is answered by reading
the table's structure, which reports each column's kind and format and the cells that
differ. That reading is also what keeps JSON export compact, since a column is described
once and only its exceptions are listed.

**Formats apply over a range**, `table.cellFormatApply(range, format)`, and a single cell's
value, format and style are set together in one call, `document.cellSet(address, ...)`,
the style a named one or one written into the cell alone. The call sits on the document
because its address names the sheet and table, and it returns the change it made.

**A custom number format is a structured value** holding its positive, negative and zero
forms, the shape Numbers stores. A shorthand parser may later build one, and the structured
value stays what pybers stores.

**Currency has one home** that the format code and the formula code share, since a
formula's result can be a currency amount as well as a cell's value (PYB-220).

**No format bit is written before it is decoded.** PYB-219 decodes each family's archive
and flag bits, and the format work splits by family on its findings.

**On the command line, the verb comes first**: `pybers set FILE ADDRESS VALUE`. A file
first would leave `diff A B`, `import` and `export -o` without a consistent place, and the
bare `pybers FILE` already covers looking at one document. `set` infers a value's kind and
`--as` overrides the inference; should inference prove unreliable, `set` falls back to text
unless `--as` names a kind. The inference is one table of parsers built on the standard
library, tried in order, rather than a chain of conditions. `set --format` sets a format by
its text form. `--preview` shows a change and writes nothing, the flag named for what it
does.

---

## A cell's position, how it is pointed at, and how far apart two are, decided 2026-10-19

Three types, each one idea. **`CellAddress`** is where a cell sits in any table: a row and a
column counted from one, bounded by the largest table Numbers holds, with no table and no
`$`. **`CellReference`** is how something points at a cell: an address, a lock on each axis,
and the table it names when its context needs one. **`CellOffset`** is a signed distance in
rows and columns.

**A lock belongs to the reference, never to the address.** `B3`, `$B3`, `B$3` and `$B$3` all
point at one address and differ only in how they move when a formula is copied, so every
formula reference carries both locks, each on or off. Keeping the lock out of the address
is also what lets a table key its cells by address with no normalizing step: two spellings
of one position are always one key.

**A reference is qualified only as far as its context needs**, the model of a path or a
URL. `B3`, `Q3::B3` and `Budget::Q3::B3` are one type, its table and that table's sheet
given by `TableReference` and `SheetReference`, typed rather than bare strings. Each owner
takes its part and hands the rest down: `document.cell` refuses a reference naming no table,
`sheet.cell` refuses one naming another sheet, and `table.cell` takes `B3` alone or a
qualifier naming that table. A qualified and an unqualified reference compare unequal, as
two paths do. Merging position and qualification into one type was weighed and kept apart
from the address, because a qualified key would have to be stripped before every lookup.

**An offset is its own type**, because an address is counted from one and bounded, and an
offset is signed and may be zero. An address plus an offset is an address, an address
minus an address is an offset, and two offsets add, which is the `datetime` and
`timedelta` algebra. A formula stores a relative axis as exactly this signed distance and a
locked axis as a position, so the three types meet what Numbers keeps.

**Iterating a table yields addresses**, portable to any table, which is what a template, a
move within one table or a conversion wants. Anything gathered across tables, a search, a
change report or a document-wide walk, yields qualified references, since a result that
leaves its loop has to say where it was.

**The input aliases are named for what they accept**, `CellReferenceLike` and
`CellRangeLike`, in the style of `os.PathLike`, so the word address names one type and the
text syntax, never an alias.

---

## A reference is a path, and a selector is CSS, decided 2026-10-20

Selecting cells borrows two models a developer already knows, one for naming a single
cell and one for matching many.

**A reference follows `pathlib.Path`.** It is qualified only as far as its context needs,
the way a path is relative or absolute, and each owner resolves its part and hands the rest
down, the way a path walks directories. `cell.address` and `cell.reference` are a path's
name and its resolved form, and an offset between two addresses is a relative path.

**A selector follows CSS.** It matches a set of cells by pattern and returns their
references. The `::` chain is the descendant combinator, `Budget::*, Notes::Table 1` is
grouping, and `Q*::*` is a partial match on names. CSS also offers what an agent asking for
cells by meaning rather than by position needs: a condition on a cell's kind or format,
in the manner of an attribute selector (`[kind=duration]`), a state, in the manner of a
pseudo-class (`:empty`, `:formula`, `:header`), a position by pattern, in the manner of
`:nth-child` (every second row, every third column), and negation, in the manner of
`:not()`. One string can then ask for every duration in every quarterly table that is not
a header, and the table-structure read and JSON export answer to the same selectors.

pybers borrows from CSS elsewhere too: a created table starts from a reset in the sense of
a CSS reset, and an item on a sheet is placed by the anchor names of `background-position`.
The selector type is built in PYB-223.

---

## Deliberately not here

**The protobuf-extraction and named-styles rationale was deleted, not moved**, on
2026-09-04. Every fact in it already lived somewhere better: the named-style rules in
`docs/findings/findings-06-styles.md`, and the schema provenance in
`src/pybers/protos/README.md`. A third copy would have gone stale against both.

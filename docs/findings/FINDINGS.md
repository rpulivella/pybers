# What the fixtures have established

Findings derived from the `.numbers` files in `tests/fixtures/` and `tests/measurements/`, each one reproducible by
reading those files with `pybers._persistence`. Recorded so they are not re-derived, and so a
later contradiction is recognizable as a contradiction rather than a surprise.

Split by topic, this file is the index.

| | |
|---|---|
| [findings-01-values.md](findings-01-values.md) | Cell records, the value encodings, and how formats attach without changing a value. **The part the protobuf schemas do not describe at all.** |
| [findings-02-formulas.md](findings-02-formulas.md) | The postfix AST, why references survive being moved, cross-table links, and what a failed formula stores. |
| [findings-03-structure.md](findings-03-structure.md) | Merges, what structural edits do to them, tiles, and how tables and sheets sit on a document. |
| [findings-04-text.md](findings-04-text.md) | Text storage, style runs, OpenType features, and the typography traps. |
| [findings-06-styles.md](findings-06-styles.md) | Fills, gradients, and why a color is not three floats. |
| [findings-07-drawables.md](findings-07-drawables.md) | Text boxes, shapes and images, everything floating on a sheet rather than inside a table. |
| [findings-08-formula-text.md](findings-08-formula-text.md) | The operator table, which functions bracket their arguments, and the three node kinds where text and nodes are not inverses. |
| [findings-09-cell-records.md](findings-09-cell-records.md) | Where a cell record keeps its formula key, which moves as the cell gains a fill, an alignment or conditional highlighting. |
| [findings-10-creation.md](findings-10-creation.md) | What a new sheet and a new table consist of, how a created archive is registered, and the reset as Numbers encodes it. |
| [findings-11-formats.md](findings-11-formats.md) | Every field of each format family's archive, the record bits a format sets, and which of them pybers writes. |
| [findings-12-language-and-region.md](findings-12-language-and-region.md) | What Numbers rewrites when a document's language and region change: the locale snapshot, formula text in the document's language, and the cached results that depend on it. |
| [findings-05-method.md](findings-05-method.md) | How these findings were produced, and the mistakes that produced them slowly. |

---

## The six that matter most

If nothing else here is read, these six change what the library has to be.

**Numbers are IEEE-754 decimal128, not float64.** `1234.5` is stored exactly. Routing a value
through a Python `float` would introduce binary rounding error into a document that never had
any, so `Cell.value` uses `Decimal`., [values](findings-01-values.md)

**Formulas are a postfix AST with relative references, never text.** The file holds no
formula text, and `$` is a per-axis boolean rather than punctuation. The regex-based range
shifting recorded as a defect in `docs/decisions.md` was treating structure as text. A move
rewrites references under one of two rules: Numbers' cut and paste rewrites nothing, and
dragging a block keeps every reference on the cell it named, which rewrites offsets.
[formulas](findings-02-formulas.md), [structure](findings-03-structure.md)

**Merges are stored as formulas**, in a formula store beside the cells, and **Numbers rewrites
them on structural edits**. Reading is safe; writing is not, a row insert that ignores the
merge store leaves a merge pointing at the wrong row, which is exactly the phantom merge
anchor in `CLAUDE.md`., [structure](findings-03-structure.md)

**A wrong offset produces wrong numbers, not an exception.** Every field is a fixed-width
integer or float, so misreading one still parses. This is why every layout claim needs a
fixture whose contents are known independently, and why the fixtures carry their own answer
key., [method](findings-05-method.md)

**Color carries a color space, and it varies within a single gradient.** Storing `(r, g, b, a)`
floats would silently shift colors, because 0.5 red in sRGB is not 0.5 red in Display P3.
, [styles](findings-06-styles.md)

**Real OpenType features sit right beside Apple's synthetic imitations.** `superscript` and
`capitalization = kSmallCaps` fake the effect on the existing glyph; the honest route is a
font feature. pybers must be able to tell them apart and must never write the fake form.
, [text](findings-04-text.md)

---

## What is still unknown

- **Where a whitespace node attaches.** Node types 32 and 33 carry the spaces a person typed,
  and postfix order and text order disagree for an operator, so the position each one
  belongs to is not established. See [formula text](findings-08-formula-text.md).
- **Cell types 1 and 4**, which `TST.CellType` names and no document carries.

---

Type identifiers throughout are ours, read from `ArchiveInfo.message_infos`. The
human-readable class names in these findings were first read from numbers-parser's
`mapping.py`, for interpretation only. `pybers._persistence.types` carries the curated subset
the read and write paths reach, each mapped to a class generated from the schemas pybers
extracted itself.

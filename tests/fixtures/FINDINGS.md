# What the fixtures have established

Findings derived from the `.numbers` files in this directory, each one reproducible by
reading those files with `pybers.archive`. Recorded so they are not re-derived, and so a
later contradiction is recognizable as a contradiction rather than a surprise.

Split by topic — this file is the index.

| | |
|---|---|
| [findings-01-values.md](findings-01-values.md) | Cell records, the value encodings, and how formats attach without changing a value. **The part the protobuf schemas do not describe at all.** |
| [findings-02-formulas.md](findings-02-formulas.md) | The postfix AST, why references survive being moved, cross-table links, and what a failed formula stores. |
| [findings-03-structure.md](findings-03-structure.md) | Merges, what structural edits do to them, tiles, and how tables and sheets sit on a document. |
| [findings-04-text.md](findings-04-text.md) | Text storage, style runs, OpenType features, and the typography traps. |
| [findings-06-styles.md](findings-06-styles.md) | Fills, gradients, and why a color is not three floats. |
| [findings-05-method.md](findings-05-method.md) | How these findings were produced, and the mistakes that produced them slowly. |

---

## The six that matter most

If nothing else here is read, these six change what the library has to be.

**Numbers are IEEE-754 decimal128, not float64.** `1234.5` is stored exactly. Routing a value
through a Python `float` would introduce binary rounding error into a document that never had
any, so `Cell.value` uses `Decimal`. — [values](findings-01-values.md)

**Formulas are a postfix AST with relative references, never text.** There is no formula
language to parse or emit, moving a cell needs no reference rewriting, and `$` is a per-axis
boolean rather than punctuation. The regex-based range shifting recorded as a defect in
`CLAUDE.md` was treating structure as text. — [formulas](findings-02-formulas.md)

**Merges are stored as formulas**, in a formula store beside the cells, and **Numbers rewrites
them on structural edits**. Reading is safe; writing is not — a row insert that ignores the
merge store leaves a merge pointing at the wrong row, which is exactly the phantom merge
anchor in `CLAUDE.md`. — [structure](findings-03-structure.md)

**A wrong offset produces wrong numbers, not an exception.** Every field is a fixed-width
integer or float, so misreading one still parses. This is why every layout claim needs a
fixture whose contents are known independently, and why the fixtures carry their own answer
key. — [method](findings-05-method.md)

**Color carries a color space, and it varies within a single gradient.** Storing `(r, g, b, a)`
floats would silently shift colors, because 0.5 red in sRGB is not 0.5 red in Display P3.
— [styles](findings-06-styles.md)

**Real OpenType features sit right beside Apple's synthetic imitations.** `superscript` and
`capitalization = kSmallCaps` fake the effect on the existing glyph; the honest route is a
font feature. pybers must be able to tell them apart and must never write the fake form.
— [text](findings-04-text.md)

---

## What is still unknown

- The **flags bitmask** on a cell record gates which trailing references are present, but the
  bit-to-field mapping is not worked out. Only the last reference is identified, as the format
  key.
- **Node type 32** appears after a function call in several files with no established meaning,
  and the AST node message has 45 fields of which a handful are identified.
- **Function indices are numeric** — 168 is SUM, 62 is IF, 231 is SUMIFS — and a full name map
  has to be derived rather than borrowed, per the schema-ownership decision in `CLAUDE.md`.
- **Header rows, header columns and footers** are switched off in every fixture here, so the
  default Numbers table shape is untested. `41-table-bands` covers it and is worth promoting.
- **Whether `character_index` counts UTF-16 code units or Unicode scalars.** Apple's text stack
  is NSString, which is UTF-16, so it is very likely code units — but the corpus contains no
  astral-plane character, so the two are indistinguishable in every fixture read so far. Style
  run boundaries after an emoji would drift silently. `47-unicode-text` exists to settle it.
- **Where a supplied image is stored.** `28` exercises image fills, but only with the default
  image Numbers provides, whose data is not in the document at all. A fixture with a real
  image dragged in would settle it.

---

Type identifiers throughout are ours, read from `ArchiveInfo.message_infos`. Human-readable
class names come from `reference/numbers-parser`'s `mapping.py` and are used **for
interpretation only** — pybers has not extracted its own mapping yet, and doing so is the half
of the bootstrap that requires executing an unsigned copy of Numbers.

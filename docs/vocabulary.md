# Vocabulary

Each word pybers uses for an action or a part has one meaning, shared by the library and the command line. A new call reuses a word from this page, and a new word joins this page before any call relies on it. [`CLAUDE.md`](../CLAUDE.md) sets out how a name is built from these words, under House style. The [library design](library-design.md) and the [command-line design](cli-design.md) use them, and [the decisions](decisions.md) record why a contested word won. Review holds every new public name to this page, under naming in the [code review rubric](code-review-rubric.md).

## Verbs

A method ends in its verb, `rowAdd`, and a module-level function begins with it, `findCurrency`.

| Verb | Meaning | Follows | Example |
| ---- | ------- | ------- | ------- |
| Set | Replace a whole part with the value given | CSS `cssText` | `document.cellSet` |
| Update | Change each property given and keep every other | Python `dict.update` | `cellStyleUpdate` |
| Add | Insert a new part | Python `set.add` | `table.rowAdd` |
| Remove | Delete a part and return it | Python `dict.pop` | `table.rowRemove` |
| Copy | Duplicate a block of cells at another position, keeping the source | Python `shutil.copy` | `table.cellsCopy` |
| Move | Relocate a block of cells, emptying the source | Python `shutil.move` | `table.cellsMove` |
| Fill | Repeat a block across a range | Numbers' Autofill | `table.cellsFill` |
| Find | Return the one part a key identifies | ECMAScript `Array.prototype.find` | `findCurrency` |
| Iterate | Yield each part in order | Python `iter` | `document.cellsIterate` |
| Shown | Return the value Numbers displays, every layer of style resolved | CSS computed value | `table.cellFillShown` |
| select | Return every part a selector matches | DOM `querySelectorAll` | `document.select` |
| parse | Read a value from its text form | ECMAScript `JSON.parse` | `parseCellValue` |
| format | Write a value as the text that `parse` reads back | `Intl.NumberFormat.format` | `formatFormula` |
| compose | Build a message for a person to read | Rust compiler diagnostics | `composeChoiceRefusal` |
| escape | Mark each special character in a name so a selector reads it literally | CSS `CSS.escape` | `escapeSelectorName` |
| resolve | Turn a relative position or an unbounded range into a concrete one | Python `Path.resolve`, `slice.indices` | `coordinate.resolve`, `range.resolve` |
| shift | Move a position in place and report whether it moved | Python `list.sort` | `location.shift` |
| shifted | Return a moved copy and leave the original unchanged | Python `sorted` | `coordinate.shifted` |
| open | Read a document from a path | Python `open` | `pybers.open` |
| create | Make a new, empty document | Numbers' File > New | `pybers.create` |
| save | Write a document to a path | Numbers' File > Save | `document.save` |
| check | Report whether pybers can read a document | `cargo check` | `checkDocument` |
| show | Print a document, or what a selector matches, for a person to read | `git show` | `pybers show` |

## Verbs on the command line

A command is a verb, and an option of `set` is the part it sets. A verb with no entry in this table has no command yet.

| Verb | Command line | Example |
| ---- | ------------ | ------- |
| Set | `pybers set`, one option for each part: `--cell-format`, `--cell-control`, `--cell-style`, `--border` and `--table-style` | `pybers set budget.numbers Summary::Costs::B4 --cell-format number` |
| Set, for a locale | `pybers set` given `--locale` and no `SELECTOR` | `pybers set budget.numbers --locale de_DE` |
| Update | An option of `pybers set`, which PYB-290 adds | |
| select | The `SELECTOR` argument of every command taking one | `pybers show budget.numbers Summary::Costs::B2:B9` |
| parse | The text every option and `VALUE` argument reads | `--cell-style 'background: #ff0000ff'` |
| format | The text `pybers show` and `pybers set` print, which `parse` reads back | `pybers show budget.numbers Summary::Costs::B4` |
| open | The `FILE` argument of every command | `pybers check budget.numbers` |
| save | Every command that writes, unless given `--preview` | `pybers set budget.numbers Summary::Costs::B4 1250.00 --preview` |
| check | `pybers check` | `pybers check --names budget.numbers` |

## Names by Python's conventions

Python's own forms carry no verb from the table above. pybers writes each in camelCase, so Python's `as_posix` would be `asPosix` here. A method Python itself requires, such as `tzinfo.utcoffset`, keeps Python's spelling.

| Form | Meaning | Follows | Example |
| ---- | ------- | ------- | ------- |
| `from` and a noun | Build an instance from another kind of value | Python `int.from_bytes` | `FormulaFunctionCall.fromName` |
| `as` and a noun | Return the same value as another type | Python `PurePath.as_posix` | `cellReference.asReference` |
| `to` and a noun | Convert a value into another kind | Python `int.to_bytes` | `toColumnLetter` |
| A class method named for its result | Build the instance its name describes | Python `datetime.today` | `Color.gray` |
| `is` and an adjective, or a verb in the third person | Answer a yes-or-no question | Python `str.isdigit`, `str.startswith` | `table.isAddressable`, `range.covers` |
| A noun alone | Return the part a name or a position identifies | Python `dict[key]` | `document.sheet`, `table.cell` |

## Reserved nouns

Each noun below keeps one meaning across the library, the command line and the docs. A second meaning needs a second word.

| Noun | Meaning | Follows |
| ---- | ------- | ------- |
| merge | Cells joined into one, their anchor holding the content | Numbers' Merge Cells |
| style | How a part looks: a cell's box, a table's lines, or a named style | CSS style |
| named style | A style a document keeps by name and several parts share | CSS class |
| variation | A part's own changes to the named style beneath it | CSS inline style |
| format | How a cell writes its value as text, such as currency or date | `Intl.NumberFormat` |
| family | One kind of format, such as number, currency or duration | Numbers' Format pop-up menu |
| control | The checkbox, slider or other device a person uses to change a cell's value | Numbers' Data Format controls |
| kind | The sort of value a cell holds, such as number, text or date | Numbers' cell types |
| fill | What paints an area: a color, a gradient or an image | CSS `background` |
| stroke | How a line is drawn: its width, color and pattern | SVG `stroke` |
| line | A stroke a table or a drawable draws for itself: a gridline, a separator, a table's outline, a shape's edge or a line on a sheet | SVG `line` |
| border | A stroke a cell draws on one of its sides | CSS `border` |
| band | A color painted on every second body row | Numbers' Alternating Row Color |
| header, footer | Rows or columns at a table's edge that Numbers styles itself | Numbers' Headers & Footer |
| section | The body, header rows, header columns or footer rows of a table | HTML table sections |
| address | A cell's row and column, counted from one, with no table | A1 notation |
| reference | An address with `$` on each axis and, where needed, its table | Numbers' cell reference |
| range | A rectangle of cells | Numbers' cell range |
| selector | Text choosing parts of a document, written as CSS writes one | CSS selector |
| locale | The language and region whose conventions govern how a document writes its values | Numbers' Language & Region |
| region | The country or area a locale specifies, `DE` in `de_DE` | `Intl.Locale.region` |

A noun can share its spelling with a verb, and the name's position tells them apart: `formatCellFormat` writes a format as text, and `cellsFill` repeats a block where `cellFillShown` returns a fill.

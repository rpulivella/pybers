# Vocabulary

Each word pybers uses for an action or a part has one meaning, shared by the library and the command line. A new call reuses a word from this page, and a new word joins this page before any call relies on it. `CLAUDE.md` sets out how a name is built from these words, under House style, and `decisions.md` records why a contested word won.

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
| resolve | Turn a relative position into an absolute one | Python `Path.resolve` | `coordinate.resolve` |
| shift | Move a position in place and report whether it moved | Python `list.sort` | `location.shift` |
| shifted | Return a moved copy and leave the original unchanged | Python `sorted` | `coordinate.shifted` |
| open | Read a document from a path | Python `open` | `pybers.open` |
| create | Make a new, empty document | Numbers' File > New | `pybers.create` |
| save | Write a document to a path | Numbers' File > Save | `document.save` |
| check | Report whether pybers can read a document | `cargo check` | `checkDocument` |

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

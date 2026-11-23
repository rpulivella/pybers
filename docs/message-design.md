# Message design

How every message pybers writes is built and worded: an error a call raises, a refusal a command prints, a part a write skipped, and the help a command gives. Each shape below has one composer, so a message's structure comes from the composer and its author supplies only the words. The [library design](library-design.md) says which error a call raises, the [command-line design](cli-design.md) says where a command prints a message and how it looks, and [`CLAUDE.md`](../CLAUDE.md) holds the house style the words follow. The [vocabulary](vocabulary.md) supplies every word a message uses for an action or a part.

## Readers

- **A script author or an agent** reads a message as an exception, in a traceback or in `str(error)`.
- **A person at a terminal** reads the same message as one line on stderr, after the command's name.

Both read the same words, so a message serves whoever reads it without knowing the recipient.

## Structure

A refusal has up to four parts, always in this order:

1. **The place**, the subject of the first sentence: a cell, a table, a file, an option, or the text given.
2. **The cause**, the rest of that sentence, in the reader's terms.
3. **The fix**, a sentence of its own, apart from the cause, given only when one exists.
4. **What was not done**, a sentence of its own: `Nothing was written.` It is given wherever the call would have read or changed something, and a call that changes nothing, such as parsing a selector or building a color, ends at its fix.

```
Sheet 1::Table 1::B4 holds a formula, so a value written there would discard it. Clear the formula first. Nothing was written.
└─ place ──────────┘ └─ cause ──────────────────────────────────────────────┘ └─ fix ──────────────────┘ └─ not done ───────┘
```

Nothing precedes the place, so a reader scanning a column of refusals sees the subject of each first. The cause states what is so, never what went wrong inside pybers, and a value given is quoted exactly as given, so it pastes back.

## Grammar

- **The cause is in the present tense**: `holds a formula`, `is not a color`, `is not supported`.
- **The fix is in the imperative**: `Clear the formula first.`, `Write it as #rrggbbaa.` A refused choice states its closest as a fact, `The closest is table-outline.`, since the reader picks it.
- **What was not done is in the past tense**: `Nothing was written.`, `Nothing was read.`
- **Every part is a complete sentence ending in a period**, except a skipped part's phrase, which takes none.
- **A limit of pybers reads `is not supported`**, and a fact about Numbers names Numbers: `Numbers allows at most five header rows.`
- **A message promises no future work.** `yet`, `not yet`, `for now` and `currently` describe a plan, and a plan belongs in a ticket. A message states what pybers does today.
- **A message names `pybers`**, never "this library", and cuts any clause the reader does not need.

## Both consumers

A message both consumers show names no call, argument or option that only one of them has. `cellStyleUpdate` means nothing at a shell, and `--cell-style` means nothing in a script. A fix that needs one consumer's own name is added by that consumer: a refused choice carries its choices on the error, and the command line appends `` `pybers set --help` lists every one.`` where the message names none, while the library's message ends before it. A message only one consumer shows, such as a command-line usage error, names that consumer's options freely.

## Shapes

| Shape | When | Composer |
| ----- | ---- | -------- |
| Refusal | A call or a command declines what it was given | `composeRefusal` |
| Refused choice | A value given is not among a closed set of choices | `composeChoiceRefusal` |
| Malformed text | Text pybers parses, a selector, a formula, a format or a color, does not read | `composeTextRefusal` |
| Unreadable document | A file is not a Numbers document pybers can read | `composeReadRefusal` |
| Fault in pybers | pybers reaches a state it should never reach | `composeFault` |
| Skipped part | A write matched a part and left it unwritten | `CellSkip` |
| Usage error | A command line itself is wrong | `composeUsageRefusal` |
| Help | A command or an option says what it does | the docstring, and `help=` |

### Refusal

The default shape, for every refusal no other shape covers.

```
Sheet 1::Table 1::B4 holds a formula, so a value written there would discard it. Clear the formula first. Nothing was written.
```

### Refused choice

The place is the value given, the cause says what it is not, and the fix names the closest valid choice. Where no choice is close, the message lists every choice when there are five or fewer, and otherwise ends at the cause, the error carrying its choices for the consumer to say where the list is.

```
'table-border' is not a table style property. The closest is table-outline. Nothing was written.
```

### Malformed text

The place is the text and the column where the fault sits, counted from one, so the reader finds it without counting characters.

```
`Budget::Q3::B0`, column 13, is not an address, since rows count from one. Write it as `B1`.
```

### Unreadable document

The place is the file. The cause says in the reader's terms what the file lacks, and never names an archive the reader cannot see. `pybers check` and `pybers.checkDocument` report the archive for a bug report.

```
/Documents/budget.numbers holds no table identities, which every Numbers document carries. Open it in Numbers and save it again. Nothing was read.
```

### Fault in pybers

A state pybers should never reach, so the reader cannot fix it and reports it. The cause states the state found, and the fix asks for a report. It is a `RuntimeError` subclass, raised `from` the exception that revealed it.

```
Sheet 1::Table 1 holds a formula key past the end of its cell record. Report this at https://github.com/rpulivella/pybers/issues. Nothing was written.
```

### Skipped part

A phrase in the present tense, with no capital and no period, since the line printing it names the part first.

```
Skipped: Sheet 1::Table 1::B4  holds a formula
```

### Usage error

A command line that cannot run, shown only at a shell, so it names options freely. The place is the option or argument at fault.

```
-o and --preview cannot be given together. Give one of them. Nothing was written.
```

### Help

- **A command's help is one imperative sentence**, its docstring: `Show a document, or every part a selector matches.`
- **An option's or an argument's help is one sentence**, in the imperative for an option that acts, `Show the change and write nothing.`, and a noun phrase for a value it takes, `The .numbers document.`

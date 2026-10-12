# Command-line design

How pybers looks and reads in a terminal: the design system for its front ends. Every command follows it, and a new convention is added here before a second command needs it. What a command calls in the library, and what that call returns, is in [the library design](library-design.md). The reasoning behind either belongs in `decisions.md`. This is the shape pybers is built toward, and a part not yet built is built to it by its own ticket.

## Users

- **A person at a shell** interrogates a document, converts it, views it, makes a spot change, or extracts part of it, without opening Numbers.
- **An agent** reads, changes and creates Numbers documents for a person, on any system Python runs on, and holds a dialog with the file. pybers is its conduit, not a server.

Repetitive or many-step work belongs in a script using the library, which offers everything. The command line covers transactions and conversions.

## Commands

Workflows are top-level verbs. A noun groups verbs only once one resource needs several, as `uv python install` does. Each command answers to one library call.

| Command | What it does |
| ------- | ------------ |
| `pybers FILE` | Runs `check --names FILE`, so a document always shows something |
| `check FILE` | Whether pybers can read a document, safe to post publicly |
| `show FILE [SELECTOR]` | A small part of a document, for reading |
| `export FILE [SELECTOR]` | JSON, YAML, CSV or a new `.numbers` document, to stdout or `-o` |
| `set FILE ADDRESS VALUE` | One cell's value or formula |
| `import FILE DATA` | Data brought into a document, at addresses or as a new one |
| `diff A B` | The cells that differ between two documents |
| `visinum FILE [ADDRESS]` | The read-only terminal browser |

`check` and `visinum` are committed. The rest are the agreed vocabulary, and each gains its options in its own ticket. With no arguments, `pybers` prints its help.

- **The default action** comes from a `TyperGroup` subclass that routes a first argument naming no command to `check --names`. A file named like a command is reached as `./check`.
- **`python -m pybers`** runs the same command.

## What a command adds

A command parses its arguments, calls the library once, formats what comes back, and chooses the exit status. Nothing else, so a script and a command never disagree.

- **Selectors and addresses** are positional, quoted in the shell, and parsed by the library. Tab completion offers the sheet and table names of the file being typed.
- **Each command has one default format** that does not change when its output is piped. A terminal only turns color on. `--format` chooses another, and `-o FILE` infers it from the extension.
- **Every command offers `--format text`, its default, and `--format json`**, so an agent or a pipeline never parses a report. Both come from `pybers.cli._formats`, and a command never builds JSON itself. JSON keys are the library's own field names, `None` is `null`, and a value missing for a reason is the name of its sentinel, such as `"UNDETERMINED"`.
- **`-` is stdin or stdout** for text formats. A `.numbers` document is never written to stdout.
- **Nothing prompts.** A command that would need an answer refuses instead.

## Writing

- **A write names its target**: `--in-place` changes the file given, and `-o NEW` writes a new document beside it. A command that writes requires one of the two.
- **`--dry-run`** shows the change and writes nothing, and a change that alters nothing writes nothing.
- **A cell outside its table** is refused, naming the table's size, unless `--extend` grows the table to hold it.

## Formulas

A command shows a formula as the library returns it, stored and never recalculated. CSV holds one thing per cell, so `export` writes the cached values to CSV unless `--formulas` asks for the formulas.

## Report lines

- **Each line opens with the shortest label that names its value**, then `: ` and the value: `Readable: yes`, `OS: macOS-26.6.1`.
- **Labels that belong together match** in structure, wording and tense: `Unrecognized cell types` beside `Unrecognized cells`, never one of them a clause.
- **A value pybers could not determine reads `unknown`**, and an empty one reads `none`.
- **A hierarchy is a tree under its label**, drawn with `TreeCompact` from `pybers.cli._console`: Rich's `Tree` with two-column guides rather than four, the guides in `label` style and the top level at column 0.

  ```
  Unrecognized cells:
  Sheet1
  └ Table 1
    ├ B7: cell type 4
    └ C9: cell type 4
  ```

## Errors

- **A refusal is one line on stderr**, naming the command, the file and the reason the library's error gives: `pybers check: /tmp/a.numbers does not exist.`
- **A message the command writes itself** follows the library's rule for wording an error.
- **`--debug`, or `PYBERS_DEBUG=1`, replaces that line with the full traceback.** Tracebacks never show local variables, because one can hold a cell's value.

## Exit status

| Status | Meaning |
| ------ | ------- |
| `0` | The command did what was asked. |
| `1` | pybers refused the file or could not read the document, or `diff` found a difference. |
| `2` | The command line itself was wrong, reported by Typer. |

## Rich

- **Rich renders everything a command prints**, through the two consoles in `pybers.cli._console`: `console` on stdout for results, `statusConsole` on stderr for spinners, progress and refusals. A result piped to a file or pasted into an issue therefore never carries a spinner frame.
- **Rich drops color when the output is not a terminal**, so a pasted report is plain text and needs no flag.
- **Text from a document or an exception is escaped** with `rich.markup.escape`, or printed with `markup=False, highlight=False`, because Rich silently swallows a bracketed word such as a table named `[draft]`.
- **No borders.** A table is `Table(box=None)` and a section is a label, never a panel.

## Color

Named styles in one Rich `Theme`, so a command names a meaning and never a color.

| Style | Rich style | Meaning | Example |
| ----- | ---------- | ------- | ------- |
| `label` | `dim` | The label before a value | `Readable:` |
| `value` | `bold` | A value, a version, a sheet or table name | `15.3.1` |
| `success` | `green` | A good outcome | `yes` |
| `failure` | `red` | A refusal, an error, a failed read | `no, ReadError: …` |
| `warning` | `yellow` | Something to look at, such as a nonzero count of untested types | `3008 (x2)` |
| `detail` | `dim` | Secondary lines under a value | `  at document/_read.py:103` |
| `identifier` | `bold cyan` | A type identifier, a cell address | `B7` |

Bold rather than bright white, which nearly vanishes on a light terminal.

## Spinners and progress

- **A spinner is Rich's default, `dots`**, through `statusConsole.status(...)`. Its text is a lowercase gerund ending in `…`: `reading the document…`.
- **A progress bar is used only when the total is known**, and every one is built the same way:

  ```python
  Progress(
      SpinnerColumn(),
      TextColumn("{task.description}"),
      BarColumn(bar_width=24),
      MofNCompleteColumn(),
      TimeElapsedColumn(),
      console=statusConsole,
      transient=True,
  )
  ```

- **Each `onProgress` call** from the library becomes a spinner or progress update.
- **A transient display disappears when it finishes**, so what remains on screen is the result alone.

## Help

- **Typer renders help with Rich**, in its default colors and without borders. Typer hard-codes a rounded box around each help and error panel, so `pybers.cli._app` draws each one as its title over its table, both one column in, as Typer indents its usage line.
- **A command's help is its docstring**, one imperative sentence, which Typer prints.

## Terminal interface

`pybers visinum` is a second front end over the same library and the same addresses, built with Textual. A view model inside it holds what only a live view needs, such as the cursor and the scroll position, and the library holds the document.

## Inspiration

| Project | What pybers took |
| ------- | ---------------- |
| [sqlite-utils](https://sqlite-utils.datasette.io/en/stable/cli.html) | Each command mirrors one library call, and output formats are flags |
| [uv](https://docs.astral.sh/uv/reference/cli/) | Workflows as top-level verbs, nouns only for resources |
| [pandoc](https://pandoc.org/MANUAL.html) | The output format inferred from `-o`, and binary output kept off stdout |
| [Miller](https://miller.readthedocs.io/en/latest/file-formats/) | Writing in place only when asked |
| [csvkit](https://csvkit.readthedocs.io/en/latest/scripts/in2csv.html) | stdin and stdout so commands compose, and one verb rather than a binary per job |
| [numbers-parser](https://github.com/masaccio/numbers-parser) | Formulas or values as a CSV choice |
| [openpyxl](https://openpyxl.readthedocs.io/en/stable/tutorial.html), [pandas](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html), [polars](https://docs.pola.rs/api/python/stable/reference/api/polars.read_excel.html) | Names rather than indices, whose bases they disagree on, and no silent overwrite |
| [jq and yq](https://jqlang.org/manual/) | A path syntax, and a lossless round trip, which yq's in-place mode lacks |
| [VisiData](https://www.visidata.org/docs/api/) | A browser over the same engine, opening at a given cell |
| [ruff](https://docs.astral.sh/ruff/linter/), [git diff](https://git-scm.com/docs/git-diff) | Exit status 1 for a finding, 2 for a usage error |

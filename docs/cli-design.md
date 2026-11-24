# Command-line design

How pybers looks and reads in a terminal: the design system for its front ends. Every command follows it, and a new convention is added here before a second command needs it. A command and an option take their words from [the vocabulary](vocabulary.md). What a command calls in the library, and what that call returns, is in [the library design](library-design.md). The reasoning behind either belongs in `decisions.md`. This is the shape pybers is built toward, and a part not yet built is built to it by its own ticket.

## Users

- **A person at a shell** interrogates a document, converts it, views it, makes a spot change, or extracts part of it, without opening Numbers.
- **An agent** reads, changes and creates Numbers documents for a person, on any system Python runs on, and holds a dialog with the file. pybers is its conduit, not a server.

Repetitive or many-step work belongs in a script using the library, which offers everything. The command line covers transactions and conversions.

## Commands

Workflows are top-level verbs. A noun groups verbs only once one resource needs several, as `uv python install` does. Each command answers to one library call.

| Command | What it does |
| ------- | ------------ |
| `pybers FILE` | Runs `check --names FILE`, so a document always shows something |
| `check FILE` | Whether pybers can read a document, and the tree of its sheets and tables with each unrecognized cell badged, safe to post publicly, `--names` showing each sheet's and table's name and each such cell's address |
| `show FILE [SELECTOR]` | A whole document, or every part a selector matches, for reading. `show fonts [SELECTOR]` shows the faces pybers knows, and a font file as FILE shows its own |
| `export FILE [SELECTOR]` | JSON, YAML, CSV or a new `.numbers` document, to stdout or `-o`, never changing FILE |
| `set FILE SELECTOR [VALUE] [--cell-format FORMAT] [--cell-control CONTROL] [--cell-style STYLE] [--cell-style-update STYLE] [--cell-style-remove PROPERTY] [--border POSITION ...] [--table-style STYLE]` | The value, the format, the control, the cell style and the borders of every cell a selector matches, or the lines of every table it matches, each optional. `set FILE --locale LOCALE` changes a document's language and region instead |
| `import [FILE] DATA` | Data brought into FILE in place, into a changed copy at `-o`, or into a new document when no FILE is given |
| `diff A B` | The cells that differ between two documents |
| `visinum FILE [ADDRESS]` | The read-only terminal browser |

`check`, `show`, `set` and `visinum` are committed. The rest are the agreed vocabulary, and each gains its options in its own ticket. With no arguments, `pybers` prints its help.

- **The command line is built on [Click](https://click.palletsprojects.com/)**, from the `cli` extra, and `decisions.md` records why.
- **The default action** comes from a Click `Group` subclass that routes a first argument naming no command to `check --names`. A file named like a command is reached as `./check`.
- **`python -m pybers`** runs the same command.

## What a command adds

A command parses its arguments, calls the library once, formats what comes back, and chooses the exit status. Nothing else, so a script and a command never disagree.

- **Selectors** are positional, quoted in the shell, and parsed by the library, the one syntax `library-design.md` sets out under Addresses. A reference a command prints is that syntax, each name escaped, so it pastes back as a selector. Tab completion offers the sheet and table names of the file being typed.
- **A shell enables completion** through the environment variable Click reads, once in its startup file: `eval "$(_PYBERS_COMPLETE=zsh_source pybers)"` for zsh, after `autoload -Uz compinit && compinit` loads zsh's completion system, and `bash_source` or `fish_source` for bash or fish.
- **A command prints every part a selector matches, each as it prints alone.** `show` prints each part, and `set` each cell it wrote, exactly as `show` prints that part, so a part reads the same whatever reached it. A selector's JSON is always an array of those parts' forms, which `parseJsonForm` reads back.
- **JSON on stdout reads back, and a diagnostic goes to stderr.** A part a write skipped prints `Skipped:` and its reason on stderr, as `Written:` does, so `--output-format json` never mixes a report into the data.
- **Each command has one default format** that does not change when its output is piped. A terminal only turns color on. `--output-format` chooses another, and `-o FILE` infers it from the extension.
- **Every command offers `--output-format text`, its default, and `--output-format json`**, so an agent or a pipeline never parses a report. `pybers.cli._formats` chooses between them, and every JSON comes from `pybers.formatJsonForm`, the library's one serializer, so a command never builds JSON itself. Its keys are the library's own field names, a number is a JSON number with its exact digits, `None` is `null`, and a value missing for a reason is the name of its sentinel, such as `"UNDETERMINED"`. The rule each value follows is in `decisions.md`, under the JSON form.
- **`-` is stdin or stdout** for text formats. A `.numbers` document is never written to stdout.
- **Nothing prompts.** A command that would need an answer refuses instead.

## Writing

- **A writing verb changes FILE itself**, since the verb is the act, as `sqlite-utils insert` and `git commit` are. `-o NEW` writes a new document beside it instead and refuses a file that already exists, any file, and `--preview` writes nothing. The two together are refused. `pybers.cli._common` owns the rule, both options and the report of what was written, so no command decides it.
- **`import` changes FILE in place, writes the changed document to `-o`, or creates a new document when given no FILE.** A new document is made by `pybers.create` in the region `--locale` specifies, the data is written into it, and it is saved to `-o`, as every new document starts there. `import` never needs a document Numbers made.
- **`export` never changes the document it reads.** It reads FILE and writes elsewhere, a new `.numbers` document included, so no `export` changes FILE.
- **`--preview`** shows the change and writes nothing, and a change that alters nothing writes nothing and says so.
- **`set` infers a value's kind** from the text given, and `--as KIND` overrides the inference. A value that does not parse as the kind specified is refused.
- **`set --cell-format FORMAT`** sets how the cells show their value, FORMAT being a format's text form, tagged by its family, with or without a VALUE. `--output-format` stays the output format every command offers. A format that cannot show a cell's value is refused, specifying both, unless `--conflict automatic` gives that cell the Automatic format and prints why on stderr. A format applies to every cell a range holds, an empty one included. A formula takes its format whatever its result, which Numbers shows once the result is of the format's kind.
- **`set --border POSITION`** draws borders on one block of cells, POSITION specifying the part drawn: `all`, `outer`, `outer-top`, `outer-right`, `outer-bottom`, `outer-left`, `between`, `between-rows` or `between-columns`. `--border-style` is `solid`, `dashed`, `dotted` or `hidden`, `--border-width` a length such as `1pt`, and `--border-color` a color's text form, each a separate option, and a style given alone draws 0.35pt black. `hidden` draws nothing and hides the table's line there, and `none` removes the borders so the table's line shows, as CSS names the two for a table's borders.

  ```bash
  pybers set budget.numbers 'Budget::Q3::B2:D9' --border outer --border-style dashed --border-width 1pt --border-color black
  pybers set budget.numbers 'Budget::Q3::B2:D9' --border all --border-style none
  ```
- **`set --table-style STYLE`** sets the lines of every table a selector matches, STYLE being CSS declarations, one per line a table draws: `body-horizontal-gridlines`, `body-vertical-gridlines`, `header-rows-horizontal-gridlines`, `header-rows-vertical-gridlines`, `header-columns-horizontal-gridlines`, `header-columns-vertical-gridlines`, `footer-rows-horizontal-gridlines`, `footer-rows-vertical-gridlines`, `header-rows-separator`, `header-columns-separator`, `footer-rows-separator` and `table-outline`, each `width style color` or `none`, and `table-title` and `table-outline-title`, each `yes` or `no`, and `banded-rows`, a color or `none`, with `banded-rows-background` setting the color alone. The lines between two header rows, two header columns or two footer rows take a stroke but never `none`, since no Numbers control hides them. A longhand such as `table-outline-color` changes one part of a line. `show` prints a table's style as these declarations, one per line, so a line pastes back, and `hidden` before a stroke or a band's color marks one set to none whose stroke or color is kept.

  ```bash
  pybers set budget.numbers 'Budget::Q3' --table-style 'body-vertical-gridlines: none; body-horizontal-gridlines: 0.5pt solid #8e8e93ff; table-outline: 1pt dashed black'
  ```
- **A cell outside its table** is refused, specifying the table's size, unless `--extend` grows the table to hold it.

## Fonts

A style names a face, and a person finds the face before writing the style, so `show` reads the fonts pybers knows as it reads a document.

- **`fonts` as FILE is every face pybers knows**: the catalog pybers ships, read from the fonts macOS installs, and the fonts installed on the machine running it. A font file, `.otf`, `.ttf` or `.ttc`, as FILE is that file's faces alone, installed or not. A file named `fonts` is reached as `./fonts`, as a file named like a command is.
- **A fonts selector has two positions, font family and face, joined by `::`**, with the wildcards, negation and grouping every selector has. `Avenir Next` selects a font family, and `Avenir Next::*Demi*` its faces whose names hold `Demi`.
- **A name matches ignoring case, spaces and hyphens**, so `AvenirNext`, `Avenir Next` and `avenir-next` each select Avenir Next, since a font's name is spelled many ways and only its letters specify it.
- **Conditions read what a face is**: `[weight=600]`, `[slant=italic]`, `[source=machine]` and `[postscript=AvenirNext-DemiBold]`. A weight also compares, as a CSS range query does, `[weight>=600]`.
- **A quoted value ending in `s` matches exactly**, case, spaces and hyphens included, as the `s` flag of a CSS attribute selector does: `[postscript="AvenirNext-DemiBold" s]`. No other flag exists.
- **The JSON is one form of the fonts shown**, every face and each font file pybers could not read, rather than an array of each face's form, so thousands of faces carry the form's version once. It reads back as a `Fonts`.
- **The faces print as a grid**, one row each, its columns a face's font family, name, PostScript name, weight, slant and source, its file left to the JSON. The family is grouped and in the `identifier` style, the PostScript name, which a style copies, in the `code` style, and the source in the `detail` style:

  ```
  $ pybers show fonts 'avenir next::*demi*'
  Font family  Name              PostScript name            Weight  Slant   Source
  Avenir Next  Demi Bold         AvenirNext-DemiBold           600  normal  catalog
               Demi Bold Italic  AvenirNext-DemiBoldItalic     600  italic  catalog
  ```

## Formulas

A command shows a formula as the library returns it, stored and never recalculated. CSV holds one thing per cell, so `export` writes the cached values to CSV unless `--formulas` asks for the formulas.

## Report lines

- **Each line opens with the shortest label that specifies its value**, then `: ` and the value: `Readable: yes`, `OS: macOS-26.6.1`.
- **Labels that belong together match** in structure, wording and tense: `Unrecognized cell types` beside `Unrecognized cells`, never one of them a clause.
- **A value pybers could not determine reads `unknown`**, and an empty one reads `none`.
- **A value is a phrase, never a sentence, and takes no period**: `Nothing written: previewing only`, `Nothing written: already set`, `Nothing written: already de_DE`.
- **A part a write skipped prints its reference, then two spaces and its `CellSkip` phrase**: `Skipped: Sheet 1::Table 1::B4  holds a formula`, worded as [the message design](message-design.md) sets out for a skipped part.
- **A count names its noun in the number it agrees with**: `1 row`, `10 rows`, through `formatCount` in `pybers.cli._report`, which holds every line more than one command prints.
- **A flag reads `yes` or `no`.**
- **Several parts print one after another, a blank line between each**, and each opens with a line specifying it in full, its label at full weight: `Table: Sheet 1::Table 2`, `Cell: Sheet 1::Table 2::B3`. A part's children are indented two spaces beneath it, and a part printed alone starts at column 0.
- **A part's line folds what describes it after its name, two spaces apart**: `Table: Budget::Q1  5 rows × 3 columns  1 header row, 1 footer row  12 cells`. A count of zero or an empty list is left out. A size reads `5 rows × 3 columns`, in a tree as on a line.
- **`show` prints a cell's fields in the order and under the names of its JSON form**, each key in words, so `formulaText` reads `Formula text`, folded three spaces apart onto fixed lines: its value, kind and formula, then its presentation, then its cell style, then its borders, then its unrecognized type code. A format prints as its text form, the format shown leading and `(automatic)` after one Automatic chose, `number (automatic)`, so it pastes into `set --cell-format`. A control prints as its text form too, `slider; minimum: 0; maximum: 100; increment: 1`, so it pastes into `set --cell-control`, and `none` removes one. A cell style prints as CSS declarations, `background: #ffd60aff; padding: 6pt`, so it pastes into `set --cell-style`, and `none` removes one. Borders print as CSS, `border: 1pt dashed #000000ff` where all four sides agree and a longhand per side otherwise, `border-top: 1pt dashed #000000ff; border-left: hidden`, leaving out a side that stores none, and a side whose neighbor stores another stroke specifies that cell and its stroke in parentheses. **Wherever CSS has a shorthand for what prints, it is used.** A color prints exactly as stored, so a value pastes back as the same color, which is why one off the 255 grid prints in `color()` rather than hex. `tests/test_cli_show.py` fails for a format or a control that does not read back from its line.
- **Rows of the same fields print as a grid**, through `formatGrid` in `pybers.cli._report`: a header naming each field as its JSON key reads in words, in the `label` style, then one row each, each column in the style of its role, `value` unless set. A column is as wide as its longest value and never cut, since a value may be copied whole, a number aligns right, and a grouped column, such as a face's font family, shows its value once, on the first row of the rows sharing it.
- **A hierarchy is a tree under its label**, drawn with `TreeCompact` from `pybers.cli._console`: Rich's `Tree` with two-column guides rather than four, the guides in `label` style and the top level at column 0.

  ```
  Unrecognized cells:
  Sheet1
  └ Table 1
    ├ B7: cell type 4
    └ C9: cell type 4
  ```

## Errors

- **A refusal is one line on stderr**, the command and then the reason the library's error gives, which names the file only where the file is at fault: `pybers check: /tmp/a.numbers does not exist.`, `pybers set: Numbers cannot band rows with a gradient.`
- **Every message follows [the message design](message-design.md)**, a usage error included, which `composeUsageRefusal` in `pybers.cli._common` builds. Where a refused choice names no choice, `formatRefusalText` appends `` `pybers set --help` lists every one.``, since `--help` lists every choice.
- **`--debug`, or `PYBERS_DEBUG=1`, replaces that line with the full traceback.** Tracebacks never show local variables, because one can hold a cell's value.

## Exit status

| Status | Meaning |
| ------ | ------- |
| `0` | The command did what was asked. |
| `1` | pybers refused the file or could not read the document, or `diff` found a difference. |
| `2` | The command line itself was wrong, reported by Click. |

## Rich

- **Rich renders everything a command prints**, through the two consoles in `pybers.cli._console`: `console` on stdout for results, `statusConsole` on stderr for spinners, progress and refusals. A result piped to a file or pasted into an issue therefore never carries a spinner frame.
- **Rich drops color when the output is not a terminal**, so a pasted report is plain text and needs no flag.
- **Text from a document or an exception is escaped** with `rich.markup.escape`, or printed with `markup=False, highlight=False`, because Rich silently swallows a bracketed word such as a table named `[draft]`.
- **No borders.** A table is `Table(box=None)` and a section is a label, never a panel.

## Color

Named styles in one Rich `Theme`, so a command specifies a meaning and never a color.

| Style | Rich style | Meaning | Example |
| ----- | ---------- | ------- | ------- |
| `label` | `dim` | The label before a value | `Readable:` |
| `value` | `bold` | A value, a version, a sheet or table name | `15.3.1` |
| `success` | `green` | A good outcome | `yes` |
| `failure` | `red` | A refusal, an error, a failed read | `no, ReadError: …` |
| `warning` | `yellow` | Something to look at, such as a nonzero count of untested types | `3008 (x2)` |
| `detail` | `dim` | Secondary lines under a value | `  at document/_read.py:103` |
| `identifier` | `bold cyan` | A type identifier, a cell address | `B7` |
| `code` | `cyan` | Text a person types, which help quotes in backticks and shows without them | `Budget::Q3` |
| `badge.info` | `bold black on cyan` | A badge for a fact worth noticing | |
| `badge.success` | `bold black on green` | A badge for a good outcome | |
| `badge.warning` | `bold black on yellow` | A badge for something to look at | ` UNRECOGNIZED ` |
| `badge.failure` | `bold white on red` | A badge for a fault | |
| `logo.grid` | `dim` | The logo's gridlines | `╶─` |
| `logo.mark` | `bold` | The logo's selection ring and prompt | `┃ ❯❯❯` |
| `logo.caret` | `bold #ee9e10` | The logo's caret, its one brand color | `▌` |
| `logo.name` | `bold` | The name beside the logo | `pybers` |

**A badge sets one word apart** that the reader must not miss, such as a cell pybers does not recognize. Every command writes one through `formatBadge(word, BadgeLevel.WARNING)` in `pybers.cli._report`, which writes the word upper case and padded, so it stands out in a pasted report too, and styles it by its level: info, success, warning or failure.

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

- **Every usage line follows the [POSIX utility argument syntax](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap12.html)**: a required argument bare and in capitals, `FILE`, an optional one in single brackets, `[SELECTOR]`, and `...` after one that repeats. Braces are never used, since a man page reads `{a|b}` as a choice, and no argument is wrapped twice. An option's alternatives are written `text|json`. `pybers set --help` opens with `Usage: pybers set [OPTIONS] FILE [SELECTOR] [VALUE]`.
- **The root command's help opens with the logo**, a selected cell between gridlines holding the Python prompt and a caret, beside the name, which `formatLogo` in `pybers.cli._logo` returns for any front end to print. The ring and prompt take the terminal's own color, so the logo reads on a light or a dark background, and only the caret keeps the logo's orange. No command's own help repeats it.
- **One renderer draws every help screen**, the root command's and each command's, in `pybers.cli._help`, with Rich and the theme's styles. A help screen is its usage line, its description indented two columns, then the sections `Arguments`, `Options` and `Commands`, each its title over its rows with no border, the rows indented two columns. A command is a `PybersCommand` and each argument a `PybersArgument`, which carries the help Click gives only to an option.
- **Help quotes text a person types in backticks, as Markdown does**, `` `Budget::Q3` ``. In color the renderer shows it in the `code` style without them, and where Click strips the color the backticks stay, so a pasted help still marks it.
- **A command's help is its docstring**, and each argument's and option's help is its `help=`, both worded by the rules of [the message design](message-design.md). An option shown with its default or environment variable ends with `[default: text]` or `[env var: PYBERS_DEBUG]`.
- **A usage error is Click's own**: the usage line, `Try 'pybers set --help' for help.`, then `Error:` and the message, with exit status 2.

## Terminal interface

`pybers visinum` is a second front end over the same library and the same addresses, built with Textual. A view model inside it holds what only a live view needs, such as the cursor and the scroll position, and the library holds the document.

## Inspiration

| Project | What pybers took |
| ------- | ---------------- |
| [sqlite-utils](https://sqlite-utils.datasette.io/en/stable/cli.html) | Each command mirrors one library call, output formats are flags, and a writing command changes the file it names |
| [uv](https://docs.astral.sh/uv/reference/cli/) | Workflows as top-level verbs, nouns only for resources |
| [pandoc](https://pandoc.org/MANUAL.html) | The output format inferred from `-o`, and binary output kept off stdout |
| [csvkit](https://csvkit.readthedocs.io/en/latest/scripts/in2csv.html) | stdin and stdout so commands compose, and one verb rather than a binary per job |
| [numbers-parser](https://github.com/masaccio/numbers-parser) | Formulas or values as a CSV choice |
| [openpyxl](https://openpyxl.readthedocs.io/en/stable/tutorial.html), [pandas](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html), [polars](https://docs.pola.rs/api/python/stable/reference/api/polars.read_excel.html) | Names rather than indices, whose bases they disagree on, and no silent overwrite |
| [jq and yq](https://jqlang.org/manual/) | A path syntax, and a lossless round trip, which yq's in-place mode lacks |
| [VisiData](https://www.visidata.org/docs/api/) | A browser over the same engine, opening at a given cell |
| [ruff](https://docs.astral.sh/ruff/linter/), [git diff](https://git-scm.com/docs/git-diff) | Exit status 1 for a finding, 2 for a usage error |

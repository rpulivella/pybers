# Command-line design

How pybers looks and reads in a terminal: the design system for its front ends. Every
command follows it, and a new convention is added here before a second command needs
it. The reasoning behind the command line's shape belongs in `decisions.md`.

## Report lines

- **Each line opens with the shortest label that names its value**, then `: ` and the
  value: `Readable: yes`, `OS: macOS-26.6.1`.
- **Labels that belong together match** in structure, wording and tense:
  `Unrecognized cell types` beside `Unrecognized cells`, never one of them a clause.
- **A value pybers could not determine reads `unknown`**, and an empty one reads
  `none`.
- **A hierarchy is a tree under its label**, drawn with `TreeCompact` from
  `pybers.cli._console`: Rich's `Tree` with two-column guides rather than four, the
  guides in `label` style and the top level at column 0.

  ```
  Unrecognized cells:
  Sheet1
  └ Table 1
    ├ B7: cell type 4
    └ C9: cell type 4
  ```

## Errors

- **A refusal is one line on stderr**, naming the command, the file and the reason:
  `pybers check: No such file: /tmp/a.numbers`.
- **`--debug`, or `PYBERS_DEBUG=1`, replaces that line with the full traceback.**
  Tracebacks never show local variables, because one can hold a cell's value.

## Exit status

| Status | Meaning |
| ------ | ------- |
| `0` | The command did what was asked. |
| `1` | pybers refused the file or could not read the document. |
| `2` | The command line itself was wrong, reported by Typer. |

## Rich

- **Rich renders everything a command prints**, through the two consoles in
  `pybers.cli._console`: `console` on stdout for results, `statusConsole` on stderr for
  spinners, progress and refusals. A result piped to a file or pasted into an issue
  therefore never carries a spinner frame.
- **Rich drops color when the output is not a terminal**, so a pasted report is plain
  text and needs no flag.
- **Text from a document or an exception is escaped** with `rich.markup.escape`, or
  printed with `markup=False, highlight=False`, because Rich silently swallows a
  bracketed word such as a table named `[draft]`.
- **No borders.** A table is `Table(box=None)` and a section is a label, never a
  panel.

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

- **A spinner is Rich's default, `dots`**, through `statusConsole.status(...)`. Its text
  is a lowercase gerund ending in `…`: `reading the document…`.
- **A progress bar is used only when the total is known**, and every one is built the
  same way:

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

- **Library code never touches the terminal.** A long operation takes an `onProgress`
  callback, and the command turns each call into a spinner or progress update.
- **A transient display disappears when it finishes**, so what remains on screen is
  the result alone.

## Help

- **Typer renders help with Rich**, in its default colors and without borders. Typer
  hard-codes a rounded box around each help and error panel, so `pybers.cli._app`
  draws each one as its title over its table, both one column in, as Typer indents
  its usage line.
- **A command's help is its docstring**, one imperative sentence, which Typer prints.

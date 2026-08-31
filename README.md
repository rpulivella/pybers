# pybers

A round-trip-tested Python library for reading and writing Apple Numbers documents,
built in deep respect for Apple Numbers itself. The goal is for editing a `.numbers`
file programmatically to be as reliable as editing it by hand.

> **Status: not yet usable.** The archive layer reads a real `.numbers` package end to
> end and the object model exists, but nothing connects them, so there is no supported
> way to open a file yet. See [What works today](#what-works-today) for the honest line
> between finished and not.

## Why this exists

`pybers` exists because a real project needed a different foundation: dataclasses instead
of the existing object model, a library and CLI/TUI split from the start, and named
styles as a first-class concept rather than a retrofit. Those are design preferences, not
criticisms, and they are worth a clean build rather than bending someone else's
architecture around them.

There is a simpler reason under all of that: I love writing Python. Taking a `.numbers`
file apart is satisfying work, and Python is where I wanted to do it.

`pybers` stands on the shoulders of
[`numbers-parser`](https://github.com/masaccio/numbers-parser) by
[masaccio](https://github.com/masaccio), which reverse-engineered Apple's entirely
undocumented `.numbers` archive format, the protobuf schemas, the compression and the
formula AST, from nothing. That is a rare piece of software archaeology, and
every reader of this format builds on it. No code from it is used here, and the
[`NOTICE`](NOTICE) file records the debt permanently.

## What works today

| Layer | State |
| --- | --- |
| `pybers.archive` | **Reads** a `.numbers` package: zip container, IWA frames, a pure-Python Snappy decoder with no C dependency, length-prefixed protobuf archives, and cell values including numbers, text, dates, booleans, durations and currency. **Writes** a package back, with one bounded and documented difference in the zip envelope, confirmed to open cleanly in Numbers. |
| `pybers.model` | The dataclass object model, split by feature area: style, geometry, rich text, floating shapes, tables and cells, sheets and documents. |
| The binding between them | **Does not exist.** This is the next work. |
| `pybers.cli`, `pybers.tui` | Not started. |

The next milestone is deliberately small and measurable: change one number in a real
`.numbers` file, save it, and have Numbers open it showing the new value with nothing
else altered.

## The format, and why there are so many fixtures

46 real `.numbers` files live under `tests/fixtures/`, each one labeling its own
contents so that a decode can be verified rather than merely believed. What they
established is written up in [`tests/fixtures/FINDINGS.md`](tests/fixtures/FINDINGS.md),
split by topic. **Read that before designing anything against this format**, because
several findings invalidate the obvious approach.

The format's characteristic failure is that a wrong offset yields wrong numbers rather
than an error, which is why this project is built on real files rather than on
assumptions. Seven findings changed what the library had to be:

- Cell numbers are **decimal128**, never `float`.
- Formulas are a **postfix AST with relative references**, so there is no formula text to
  parse, and `$` is a per-axis boolean rather than a character.
- **Merges are stored as formulas**, so a structural edit that ignores the merge store
  corrupts the document.
- Color carries a **color space**, so a bare RGB triple is not a color.
- All text formatting is a **named style plus a variation** layered on it, and there is no
  unparented text style.
- **Text run indices count UTF-16 code units**, not Python characters. One astral
  character silently shifts every later run boundary by one.
- **Numbers shares style archives by reference** between objects, so a decoder that hands
  out the same mutable object turns one edit into a restyle of unrelated shapes.
  `Style` is a frozen dataclass for exactly this reason, and that contract holds on the
  read path.

## Installation

Not published to PyPI yet. To work on it:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Requires Python 3.11 or newer. The only runtime dependency is `protobuf`.

## Repository map

| Path | What lives here |
| --- | --- |
| `src/pybers/` | The library. `model/` is the object model, `archive/` is the container and reader, `protos/` and `_generated/` are the extracted iWork schemas. |
| `tests/` | The pytest suite, plus `fixtures/`: real `.numbers` files and the findings written from them. |
| `scripts/` | Repository tooling, including the schema extractor and the writing gate. See `scripts/README.md`. |
| `.claude/` | Project slash-commands used by the agentic workflow. |
| `workarea/` | Ephemeral scratch. Git-ignored apart from its README. |
| `CLAUDE.md` | Design contract, house style, and the record of every architectural decision with its reasoning. |
| `CONTRIBUTING.md` | Git workflow: commits, branches, releases. |

## The protobuf schemas are extracted, not copied

`src/pybers/protos/` holds 33 `.proto` schemas dumped from a local `Numbers.app`, and
`src/pybers/_generated/` holds the modules `protoc` compiles from them. Both are
committed, so `pip install pybers` works on a machine without Numbers present.

`scripts/protos-extract.py` re-runs the extraction against a newer Numbers when Apple
ships one. The technique, that Apple compiles the protobuf descriptors into the binary
where they can be dumped, was learned from numbers-parser's build, and the extractor
credits it in its docstring.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers the commit format, branch strategy and
release tagging. Other details:

- **Prose is linted.** `scripts/standards-check.py` checks documentation, docstrings and
  comments against the project's writing rules, the way a linter checks code. Run it
  before opening a pull request.
- **The house style is camelCase** for functions, variables and parameters, which is the
  opposite of what most Python tooling assumes. This is deliberate. Modules stay
  lowercase and classes stay PascalCase.

## License

[Apache-2.0](LICENSE). See [`NOTICE`](NOTICE) for attribution that carries forward into
derivative works.

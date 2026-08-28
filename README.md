# pybers

A clean, round-trip-tested Python library for reading and writing Apple Numbers
documents, built in deep respect for Apple Numbers itself.

> Status: **pre-kickoff scaffold.** This repository currently holds the object model, the
> pytest harness, and the design contract, not yet real `.numbers` file I/O.

- **Start here if you are a fresh session:** `docs/handoff.md`
- **Design contract, origin story, house style:** `CLAUDE.md`
- **Git workflow (commits, branches, changelog):** `CONTRIBUTING.md`
- **Research and decisions:** `docs/`
- **Vendored reference material (old fork this project replaces):** `reference/`

## Why

`pybers` would not exist without [`numbers-parser`](https://github.com/masaccio/numbers-parser)
by [masaccio](https://github.com/masaccio). Reverse-engineering Apple's entirely
undocumented `.numbers` archive format, the protobuf schemas, the compression, the
formula AST, from nothing is a remarkable piece of software archaeology, and it is the
foundation this project builds on; genuine thanks are owed for it being open source at
all.

This project grew out of real, hands-on use of a fork of that project extended to add
formula-writing support, on real files, for a real budget. That extension work surfaced a
handful of correctness bugs along the way, style loss on write, a shared mutable `Style`
object corrupting an unrelated cell, a row-insert regex that shifted the wrong end of a
formula range, ordinary friction from pushing a young feature branch further, not a
reflection on the project as a whole. `pybers` exists because this developer wanted a
different foundation for those specific bugs and a few other things he had been wanting
regardless (dataclasses, a library-and-CLI/TUI split, first-class named styles), not
because `numbers-parser` did anything wrong. Full story, including the specific bugs, is
in `CLAUDE.md`. That project is not vendored here. It is a separate checkout kept
outside this repository.

## Repository map

| Path | What lives here |
| --- | --- |
| `src/pybers/` | The library itself. |
| `tests/` | Pytest suite, round-trip and golden-file tests once `pybers.archive` exists. |
| `docs/` | Research and decisions, incl. `handoff.md`. **Committed.** |
| `reference/` | Vendored old fork + patch rationale, study, do not extend. |
| `scripts/` | Repo tooling (`ticket.py` and future build/release scripts). |
| `.claude/` | Project slash-commands. |
| `workarea/` | Ephemeral human scratch. **Git-ignored** (only its README is tracked). |
| `CLAUDE.md` | The agent constitution, design contract, house style, origin story. |
| `CONTRIBUTING.md` | Git workflow: commits, branches, changelog. |

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See `CONTRIBUTING.md` for the full commit/branch workflow.

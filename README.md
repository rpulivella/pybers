# pybers

A clean, round-trip-tested Python library for reading and writing Apple Numbers
documents — built in deep respect for Apple Numbers itself.

> Status: **pre-kickoff scaffold.** This repository currently holds the object model, the
> pytest harness, and the design contract — not yet real `.numbers` file I/O.

- **Start here if you're a fresh session:** `docs/handoff.md`
- **Design contract, origin story, house style:** `CLAUDE.md`
- **Git workflow (commits, branches, changelog):** `CONTRIBUTING.md`
- **Research and decisions:** `docs/`
- **Vendored reference material (old fork this project replaces):** `reference/`

## Why

Editing a `.numbers` file programmatically should be as reliable as editing one by hand
in Numbers. This library replaces an inherited fork of `numbers-parser` that accumulated
real correctness bugs — style loss on write, a shared mutable `Style` object corrupting
an unrelated cell, a row-insert regex that shifted the wrong end of a formula range — that
ad hoc patching wasn't fixing at the root. Full story in `CLAUDE.md`.

## Repository map

| Path | What lives here |
| --- | --- |
| `src/pybers/` | The library itself. |
| `tests/` | Pytest suite — round-trip and golden-file tests once `pybers.archive` exists. |
| `docs/` | Research and decisions, incl. `handoff.md`. **Committed.** |
| `reference/` | Vendored old fork + patch rationale — study, do not extend. |
| `scripts/` | Repo tooling (`ticket.py` and future build/release scripts). |
| `.claude/` | Project slash-commands. |
| `workarea/` | Ephemeral human scratch. **Git-ignored** (only its README is tracked). |
| `CLAUDE.md` | The agent constitution — design contract, house style, origin story. |
| `CONTRIBUTING.md` | Git workflow: commits, branches, changelog. |

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See `CONTRIBUTING.md` for the full commit/branch workflow.

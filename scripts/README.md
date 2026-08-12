# pybers — Scripts

Personal tooling for this repo: the ticket/PR workflow tools and any future build/release
utilities. Every script is self-contained, runnable from the repo root, and reports
through [`rich`](https://github.com/Textualize/rich). This house style mirrors
`another repository`'s and `another repository`'s `scripts/README.md` exactly — same author,
same conventions, deliberately kept in sync. It governs `scripts/` (repo tooling) only —
`src/pybers/` (the library itself) follows the same core conventions but uses dataclasses
rather than TypedDict for data, and is documented in `CLAUDE.md`.

> Requires Python 3.11+. `rich` is required; `rich_argparse` is optional (the `--help`
> output falls back to plain argparse without it). Per-script extras are noted in each
> file's docstring.

## Current scripts

```
ticket.py    file and move tickets on GitHub Issues and the pybers Project board,
             the single sanctioned path — never hand-run the GitHub API around it
             (see the command map below). INERT until a GitHub remote and Project
             board exist — see CLAUDE.md / the handoff doc.
```

`pr-preflight-check.py` (the deterministic half of `/pr-review-code`) does not exist yet
— author it with `/script-write` once there is a real CI/test story to gate on beyond
plain `pytest`.

## Naming

Names are **topic-first**, matching the skill convention that sorts `ticket-create`
beside `ticket-edit`, so everything about one subject sorts together.

The **`test-` prefix is the deliberate exception** for a hand-rolled test script — not
used here since this project's tests are real `pytest` under `tests/`, not hand-rolled
`scripts/test-*.py`. If a repo-tooling script ever needs its own test outside pytest's
reach, follow the `test-<topic>.py` / synthetic-data / glob-discovered convention from
`another repository`'s `scripts/README.md`.

- A **`-check`** asserts something about the repository as it stands right now, and can
  fail because a *file* changed. Run it against the working tree.
- A **`test-`** is a unit test: it drives a function with synthetic inputs and can only
  fail because the *code* changed.

## ticket.py commands, and the skill that calls each

| Command | Called by |
|---|---|
| `create` | `/ticket-create` |
| `edit` | `/ticket-edit` |
| `show` | `/ticket-startwork`, `/changelog-add` (`--title-only`), `/pr-draft` |
| `start` | `/ticket-startwork` |
| `status` | `/ticket-startwork` — the move to `Code Review`, and the move back to `Concept` when a spec proves inadequate |
| `close` | `/ticket-startwork` — `--reason completed` on delivery, `--reason not-planned` on abandonment |
| `list` | `/release-tag` — reconciling shipped tickets against `CHANGELOG.md`. Also the everyday manual command for reading the board. |

Opening the pull request itself is **not** here: `/pr-draft` shells out to `gh pr create
--draft`, and merging is `gh pr merge`. Pull requests are deliberately outside this tool,
which owns Issues and the Project board only.

## ticket.py authentication

Same pattern as every other repo of this developer's, `another repository` included. Resolved in
order: `GITHUB_TOKEN` or `GH_TOKEN` in the environment, then a `GITHUB_TOKEN=` line in the
git-ignored `.dev.vars` at the repository root, then the token `gh` holds in the system
keyring.

**Prefer `.dev.vars`.** The keyring entry belongs to `gh`, and macOS grants Keychain
access per binary, so reading it from Python prompts for a password on every single run.
Either earlier source avoids that entirely.

The token must be a **classic** personal access token carrying both `repo` and `project`.
Fine-grained tokens cannot reach user-owned Project boards at all — that permission is not
offered — and `repo:status` alone is not enough: the board loads but the issues behind it
come back empty, which reads as an empty backlog rather than as a failure.

## House code rules

These hold for every script here.

1. **Never shell out to the OS when a Python library can do the work. Not ever.**
   Introducing a maintained dependency beats calling a console app. HTTP goes through
   `urllib.request` (typed exceptions), JSON through `json`, YAML through `PyYAML` —
   never `curl`, never `jq`. The one sanctioned exception is a genuinely external
   toolchain with no Python equivalent (`git`, `gh`) — those stay `subprocess`, isolated
   behind one helper, with explicit return-code handling and a comment saying why.
2. **camelCase** for functions, variables, and module-level config alike.
3. **Full type annotations on everything** — parameters, returns, and module data, even
   when the type is obvious. Dataclasses for structured config, not TypedDict.
4. **Docstrings on every function and class.** No exceptions.
5. **`argparse` for every CLI**, with `cmd`-prefixed handler functions mapping 1:1 onto
   subcommands.
6. **`rich` for all output — color-coded, never bordered.** Bordered tables/panels
   collapse to "+N lines" in the agent console. Use `console.print` with color markup;
   `Table(box=None)` if a table is genuinely needed. Show every row, never truncate.
7. **Separate logic from presentation.** A logic function computes and RETURNS a result;
   it never prints. Live progress for long operations rides a host-supplied `onProgress`
   callback into a `rich` `console.status` spinner — logic never touches the terminal
   directly.
8. **A `--dry-run` / non-destructive mode** on anything that mutates state.
9. **The dunder header block** (`__author__` … `__usage__`) on every script.
10. **No contractions**, in code, comments, or docstrings.

## Logging for long-running tasks

Prefer reviewing a log file over re-running a script to see what happened. A long-running
script writes its own timestamped log under `workarea/logs/` (git-ignored) rather than
relying on captured stdout — `workarea/logs/<script>-<timestamp>.log`.

## Setup

```
/usr/bin/env python3 -m pip install --upgrade rich rich_argparse keyring
```

See each script's docstring for its specific prerequisites.

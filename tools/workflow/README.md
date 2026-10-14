# pybers: Workflow tools

**The development workflow, shared rather than specific to pybers.** Filing and moving
tickets, opening and merging pull requests, and running the gates. Each command backs a
skill, and a skill is the only thing that should be calling one. This folder is the part
meant to be extracted and shared across repositories, so nothing here may depend on
`tools/local/`.

**What only pybers needs lives in [`tools/local/`](../local/README.md):** the extractors
that read Numbers and write `src/pybers/protos/`, `src/pybers/_generated/` and the function
table, and the golden confirmation that drives Numbers. Neither folder ships in the wheel.

Run a command from the repository root as `.venv/bin/python3 -m tools.workflow.<command>`.
Each reports through [`rich`](https://github.com/Textualize/rich). The house rules below
govern `tools/local/` too, and `src/pybers/` follows the same conventions in `CLAUDE.md`.

## Layout

This folder lists only the commands a person runs. What they import sits in `lib/`, and a
test imports from `lib/`, never a command.

```
ticket.py            file and move tickets on GitHub Issues and the pybers Project
                     board, the single sanctioned path (see the command map below)
pr.py                open, inspect, promote and merge pull requests, so that no skill
                     needs `gh`, whose identity is an ambient keyring holding several
                     accounts at once
preflight.py         run every gate in one pass and report all of them: pytest, the
                     prose gate, ruff and mypy. What `.github/workflows/preflight.yml`
                     calls, so the gate list lives here rather than in two places
standards_check.py   the prose gate on its own, for a file, the tree or a string
merge_readiness.py   gather a branch's facts, check a pull request, and post one
                     verdict as a comment. `collect` runs on the branch with no write
                     access, and `report` runs this repository's code over those facts
```

## Naming

Names are **topic-first**, matching the skill convention that sorts `ticket-create`
beside `ticket-edit`, so everything about one subject sorts together.

A module name takes underscores, because Python cannot import a hyphen. A `_check` command
asserts something about the repository as it stands, so it fails when a *file* changes.
Tests live under `tests/` as `pytest` and import from `lib/`.

## ticket.py commands, and the skill that calls each

| Command | Called by |
|---|---|
| `create` | `/ticket-create` |
| `edit` | `/ticket-edit` |
| `show` | `/ticket-startwork` (always `--comments`), `/pr-draft`, `/ticket-edit`, **rendered, for reading only** |
| `export-as-source` | `/ticket-edit` (`--body` and `--title`), `/changelog-add` and `/pr-draft` (`--title`), **byte-exact, for round-tripping** |
| `start` | `/ticket-startwork` |
| `status` | `/ticket-startwork`, the move to `Code Review`, and the move back to `Concept` when a spec proves inadequate |
| `close` | `/ticket-startwork`, `--reason not-planned` on abandonment. **Not on delivery**: the Project's own `Pull request merged` workflow sets Status to Done server-side when the PR lands, so closing a delivered ticket by hand only restates what already happened |
| `list` | `/release-tag`, reconciling shipped tickets against `CHANGELOG.md`. Also the everyday manual command for reading the board. |
| `comment` | Closing a ticket the board's own workflow cannot explain, and recording what a session settled. A body carries what a Status change cannot |
| `comment-export` | Revising a filed comment, **byte-exact, for round-tripping**. The rendered form is `show --comments` |
| `comment-edit` | Correcting a filed comment in place, keeping its id and its position in the thread |
| `comment-delete` | Removing one. **Permanent, GitHub keeps no copy**, so it prints the body first and takes `--dry-run` |

A comment id is scoped to the REPOSITORY rather than to the issue it sits on, which is
why every command above that reaches one takes the id alone. Passing a ticket number
beside it would imply a check that is not happening.

Pull requests are **not** here: `ticket.py` owns Issues and the Project board only.
They live in `pr.py`, and both reach GitHub through `lib/github.py`.

## pr.py commands, and the skill that calls each

| Command | Called by |
|---|---|
| `create` | `/pr-draft`, always opens a draft; there is no flag to open otherwise |
| `edit` | `/pr-draft edit`, revising a filed title or body. Reads the body back and compares, so a write that did not land fails loudly |
| `export-as-source` | `/pr-draft edit` (`--body` and `--title`), **byte-exact, for round-tripping**. Contrast `find`, which renders. `/pr-review-code` reaches it through that skill rather than directly, so the mechanism lives in one place |
| `find` | `/pr-review-code` and `/pr-merge` (`--number-only`), resolve the PR for the current branch. **Rendered, for reading only** |
| `ready` | `/pr-review-code`, the only sanctioned promotion out of draft |
| `rerun` | `/pr-merge`, restarting a check a GitHub outage canceled |
| `checks` | `/pr-review-code`, which reports the state without gating on it. `merge` calls the same helpers itself and refuses anything but passed, so the guard cannot be skipped by skipping a skill |
| `merge` | `/pr-merge`, the only skill that runs it. `--subject` required, `merge` by default and `squash` by exception |
| `comment` | Recording on the pull request what a review found, rather than leaving it in a session nobody can read later |
| `comment-list` | **Rendered, for reading only**, with the id each comment is reached by. A command of its own where `ticket.py` uses `show --comments`, because `pr.py` has no `show` to hang a flag on |
| `comment-export` | Revising a filed comment, **byte-exact, for round-tripping** |
| `comment-edit` | Replacing a review's own summary on a re-run, which costs neither the first run's record nor the comment's place in the thread |
| `comment-delete` | Removing one. **Permanent**, prints the body first and takes `--dry-run` |

`--base` defaults to `develop`. A web-facing repository whose deploy tracks another branch
passes `--base` instead of editing the default.

**Never use `gh` for any of this.** `gh` authenticates from an OAuth token in the system
keyring, which can hold several accounts at once, so the account it acts as is ambient
state no repository can pin. `pr.py` uses the explicit PAT below, which keeps every GitHub
interaction here on exactly two channels: a PAT for the API, and SSH for git itself.

## GitHub authentication

`lib/github.py` resolves the token for every command, so there is exactly one auth
story here. Resolved in order:
`GITHUB_TOKEN` or `GH_TOKEN` in the environment, then a `GITHUB_TOKEN=` line in the
git-ignored `.dev.vars` at the repository root. **There is deliberately no third
fallback**, a missing token raises rather than guessing.

**The system keyring is never consulted.** It holds `gh`'s own token, `gh` can be signed
into several accounts at once, and a fallback cascade is precisely how the wrong identity
gets used in silence.

The token must be a **classic** personal access token carrying both `repo` and `project`.
Fine-grained tokens cannot reach user-owned Project boards at all, that permission is not
offered, and `repo:status` alone is not enough: the board loads but the issues behind it
come back empty, which reads as an empty backlog rather than as a failure.

## House code rules

These hold for every script here.

1. **Never shell out to the OS when a Python library can do the work. Not ever.**
   Introducing a maintained dependency beats calling a console app. HTTP goes through
   `urllib.request` (typed exceptions), JSON through `json`, YAML through `PyYAML`,
   never `curl`, never `jq`, **never `gh`**. The one sanctioned exception is a genuinely
   external toolchain with no Python equivalent (`git`). That stays `subprocess`,
   isolated behind one helper, with explicit return-code handling and a comment saying
   why. `gh` was removed from that list on 2026-08-13: it is a shell-out AND a credential source, and it
   is a second identity system, and `pr.py` covers what it was used for.
2. **camelCase** for functions, variables, and module-level config alike.
3. **Full type annotations on everything**, parameters, returns, and module data, even
   when the type is obvious. Dataclasses for structured config, not TypedDict.
4. **Docstrings on every function and class.** No exceptions.
5. **`argparse` for every CLI**, with `run`-prefixed handler functions mapping 1:1 onto
   subcommands.
6a. **Never interpolate arbitrary text into a markup-enabled `console.print`.** rich reads
   square brackets as style tags and silently consumes any that look like one. Measured
   2026-08-18: `[hotfix]`, `[build]` and `/work/[slug]` vanish while `[90]` and `[ERROR]`
   survive, so the corruption is *inconsistent*, a reader cannot learn to distrust it
   selectively. Two cases and nothing between them:

   ```python
   console.print(body, markup=False, highlight=False)   # whole line is arbitrary
   console.print(f"title: [bold]{escape(title)}[/]")    # styled label + arbitrary value
   ```

   Treat all of these as arbitrary: issue titles and bodies, commit subjects, file and
   route paths, subprocess output, and exception messages. **The bytes were never wrong**,
   only the display, which is why this hid for so long, and why it mattered most in
   `--dry-run` previews, whose entire purpose is showing exactly what will be written.

6. **`rich` for all output, color-coded, never bordered.** Bordered tables/panels
   collapse to "+N lines" in the agent console. Use `console.print` with color markup;
   `Table(box=None)` if a table is genuinely needed. Show every row, never truncate.
7. **Separate logic from presentation.** A logic function computes and RETURNS a result;
   it never prints. Live progress for long operations rides a host-supplied `onProgress`
   callback into a `rich` `console.status` spinner, logic never touches the terminal
   directly.
8. **A `--dry-run` / non-destructive mode** on anything that mutates state.
9. **The dunder header block** (`__author__` … `__usage__`) on every script.
10. **No contractions**, in code, comments, or docstrings.
11. **A message states the miss and stops.** Any sentence a script prints or posts says
    what was found, never a remedy, a command or a script name. Detail lines take sentence
    case and no trailing period, and a count of zero is not printed.

## Logging for long-running tasks

Prefer reviewing a log file over re-running a script to see what happened. A long-running
script writes its own timestamped log under `workarea/logs/` (git-ignored) rather than
relying on captured stdout, `workarea/logs/<script>-<timestamp>.log`.

## Setup

```
.venv/bin/python3 -m pip install -e ".[dev]"
```

The `dev` extra equips the venv for every command and the suite. The one exception is the
job that posts the readiness comment, which installs rich alone, so `rich_argparse` stays
optional and `lib/github_body.py` is a lazy import. A command's docstring names any other
prerequisite.

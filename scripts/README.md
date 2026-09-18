# pybers: Scripts

**The repository harness.** Everything here serves the workflow rather than the library:
filing and moving tickets, opening and merging pull requests, and running the gates. Each
one backs a skill, and a skill is the only thing that should be calling one.

**What does NOT belong here is anything that builds pybers itself.** The extractors that
read Numbers and write `src/pybers/protos/`, `src/pybers/_generated/` and the function
table live in `tools/`, which has [its own README](../tools/README.md). The split is
whether a program serves the repository or the library; both are development tooling and
neither ships in the wheel, but they answer to different readers and change for different
reasons.

Every script is self-contained, runnable from the repo root, and reports
through [`rich`](https://github.com/Textualize/rich). This house style mirrors
the same author's other repositories exactly,
same conventions, deliberately kept in sync. The house rules below govern `tools/` too.
`src/pybers/` (the library itself) follows the same core conventions but uses dataclasses
rather than TypedDict for data, and is documented in `CLAUDE.md`.

> Requires Python 3.14+. `rich` is required; `rich_argparse` is optional (the `--help`
> output falls back to plain argparse without it). Per-script extras are noted in each
> file's docstring.

## Current scripts

```
ticket.py    file and move tickets on GitHub Issues and the pybers Project board,
             the single sanctioned path, never hand-run the GitHub API around it
             (see the command map below). Live now.
pr.py        open, inspect, promote and merge pull requests. Exists so that no
             skill needs `gh`, whose identity is an ambient keyring holding
             several accounts at once. Live now.
pr-preflight-check.py
             run every gate in one pass and report all of them: pytest, the
             prose gate, ruff and mypy. The deterministic half of
             `/pr-review-code`, and what `.github/workflows/preflight.yml`
             calls, so the gate list lives here rather than in two places, and
             that workflow names no gate of its own. Live now.
merge-readiness.py
             gather a branch's facts on GitHub, then check a pull request and
             report one verdict as a single comment on it. Two halves for two
             levels of trust: `collect` runs on the branch with no write access,
             and `report` runs this repository's code over the facts it wrote.
             `merge_readiness_lib.py` holds the checks and
             `merge_readiness_presenter.py` renders the comment. Live now.
golden-confirm.py
             confirm a golden in running Numbers and write a report of what
             Numbers shows, through a helper app that holds the permissions so
             Terminal holds none. Backs `/golden-confirm`, and nothing in the
             preflight, CI or the suite runs it. Live now.
```

## Naming

Names are **topic-first**, matching the skill convention that sorts `ticket-create`
beside `ticket-edit`, so everything about one subject sorts together.

The **`test-` prefix is the deliberate exception** for a hand-rolled test script, not
used here since this project's tests are real `pytest` under `tests/`, not hand-rolled
`scripts/test-*.py`. If a repo-tooling script ever needs its own test outside pytest's
reach, follow the `test-<topic>.py` / synthetic-data / glob-discovered convention from
the author's other repositories.

- A **`-check`** asserts something about the repository as it stands right now, and can
  fail because a *file* changed. Run it against the working tree.
- A **`test-`** is a unit test: it drives a function with synthetic inputs and can only
  fail because the *code* changed.

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
They live in `pr.py`, which shares this tool's auth rather than duplicating it.

## pr.py commands, and the skill that calls each

| Command | Called by |
|---|---|
| `create` | `/pr-draft`, always opens a draft; there is no flag to open otherwise |
| `edit` | `/pr-draft edit`, revising a filed title or body. Reads the body back and compares, so a write that did not land fails loudly |
| `export-as-source` | `/pr-draft edit` (`--body` and `--title`), **byte-exact, for round-tripping**. Contrast `find`, which renders. `/pr-review-code` reaches it through that skill rather than directly, so the mechanism lives in one place |
| `find` | `/pr-review-code` and `/pr-merge` (`--number-only`), resolve the PR for the current branch. **Rendered, for reading only** |
| `ready` | `/pr-review-code`, the only sanctioned promotion out of draft |
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

## ticket.py authentication

`pr.py` reuses this, so there is exactly one auth story here. Resolved in order:
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
5. **`argparse` for every CLI**, with `cmd`-prefixed handler functions mapping 1:1 onto
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

## Logging for long-running tasks

Prefer reviewing a log file over re-running a script to see what happened. A long-running
script writes its own timestamped log under `workarea/logs/` (git-ignored) rather than
relying on captured stdout, `workarea/logs/<script>-<timestamp>.log`.

## Setup

```
/usr/bin/env python3 -m pip install --upgrade rich rich_argparse
```

**Either interpreter runs these, corrected 2026-09-02.** `rich` and `rich_argparse` moved
into the `dev` extra, so `pip install -e ".[dev]"` equips the venv for the tooling as well
as the suite, and this section's earlier claim that the venv carried only test
dependencies stopped being true then.

**`pr-preflight-check.py` is the exception and must use the venv**, because pytest, ruff
and mypy exist nowhere else.

See each script's docstring for its specific prerequisites.

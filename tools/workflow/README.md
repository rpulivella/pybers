# Workflow tools

The development workflow a repository shares with others: tickets on GitHub Issues and a
Project board, pull requests, and the gates a change must pass. Nothing here may import
`tools/local/`, which holds what one repository alone needs.

## Running

Install the `dev` extra with `.venv/bin/python3 -m pip install -e ".[dev]"`, then run a
command from the repository root as `.venv/bin/python3 -m tools.workflow.<command>`. A
skill calls each command, and `--help` lists its subcommands.

```
ticket            issues, the Project board and comments
pr                pull requests, their checks and runs, merging, and comments
preflight         every gate in one pass: pytest, the prose gate, ruff and mypy
standards_check   the prose gate alone, for a file, the tree or a string
dashboard         the session dashboard's status line, task order and merges
```

## Layout

A folder lists only the commands a person runs. Their logic sits in `lib/`, where a test
reaches it, and a command is tested only for its own handling. A new command goes here
when every repository could use it, and in `tools/local/` when only one can. Run it,
`--preview` included, before calling it done.

## GitHub Authentication

Every command takes its token from `GITHUB_TOKEN` or `GH_TOKEN` in the environment, then
from a `GITHUB_TOKEN=` line in the git-ignored `.dev.vars` at the repository root, and
refuses without one. Neither `gh` nor the system keyring is consulted, since either can
hold several accounts and act as the wrong one in silence. The token must be a classic
personal access token with `repo` and `project`, because a fine-grained token cannot
reach a user-owned Project board.

## Workflow Rules

1. Prefer a Python library to any shell command. `git` is the one external tool, and
   `gh` has no place here.
2. camelCase, full type annotations, dataclasses for records, and a docstring on every
   function and class. A module name takes underscores, since Python cannot import a
   hyphen.
3. `argparse`, with one `run`-prefixed handler per subcommand.
4. `rich` output, never bordered. Arbitrary text prints with `markup=False` or through
   `escape()`, because rich silently consumes square brackets it reads as markup.
5. Logic returns its result and never prints.
6. `--preview` on anything that changes state.
7. The dunder header block on every file.
8. A message states what it found and stops, with no remedy, command or file name.
9. A long-running command logs to `workarea/logs/<command>-<timestamp>.log` rather than
   relying on its output.

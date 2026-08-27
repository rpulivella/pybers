# Contributing to pybers

pybers is built through an agentic harness. This guide is the single source of truth for
how change flows into the repository, commits, branches, and release tags. The invisible
laws of the codebase live in `CLAUDE.md`; this file is only about the git workflow.

## Commit message format

One scannable line per commit. The shape:

- `[<N>] <prefix>: <summary>`, the ticket number first, in brackets, read from the branch
  name. (No ticket system exists yet, this form starts once one does.)
- `[init] <prefix>: <summary>`, pre-ticket bootstrap: initial scaffolding and architecture
  de-risking, before the ticket workflow begins and before anything ships. **The default
  for this phase**. There is nothing shipped to "fix", so `[hotfix]` is wrong here.
- `[hotfix] <prefix>: <summary>`, a ticketless urgent or infrastructural change (tooling,
  a skill, CI, docs) **after shipping**, once a ticket workflow exists. Not used during
  bootstrap.
- `[workarea] <prefix>: <summary>`, a change confined to the non-shipping `workarea/`
  tree.

Rules: single line, no body, no footer; at most 60 characters including the bracket;
imperative mood; a Conventional-Commits prefix always (`feat` `fix` `perf` `refactor`
`style` `docs` `chore`). Never a `Co-Authored-By` trailer, it breaks the one-line log.

```
[init] chore: scaffold the project, package graph, and pytest gate
[init] feat: add the dataclass object model
[hotfix] docs: correct the install instructions
[workarea] chore: capture archive-format research
```

## Branch strategy

**`develop` is the one long-lived branch**, the trunk, the default, and the release
line. There is no `main` and there are no standing release branches: a solo project does
not need a parallel production line, and a tag already records exactly what shipped.

```
routine:     commit on develop
per ticket:  <type>/<id>-verbose-slug  ->  PR into develop  ->  delete branch
release:     annotated tag on develop  ->  CI build
```

- **`develop`** stays green. Routine and interactive work lands here directly. Once a
  ticket system exists, every ticket merges here through a pull request instead.
- **`type`** matches the ticket's one label: `feature` `fix` `bugfix` `chore` `docs`
  `perf` `refactor` `style`. The branch carries `feature/`; the commit inside it still
  carries the Conventional prefix `feat:`, the branch label and the commit prefix are
  two different axes.

## Release tagging

Releases are annotated tags on `develop`. There are no release branches.

```
release/v<version>-b<NN>    # pre-release build iteration (b01, b02, ...)
release/v<version>-Final    # shipped PyPI release
```

- Lowercase prefix; a `v` prefix on the version; leading zeros on iterations (`-b01`,
  never `-b1`).
- `<version>` is SemVer and matches the `version` field in `pyproject.toml`.
- Never reuse a tag, increment the iteration for a rebuild.
- Update `CHANGELOG.md`'s Unreleased section before a release tag (`/changelog-add`).

## Build and verify

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Every commit leaves the test suite green. No exceptions.

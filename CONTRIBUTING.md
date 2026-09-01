# Contributing to pybers

pybers is built through an agentic harness. This guide is the single source of truth for
how change flows into the repository, commits, branches, and release tags. The invisible
laws of the codebase live in `CLAUDE.md`; this file is only about the git workflow.

## Commit message format

One scannable line per commit. The shape:

- `[<N>] <prefix>: <summary>`, the ticket number first, in brackets, read from the branch
  name.
- `[hotfix] <prefix>: <summary>`, a ticketless urgent or infrastructural change (tooling,
  a skill, CI, docs) where a ticket adds no value. Use sparingly.
- `[init] <prefix>: <summary>`, pre-ticket bootstrap: initial scaffolding and architecture
  de-risking, before the ticket workflow begins and before anything ships. **The default
  for this phase**, and it retires the day the first ticket-numbered commit lands.

Rules: single line, no body, no footer; at most 60 characters including the bracket;
imperative mood; a Conventional-Commits-inspired prefix always (`feat` `fix` `perf`
`refactor` `style` `docs` `chore`). Never a `Co-Authored-By` trailer, it breaks the
one-line log.

```
[init] chore: scaffold the project, package graph, and pytest gate
[init] feat: add the dataclass object model
[hotfix] docs: correct the install instructions
```

## Branch strategy

**`develop` is the one long-lived trunk branch**, the default, and the release
line. There is no `main` and there are no standing release branches: a solo project does
not need a parallel production line, and a tag already records exactly what shipped.

```
per ticket:  <type>/<id>-verbose-slug  ->  PR into develop  ->  delete branch
release:     annotated tag on develop  ->  CI build
```

- **`develop`** stays green. Every ticket merges here through a pull request, and the
  only thing that lands directly is the occasional `[hotfix]`, to a doc for example.
- **`type`** is mapped from the ticket's label rather than copied from it, because two
  of the six read badly as a branch prefix: `feat` becomes `feature` and `fix` becomes
  `bugfix`, while `perf`, `refactor`, `docs` and `chore` are already their own prefix.
  Those six are the closed set.
- **The branch prefix and the commit prefix are two different axes.** A branch carries
  one `type` for the life of the ticket; the commits inside it each carry whichever
  Conventional prefix describes that commit. A `feature/12-...` branch normally holds
  several `feat:` commits and then `docs:`, `fix:` and `refactor:` as the work turns.

## What review-ready means

A pull request leaves draft when three things are true, and not before:

1. Every acceptance criterion the ticket carries is met.
2. Test coverage appropriate to the ticket exists and passes. What is appropriate is a
   judgment the ticket's own criteria settle: a decoder earns assertions against a fixture
   whose contents are known independently, and a configuration change earns proof it takes
   effect.
3. The gates pass. Today that is `.venv/bin/python3 -m pytest` and
   `scripts/standards-check.py` with zero failures. Ruff and mypy join them once #4 lands,
   and this list is meant to grow rather than to stay accurate by omission.

**A draft PR is the right place to be feature complete with tests still being written.**
Opening one early is encouraged, because the diff is easier to follow as it grows than as
one arrival. Marking it ready for review is the assertion that all three hold.

The board mirrors this: `Code Review` means an open, non-draft pull request. A branch whose
tests are still being written stays `In Progress` even though the feature works.

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

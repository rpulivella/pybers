# Contributing to pybers

pybers is built through an agentic harness. This guide is the single source of truth for how change flows into the repository, commits, branches, and release tags, and for where things live. The invisible laws of the codebase live in `CLAUDE.md`.

Everyone taking part, in any space of this repository, follows the [code of conduct](CODE_OF_CONDUCT.md).

A contribution written with an AI tool is held to the [AI policy](docs/ai-policy.md).

## Who contributes

Write access is held by collaborators. The project draws no line between a collaborator and a maintainer, and uses the one term, maintainer. At present, only a maintainer may open a pull request, and anyone else contributes by filing an issue.

## How a ticket is referenced

Tickets are written `PYB-34` in prose and pull requests `PR #38`, never a bare number and never a bare `#`. Commit subjects are the exception and keep the bare `[34]`, as does `Closes #34`, which GitHub parses in no other form. The key is declared once in `pyproject.toml` under `[tool.pybers]`.

## Commit message format

One scannable line per commit. The shape:

- `[<N>] <prefix>: <summary>`, the ticket number first, in brackets, read from the branch name.
- `[hotfix] <prefix>: <summary>`, a ticketless urgent or infrastructural change (tooling, a skill, CI, docs) where a ticket adds no value. Use sparingly.
- `[init] <prefix>: <summary>`, pre-ticket bootstrap: initial scaffolding and architecture de-risking, before the ticket workflow begins and before anything ships. **The default for this phase**, and it retires the day the first ticket-numbered commit lands.

Rules: single line, no body, no footer; at most 60 characters including the bracket; imperative mood; a Conventional-Commits-inspired prefix always (`feat` `fix` `perf` `refactor` `style` `docs` `chore`). Never a `Co-Authored-By` trailer, it breaks the one-line log.

```
[init] chore: scaffold the project, package graph, and pytest gate
[init] feat: add the dataclass object model
[hotfix] docs: correct the install instructions
```

## Branch strategy

**`develop` is the one long-lived trunk branch**, the default, and the release line. There is no `main` and there are no standing release branches: a solo project does not need a parallel production line, and a tag already records exactly what shipped.

```
per ticket:  <type>/<id>-verbose-slug  ->  PR into develop  ->  delete branch
release:     annotated tag on develop  ->  CI build
```

- **`develop`** stays green. Every ticket merges here through a pull request, and the only thing that lands directly is the occasional `[hotfix]`, to a doc for example, which an administrator pushes past the rules below.
- **`type`** is mapped from the ticket's label rather than copied from it, because two of the six read badly as a branch prefix: `feat` becomes `feature` and `fix` becomes `bugfix`, while `perf`, `refactor`, `docs` and `chore` are already their own prefix. Those six are the closed set.
- **The branch prefix and the commit prefix are two different axes.** A branch carries one `type` for the life of the ticket; the commits inside it each carry whichever Conventional prefix describes that commit. A `feature/12-...` branch normally holds several `feat:` commits and then `docs:`, `fix:` and `refactor:` as the work turns.

## What `develop` enforces

GitHub holds `develop` to these rules, which a reader without access to the repository settings cannot otherwise see:

- No direct push
- A pull request for every change
- The `preflight` and `readiness` checks passing before a merge
- No approving review required
- No requirement to be up to date with `develop`, which the `readiness` report flags instead
- An administrator able to bypass every rule above

## What review-ready means

A pull request leaves draft when three things are true, and not before:

1. Every acceptance criterion the ticket carries is met.
2. Test coverage appropriate to the ticket exists and passes. What is appropriate is a judgment the ticket's own criteria settle: a decoder earns assertions against a fixture whose contents are known independently, and a configuration change earns proof it takes effect.
3. The gates pass. All four of them, which `scripts/pr-preflight-check.py` runs in one pass and reports together, so a failing run lists everything to fix rather than the first thing: pytest, the prose gate, ruff and mypy. GitHub runs that same command once the pull request leaves draft, so there is one gate list rather than two. This list is meant to grow rather than to stay accurate by omission.

**A draft PR is the right place to be feature complete with tests still being written.** Opening one early is encouraged, because the diff is easier to follow as it grows than as one arrival. Marking it ready for review is the assertion that all three hold.

The board mirrors this: `Code Review` means an open, non-draft pull request. A branch whose tests are still being written stays `In Progress` even though the feature works.

The standard a review is held to is [docs/code-review-rubric.md](docs/code-review-rubric.md), six questions asked of the change rather than of the repository around it.

## What GitHub checks

Nothing runs on a draft. Once a pull request leaves draft, GitHub shows two checks:

- **`preflight`**, the four gates run locally, one step per gate.
- **`readiness`**, what exists only at pull request level: the template, the checklist, the CHANGELOG entry, the ticket identifier, currency with `develop`, dependency advisories, and a confirmation date for every golden touched.

A red `readiness` leaves `preflight` green, and `pr.py merge` refuses while either is red. A third workflow posts the report as one comment, replaced on every run. **Green means a person can now test the change, never that it is ready to merge.**

Dependabot advises only. It emails a maintainer when an advisory affects a declared dependency or a workflow action, it opens no pull request, and a maintainer acts on the alert by filing a ticket.

## One ticket, more than one pull request

A ticket may take several pull requests, and the last one is not always obvious when the first opens. Two rules keep that honest:

- **Every body carries its closing keyword.** That keyword is what links a pull request to its ticket on GitHub, and no API can make that link any other way. A pull request that is not the last for its ticket says so on its own line beneath the keyword.
- **Whether a merge completes the ticket is decided at merge time**, and it completes it by default. `/pr-merge` asks. When the answer is no, `pr.py merge --ticket-stays-open` merges, GitHub closes the ticket on the keyword as it always does, and the tool reopens it and restores the Status it held.

## Changelog

Every pull request adds one line to the top of `CHANGELOG.md`'s `## Unreleased` list, `- [PYB-<N>] <ticket title, verbatim>`, and `/changelog-add` writes it. The `readiness` check fails a pull request that has none. A final release reconciles the list against every ticket marked Done, and each version is headed `## X.Y.Z (build) - date`, as the file's own header states.

## Release tagging

Releases are annotated tags on `develop`. There are no release branches.

```
release/v<version>-b<NN>    # pre-release build iteration (b01, b02, ...)
release/v<version>-Final    # shipped PyPI release
```

- Lowercase prefix; a `v` prefix on the version; leading zeros on iterations (`-b01`, never `-b1`).
- `<version>` is SemVer and matches the `version` field in `pyproject.toml`.
- Never reuse a tag, increment the iteration for a rebuild.
- Update `CHANGELOG.md`'s Unreleased section before a release tag (`/changelog-add`).

## Build and verify

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
.venv/bin/python3 -m pytest                       # the suite, that exact spelling
.venv/bin/python3 scripts/pr-preflight-check.py   # all four gates, what CI runs
```

pytest alone is a partial answer. The preflight runs pytest, the prose gate, ruff and mypy in one pass and reports all four. What it cannot answer is the pull request half: the template, the CHANGELOG, the branch's currency and the dependency advisories, which the readiness report adds on GitHub.

Every commit leaves the test suite green. No exceptions.

## Repository layout

| Path | What lives here |
| --- | --- |
| `src/pybers/` | The library, a directory per feature with `_persistence/` and `_engine/` beneath them. `protos/` holds the extracted iWork schemas and `_generated/` the modules compiled from them. A leading underscore means a caller has no business there. |
| `tests/` | The pytest suite, with `fixtures/` (origins), `measurements/` (one change from an origin) and `golden/` (files pybers wrote, confirmed in Numbers). Each directory's README catalogs its files. |
| `docs/` | `decisions.md`, the settled decisions, and `findings/`, what the real files established about the format. |
| `scripts/` | Repository tooling, including the ticket and pull request tools and the prose gate. |
| `tools/` | The schema and function extractors, run against a local `Numbers.app`. |
| `.claude/` | The slash commands the agentic workflow runs. |
| `.github/` | The pull request template and the three workflows that check a pull request. |
| `workarea/` | Ephemeral scratch, git-ignored apart from its README. |

## Code and prose style

**Functions, variables and parameters are camelCase**, the opposite of what most Python tooling assumes, and ruff and mypy are configured for it. Modules stay lowercase and classes PascalCase. `CLAUDE.md` carries the rest of the house style.

**The prose gate lints prose.** Documentation, docstrings and comments are checked against the project's writing rules the way ruff checks code, because a wrong comment is a defect here. `scripts/standards-check.py` runs it alone.

As a maintainer I want pull requests checked automatically so that a contributor gets a signal without waiting for me, and so that nothing merges on an untested branch.

1. A workflow under `.github/workflows/` runs on every pull request targeting `develop` once that pull request leaves draft, and on every push to `develop`. A draft skips the job rather than running it, because the same preflight already runs on the developer's machine and a draft cannot merge, and a superseded run on the same branch is canceled rather than left to race.
2. It installs the project with `pip install -e ".[dev]"` and needs nothing else installed on the runner.
3. It runs `scripts/pr-preflight-check.py`, the same command a contributor runs before opening a pull request, and fails the job on a non-zero exit. The workflow does not name the gates itself.
4. It runs on the single Python version `pyproject.toml` declares, and names no version of its own, so the version claim lives in one place and CI never runs the same interpreter twice.
5. The job needs no `.numbers` file absent from the repository, no Numbers.app, no agent, and no network access beyond installing dependencies.
6. A failing job names which gate failed in its summary, without requiring the log to be opened.
7. `README.md` carries a status badge for this workflow, so the state of `develop` is visible without opening the Actions tab.

## SPEC

- **#3 is a prerequisite rather than a parallel effort.** Its script is the gate list, and this workflow installs and calls it. #12 AC 5 asks for that relationship to be settled, and this settles it: the preflight is the deterministic gate, CI is a second trigger for it, and neither carries its own copy of what to run.
- **A runner has no agent and a small machine.** Two vCPUs, no Numbers.app, no local venv and nothing agentic, so no gate may depend on any of those. The suite reads all 46 fixtures on every run, which is the budget any new step competes against.
- **The version is read from `pyproject.toml`, never named in the workflow.** `requires-python` is the one place a version belongs, and `actions/setup-python` takes that file directly, so the job does not go stale when the floor moves. AC 4 was rewritten on 2026-09-03: an earlier draft ran a floor leg and a stable leg, which duplicates the work outright once the two resolve to the same interpreter, and #34 would have done exactly that.

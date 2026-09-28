As a maintainer I want Dependabot watching this project so that an advisory published between pull requests reaches me, and so that a workflow does not sit on a stale action for months.

## Acceptance criteria

1. `.github/dependabot.yml` exists and configures the `github-actions` ecosystem, so an action pinned in `preflight.yml`, `readiness.yml` or `merge-readiness.yml` is raised when a newer version ships.
2. The file records whether the `pip` ecosystem is configured and why, since floors with no lockfile give a version update almost nothing to raise.
3. Dependabot alerts are enabled for the repository, and an advisory against a declared dependency reaches a maintainer by email, with neither the Actions tab nor the Security tab being opened.
4. An advisory affecting a version the floor admits produces a pull request that raises the floor `pyproject.toml` declares.
5. A pull request Dependabot opens passes the readiness checks, which means those checks say what they expect of a pull request carrying no ticket number, no template body and no CHANGELOG entry, rather than failing it for lacking them.
6. `CONTRIBUTING.md` states what a maintainer does with a Dependabot pull request, who merges it, and whether it earns a ticket.
7. No gate changes. The preflight and both workflows continue to fail only for reasons the change under review caused.

## Constraints

1. `pyproject.toml` declares floors with no lockfile anywhere, so a pip version update has close to nothing to raise. Alerts and security updates behave differently on exactly that point, which is what makes AC 2 a finding rather than a preference.
2. PYB-76 landed the per-pull-request scan, which queries OSV against the resolved environment and reports it in the readiness comment, so anything here that rescans a pull request duplicates a check that already reports.
3. Dependabot's pull requests are the one case the readiness checks were not written for, and AC 5 is the real work in this ticket.

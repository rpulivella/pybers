As a contributor I want a deterministic check I can run before requesting review so that a pull request fails on mechanical problems before a human or an agent reads it.

1. `python3 scripts/pr-preflight-check.py` exits non-zero when any gate fails and zero when they all pass.
2. It runs the full pytest suite and reports the failing tests.
3. It runs `scripts/standards-check.py` over every prose file in the repository, and fails on a FAILURE, never on a WARNING. Corrected 2026-09-02 and again 2026-09-03: the original said "the changed files", which reads as that script's own default of uncommitted work, and a preflight runs when the tree is clean, so that default would examine nothing and pass. The branch-scoped replacement was also wrong, because resolving a base ref needs history that a single-branch or shallow clone does not carry, and every other gate here is already repository-wide.
4. It runs ruff and mypy, and fails on any finding from either.
5. It reports every gate's result in one pass rather than stopping at the first failure, so one run lists everything to fix.
6. `/pr-review-code` step 2 calls it, and the skill no longer carries a note that it does not exist.
7. It runs from a fresh clone with only `pip install -e ".[dev]"` performed, needing no network access and nothing installed globally.

## SPEC

- **Three of the four gates are importable and one is not**, measured 2026-09-02. `pytest.main()`, `standards-check.py` itself, and `mypy.api.run()` are first-class interfaces, so the house rule against shelling out applies to them. Ruff's Python package is a shim exporting only `find_ruff_bin()` and no linting API at all, so ruff is located through that function and run as a binary. That is the only exception, and the binary is found through the package rather than trusted to be on PATH.
- **A repository-wide prose run does not cover every file.** `standards-check.py` carries `checkExtensions` of `.py` and `.md`, so `pyproject.toml` is outside even `--all` and is checked only when named.
- **A dependency or CVE check does not belong here.** A gate must fail only for reasons the change caused, and an advisory published overnight is not one. It also needs the network AC 7 forbids. That belongs in a scheduled job, filed separately.

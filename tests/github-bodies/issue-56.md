[PYB-54](https://github.com/rpulivella/pybers/issues/54)

Every merge in the corpus was one row tall, so the vertical axis of a merge extent had never been read, while the example documents hold twenty-seven vertical merges in a single table. This adds `22d-merge-multi-row`, seven columns by five rows carrying a two-row merge, a two-by-two and a three-row merge, along with the tests establishing that the reader already reads all three correctly. The fixture also completed a finding that only a multi-row merge could show: Numbers joins the content a merge swallows in row-major order, a tab between columns and a newline between rows, where the corpus had proved the tab half alone.

Writing those tests would have made a third copy of `archiveBodies` and a second of `recordedColumns`, so both moved to `tests/conftest.py` and the two modules that had defined them now import from it. That is the whole reason `pyproject.toml` changes: ruff grouped `conftest` with pytest as a third-party package, and one isort line puts it with `pybers` where it belongs.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes
**CI / automation / build**: None **Object model (public dataclass fields)**: None **Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

## Screenshot(s) / video(s)
None

_Closes #54_

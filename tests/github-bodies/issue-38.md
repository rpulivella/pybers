[PYB-34](https://github.com/rpulivella/pybers/issues/34)

Raises `requires-python` to 3.14 and every dependency floor to a version the project has been run on. The old floors were whatever was current when each line was written, so `>=3.11` and `protobuf>=6.32.1` were claims nothing had ever executed. The three `UP047` findings that leaving 3.11 exposes are resolved with PEP 695 type parameters rather than suppressed.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes

**CI / automation / build**: `pip install pybers` now refuses Python 3.11 through 3.13 at resolution time, and every dependency floor moves, protobuf from 6.32.1 to 7.36.1 among them. The protobuf gencode remains 6.32.1, which is the version below which the runtime provably cannot work and is deliberately no longer the declared floor.

**Object model (public dataclass fields)**: None

**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

No test was added because nothing here changes behavior: the floors are metadata, and the PEP 695 rewrite is the same three signatures in newer syntax, already covered by the existing suite. What the change needed instead was a new environment, so 747 tests ran green on a throwaway 3.14.6 venv built from nothing, which is what AC 6 asks for, and every declared floor now equals the installed version exactly in both that venv and the development one. AC 7 is answered by this pull request rather than locally, since it asserts CI runs on 3.14 with no edit to the workflow.

## Screenshot(s) / video(s)
None

_Closes #34_

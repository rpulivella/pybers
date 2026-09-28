[PYB-39](https://github.com/rpulivella/pybers/issues/39)

GitHub numbers issues and pull requests from one counter, so `#37` in this repository named two things. Tickets now read `PYB-39` and pull requests `PR #38`, in prose and in what the tools print, and both tools accept either form back as input so a reference can be pasted where it came from.

## Detail your changes
- [x] No regressions / known issues found
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Preconditions / setup for testing
None

## Breaking Changes

**CI / automation / build**: `ticket.py` and `pr.py` change what they print. Any script reading their output for a bare `#N` needs updating, and none exists in this repository.

**Object model (public dataclass fields)**: None

**Archive round-trip**: None

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- NA I added or updated pytest tests covering the change
- NA Round-trip / golden-file tests pass for any archive-layer change

Both are NA because `scripts/` is repository tooling pytest does not cover. Every parser form was exercised against live data instead: `PYB-39`, `39`, `#39` and the issue URL all resolve, `PR #38`, `#38`, `38` and the pull request URL all resolve, and a bad argument still produces a usage message rather than a traceback.

Three carve-outs are deliberate rather than missed. The 17 existing changelog entries keep their `[#N]`, so the file records when the convention changed. Eighteen iWork archive identifiers such as `#903915` stay, since the findings depend on the number. Two `CLAUDE.md` references point at its own numbered bug list, where `#2` and `#3` are real tickets about something else entirely.

## Screenshot(s) / video(s)
None

_Closes #39_

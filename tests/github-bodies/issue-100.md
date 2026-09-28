[PYB-94](https://github.com/rpulivella/pybers/issues/94)

`/golden-confirm` opens a temporary copy of a golden in running Numbers, checks each cell its `tests/golden/<golden>.expected.toml` names, and writes a report with sharp screenshots, a Quick Look rendering per sheet, and the archives a Numbers-saved copy changed. Everything needing Accessibility, Screen Recording or control of Numbers runs in `pybersdev-golden-confirm.app`, a background helper built from `scripts/golden-confirm-helper/` and signed with the developer's own certificate, so Terminal holds none of those permissions. All 23 goldens pass, and `damage-check` shows a truncated file and a damaged archive each failing the run and saying why.

## Detail your changes
- [x] Known issues remain (described below)
- [x] No change to the object-model shape (Cell/Table/Sheet/Document fields)
- [x] No change to the on-disk archive round-trip contract

## Known issues
- A locked Mac stops a run, because Numbers will not open a document there: measured 2026-09-17, the open times out. `caffeinate` now keeps an idle lock from interrupting a batch

## Preconditions / setup for testing
1. A Mac with Numbers and an Apple Development signing identity (Xcode, Settings, Accounts).
2. `python3 scripts/golden-confirm.py helper-build`
3. Grant `~/Library/Application Support/pybers/pybersdev-golden-confirm.app` Accessibility and Screen & System Audio Recording in System Settings, Privacy & Security. The first run asks to control Numbers.
4. A run launches Numbers hidden and captures through ScreenCaptureKit, so switching desktops or entering a full-screen app during it is fine. `python3 scripts/golden-confirm.py permissions`, then `python3 scripts/golden-confirm.py run 11-text-written-and-retyped.numbers`, and open the report it names.

## Breaking Changes
**CI / automation / build**: None. Nothing in the preflight or CI runs the tool.
**Object model (public dataclass fields)**: None
**Archive round-trip**: None. Nine round-trip assertions now go through `listPackageDifferences`, which is stricter: it compares every message and each archive's object references, where `readArchiveBodies` compared only the first message body.

## Checklist (before requesting review)
- [x] I performed a self-review
- [x] The CHANGELOG.md Unreleased entry is in this PR (`/changelog-add`)
- [x] I added or updated pytest tests covering the change
- [x] Round-trip / golden-file tests pass for any archive-layer change

The tool has no pytest coverage by design (AC 10): it needs a logged-in Mac with Numbers, and was exercised against all 23 goldens and `damage-check`.

## Screenshot(s) / video(s)
None. Reports and screenshots stay in the git-ignored `workarea/golden-confirm/PYB-94/`.

_Closes #94_

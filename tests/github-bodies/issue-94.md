As a pybers developer I want one command that opens a golden in real running Numbers, checks it and captures what Numbers shows, so that confirming a golden takes a glance at a report rather than a manual session in Numbers.

## Acceptance criteria

1. A `/golden-confirm` skill, backed by a script under `scripts/`, takes a golden in `tests/golden/`, reads the cells to check from that golden's expected-values file (AC 12), and reports every check below as passed, failed, or left for a human.
2. The golden is byte-identical after a run, because only a temporary copy is ever opened, and that copy is removed afterward.
3. A document Numbers refuses, warns about or crashes on while opening fails the run and says which of the three happened, naming the alert when there is one, shown against a truncated file and against a zip holding one damaged archive.
4. For each cell asked about, the report gives the value, the formula and the format kind Numbers reads, each compared with what was expected in a form that reads the same on every developer's Mac whatever its region settings. The formatted value is reported beside them and never compared.
5. The report carries screenshots taken from running Numbers:
   1. each sheet as Numbers displays it, with the cells asked about in view,
   1. the Data Format section of the inspector's Cell tab for each cell asked about, which is where controls, merges and format details show.
6. The report carries the Quick Look rendering of the golden, so what pybers stored sits beside what Numbers recalculated.
7. A copy Numbers saves from the opened document is read by pybers and compared with the golden, and every archive that differs is listed.
8. The Data Format settings the inspector shows as text, such as a slider's minimum, maximum and increment, are compared with what was expected. The report names each check that neither Numbers' scripting nor the inspector could answer, such as whether a range is merged, and points at the screenshot that answers it.
9. A run without a logged-in session, or whose helper (AC 11) lacks Accessibility, Screen Recording or permission to control Numbers, stops before opening anything and says what is missing and where to grant it.
10. Nothing in the preflight, CI or the test suite runs it, and nothing under `src/` or `tests/` imports it.
11. Accessibility and Screen Recording are held only by `pybersdev-golden-confirm.app`, a helper with no window, menu or Dock icon, so Terminal needs neither permission. A run that gets no result back from the helper fails and says so.
12. Each golden's expected values live in a file beside it, `tests/golden/<golden>.expected.toml`, naming the cells to check and what each should show.
13. One command builds the helper from source in the repository, without an Xcode project, signs it with the developer's own Apple Development certificate, and installs it to `~/Library/Application Support/pybers/`. A rebuild keeps the permissions already granted.
14. A run whose installed helper was built from different source than the repository holds stops before opening anything and says to rebuild.
15. The helper performs only its own fixed operations, opening a temporary copy of a golden, reading cells and inspector settings, capturing the Numbers window and saving a copy, and never runs a script or command it is given.
16. Only the Numbers window is ever captured, never the whole screen.
17. Screenshots are lossless PNG at the display's own resolution, so graphical detail stays sharp: each sheet as the whole Numbers window, and each cell asked about as the inspector's Data Format section cropped from that window wherever the window sits and whatever its size. A run that would take more than 40 stops before opening anything and says so.
18. The report and its screenshots land in `workarea/golden-confirm/PYB-<N>/<golden>/`, one folder per ticket whose number comes from the branch name, which git ignores and the developer can open. A run on a branch with no ticket number stops and says so.
19. `/pr-merge` removes the merged ticket's `workarea/golden-confirm/PYB-<N>/` folder and leaves every other ticket's folder in place.
20. A run leaves every document the developer already has open in Numbers untouched, closes its copy without saving, and quits Numbers afterward only when the run launched it. While Numbers holds a document with unsaved changes the run stops before opening anything and names each such document, since a damaged golden can crash Numbers.
21. When Numbers runs in a language whose Cell tab the helper cannot find, the run stops before any check and says why.

## Constraints

- Numbers rewrites a document it opens, so only a copy may be opened. It is sandboxed and opens a file object rather than a path string. On macOS 26 the app is `Numbers Creator Studio.app`, so it is addressed by bundle id `com.apple.Numbers`.
- Its scripting dictionary reports no merge and no control settings, and `value` is a double for a number. The screenshots exist for exactly those gaps, and they need Screen Recording permission for the app running the tool.
- ~~Open decisions: how a cell's inspector is brought up and captured reliably, and where the expected values for each golden are kept.~~ Decided 2026-09-17 and folded into AC 5.ii, AC 8 and AC 11 to 21.
- Measured 2026-09-17, macOS 26 and Numbers 15.3.1. A program Terminal starts directly runs under Terminal's permissions, and only an app started with `open` holds its own, so the helper is an app with `LSBackgroundOnly` rather than a bare binary. A rebuild signed with the same certificate kept both grants; an ad-hoc signed rebuild is expected to lose them and was not measured.
- Measured 2026-09-17: a truncated file makes `open` return `missing value` with no alert, and a zip holding a damaged `Tile.iwa` crashed Numbers, which AppleScript reports as error -609.

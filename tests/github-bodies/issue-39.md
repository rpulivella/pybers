As a maintainer I want a ticket and a pull request to be written differently everywhere, so that a reference names one thing rather than two.

1. Every ticket reference in prose reads `PYB-34`, and every pull request reference reads `PR #38` with both parts. A `#` followed by digits survives only where it names something that is not a ticket: an iWork archive identifier quoted from the format, or a numbered item within the document that carries it.
2. `README.md` and `CLAUDE.md` each declare the key on one line, so a clone carries the convention without depending on this developer's machine.
3. `scripts/ticket.py` prints `PYB-34` and `scripts/pr.py` prints `PR #38`, so the form a developer copies is the correct one and the convention does not rely on being remembered.
4. New `CHANGELOG.md` entries read `- [PYB-34] <title>`, since a changelog is published prose rather than a commit message. Existing entries are left exactly as written, so the file records when the convention changed rather than reading as though it always held.
5. Commit subjects keep the bare number, `[34] feat: ...`, unchanged and stated as deliberate rather than left to look like an oversight.
6. The pull request template opens with `[PYB-34](url)` on the first line and carries `_Closes #34_` in italic as its last, with no heading repeating the title and no `Ticket:` label.
7. `Closes #34` still closes its ticket on merge, verified on a real pull request rather than assumed.
8. The skills that write prose, `/ticket-create`, `/ticket-edit`, `/pr-draft`, `/pr-review-code`, `/pr-merge` and `/changelog-add`, instruct the new forms and none of them demonstrates a bare `#`.
9. `scripts/ticket.py` accepts `PYB-39`, `39` and `#39` for any ticket argument, and `scripts/pr.py` accepts `PR #38`, `#38` and `38` for any pull request argument, so a reference the tools print can be pasted straight back into them. Every skill that takes such an argument lists the accepted forms.

## SPEC

- **GitHub numbers issues and pull requests from one counter**, which is why this is ambiguity rather than untidiness: in this repository PYB-34 and PYB-36 are tickets while 35, 37 and 38 are pull requests, interleaved.
- **`Closes #34` is the one form that cannot change.** GitHub parses that keyword and no other, so AC 1 has exactly one exception and AC 7 exists because the failure is silent: the pull request merges, the ticket simply stays open.
- Measured 2026-09-03 and corrected the same day: of 50 `#N` in documentation only **9 are tickets**. Eighteen are iWork archive identifiers such as `#903915`, whose findings depend on the number, and two are `CLAUDE.md` pointing at its own numbered bug list, where `#2` and `#3` are real tickets about something else. A mechanical sweep damages all twenty. The 60 commit subjects and the 17 existing changelog entries are out of scope by decision.

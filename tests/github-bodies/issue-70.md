As a developer recording why a ticket closed, or a reviewer recording what a review caught, I want to leave a comment from the command line so that the reason outlives the session that produced it.

## Acceptance criteria

1. A comment can be added to a ticket and to a pull request, and the tool prints where it landed.
   1. A body carrying backticks, fenced code, list items and tables arrives with those constructs intact, and any reflowing of prose is reported rather than silent, so a comment can quote code and a command without being mangled.
2. Every comment is readable two ways: rendered for a person, and byte for byte for revising. That is the same split `show` and `export-as-source` already make for a body, and it exists for the same reason.
3. A comment can be edited in place, so a correction does not cost the original and a review that runs twice replaces its own summary rather than stacking a second one.
4. A comment can be deleted, and the tool says before doing it that GitHub keeps no copy.
5. What was written is read back and checked against what was sent, the way `edit` already does, so a write that did not land fails loudly rather than passing.

## Constraints

- A pull request IS an issue to GitHub's REST API, so one set of endpoints serves both and `pr.py` already imports `ticket`. Two implementations of this would drift.
- The same author's tooling in another repository carries the adding and deleting halves, and `scripts/ticket.py` here was adapted from it, so those two are a port. Editing is not there and is the one part with no prior art to lift.
- GitHub scopes a comment id to the repository rather than to the issue, so reaching one needs no ticket or pull request number, and taking one would imply a check that is not happening.
- An agentic review posting its own summary is what PYB-12 has yet to settle, so this builds the command and leaves who calls it alone.

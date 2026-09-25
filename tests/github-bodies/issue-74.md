As a developer posting a body to GitHub I want the indentation that identifies a block to survive the trip so that code I pasted arrives as code rather than as a sentence.

## Acceptance criteria

1. An indented code block in a drafted body reaches GitHub as a code block.
   1. Its indentation is intact, so markdown still reads it as code.
   1. Its lines are not joined onto one line.
2. Every change made to the leading or trailing whitespace of a line is reported, the way a joined paragraph already is.
   1. Removing the two-space hard-break marker from a single-line paragraph is reported rather than counted as no change at all.
3. What survives today still survives: a fenced block, a nested list item, a wrapped list continuation, a table and a block quote come through exactly as they do now.

## Constraints

- `unwrapParagraphs` matches `blockOpener` and `listOpener` against the already-stripped line, so any construct markdown identifies by its indentation is invisible by the time the question is asked. Both patterns are anchored to a start that has been discarded.
- Measured identically on `develop` and on the PYB-72 branch, so the behavior predates both: `"Before:\n\n    def f():\n        return 1\n\nAfter.\n"` comes back as `"Before:\n\ndef f(): return 1\n\nAfter.\n"`, reported as one paragraph joined.

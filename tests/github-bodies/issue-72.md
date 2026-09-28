As a developer posting a body to GitHub I want every change the tool makes to my text to be reported so that nothing I wrote is rewritten without my knowing.

## Acceptance criteria

1. A body whose line endings are changed on the way to GitHub says so, the way a body whose paragraphs are joined already does.
   1. A carriage return inside a fenced code block, a table or a list item reaches GitHub as written, since a newline is meaningful in all three and the author may have meant it.
2. A body needing no change at all still reports nothing, so the report stays a signal rather than noise on every call.

## Constraints

- `unwrapParagraphs` splits with `str.splitlines`, which treats `\r\n` and a bare `\r` as line breaks and rejoins with `\n`. The count it returns tracks only the paragraphs it JOINED, so the line-ending change is invisible to it and to every caller.
- This reaches `create`, `edit` and the four comment writers alike, because all of them post through `readBodyFile`.

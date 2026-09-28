As a developer arriving at this repository I want the README to describe what the library actually does so that I can tell what it is for without reading the CHANGELOG or the design record.

1. The repository map names `numbersfile/`. The map still says `archive/`, which has not been a directory since #2 renamed it, so anyone following the map looks for something that does not exist.
2. "What works today" covers what has shipped since it was written: reaching a sheet or a table by name or by position, iterating every cell a document stores, merging and unmerging a block, and an edit marking the cells it changed so that Numbers recalculates what depends on them.
3. The worked example uses the library as it now reads rather than the index arithmetic that was the only spelling available when the example was written.
4. The evidence the README claims matches the evidence that exists. It cites one numeric edit confirmed in Numbers, and there are four confirmed goldens.
5. The contributing notes name every gate a contributor is expected to run before opening a pull request, rather than the prose one alone.
6. Every path, module, command and file the README names exists, checked rather than assumed.

## SPEC

- **Do not add a CI badge.** #5 owns it, and a badge for a workflow that does not exist yet renders as a broken image on the front page of a public repository.
- **Do not write this by copying from `CLAUDE.md`.** That file is a design record for people who have already decided to work here, and it opens with the origin story and the architectural decisions. The README is read by someone deciding whether to care.

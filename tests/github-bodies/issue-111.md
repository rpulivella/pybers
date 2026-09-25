As a developer confirming a golden I want the tool to check a table's size, its merges and its empty cells so that QA is left only what needs eyes.

## Acceptance criteria

1. An expected-values file can state a table's row and column count, and a run reports it passed or failed against what Numbers shows, as it does a cell's value.
2. An expected-values file can state the ranges a table merges, and a run reports each passed or failed against Numbers.
3. An expected-values file can state that a cell is empty, and a run reports it passed or failed.
4. With Numbers not running, both the permissions check and a run say that Numbers is not running, rather than pointing at the Automation settings.
5. A check the tool cannot make stays in the report's QA list: hidden rows and columns, an error's glyph, and what Quick Look shows.

## Constraints

- Through AppleScript a covered cell reports its anchor's name, measured 2026-09-18 while building `56-structure-base`, which is how a merge can be read.
- Status -600 from `AEDeterminePermissionToAutomateTarget` means Numbers is not running, which the helper currently reports as a missing Automation grant.

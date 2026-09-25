As a Python developer I want a formula holding Apple's list node to read as text so that a document using it can be inspected and edited rather than refused.

## Acceptance criteria

1. A formula holding node type 25 renders as the text Numbers displays for it.
2. That text parses back to the same node array, so the round trip holds for this node as it does for every other one the renderer handles.
3. What node type 25 carries is recorded in the findings, with the measurement behind it rather than the schema's own name for it.

## Constraints

- `TSCE.ASTNodeArrayArchive.ASTNodeType` names 25 `LIST_NODE`. It appears zero times across the 46 fixtures and 438 times in one real document, so its meaning has to be measured rather than read off the schema, which permits far more than Numbers writes.
- The renderer refuses it today and the nodes round-trip untouched, so this is a gap in what can be displayed rather than a loss of anything stored.

As a Python developer I want the formula pybers reports for a cell to be the formula that produced that cell's value so that a script reading a document is never working from a formula the document does not contain.

## Acceptance criteria

1. Every reference in every formula resolves to a position inside the table it names. A column at or before the first column is reported as a defect rather than returned as an address.
2. The formula rendered for a cell agrees with the value that cell caches, across a document Numbers wrote and has recalculated.
3. Where several cells name one pooled formula, each resolves it against its own position, and every one of them lands inside its table.

## Constraints

- Measured 2026-09-09 against a real document outside the corpus: 66 formulas resolve to a column at or before zero, and `AK3` renders as `=SUM(D3,J3,P3,V3,AB3,AH3)`, which sums to 8.26 where that cell caches 89.91.
- Whether the fault is the slot the formula key is read from or the host the offsets resolve against is not established, and the two produce the same symptom.

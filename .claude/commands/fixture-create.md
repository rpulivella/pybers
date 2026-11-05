---
description: Design and make a fixture or measurement that labels its own contents, across row 1 with row 2 saying exactly what was input, by the helper's recipe or by hand in Numbers.
argument-hint: <what the document must show, such as the formula text of a decimal literal under en_IT>
---

# /fixture-create

Design a document Numbers makes, then make it. A fixture is an origin and a measurement is
derived from one. `tests/measurements/README.md` says which is which and how each is made,
and `tools/local/README.md` lists the steps a recipe can take. This skill holds the layout
those files do not give.

## The layout

- **Across, not down.** One entry per column in row 1, so the whole document reads on one
  screen. Stop at about column L, and split a longer set into a second table or a second
  document rather than run past it.
- **Row 2 says exactly what was input**, in text, so a reader knows what each cell holds
  without opening the recipe:
  - a typed value or formula as typed: `input as 1234.5`, `input as =DOLLAR(1234.5,2)`.
  - every choice after it as the inspector names it: `input as 1234.5, Currency, Euro (€)`,
    `input as 1234.5, Number, Decimals 2, Thousands Separator`.
  - a change made by hand as the menu names it: `Language & Region set to German (Germany)`.

  Never a summary such as `formula, DOLLAR`, which says what the cell is for rather than
  what is in it.
- **The column after the last entry is labeled `empty`** and left so in row 1, which marks
  where the entries stop and measures an untouched cell.
- **Each entry varies one thing** from its neighbors, so a difference in the file names its
  cause.

## Steps

1. **Read what the ticket needs measured**, and list the entries, each with its row 2 label,
   before writing anything. Show the list to the user.
2. **Choose the name**: the next number after the highest in `tests/fixtures/` and
   `tests/measurements/`, then a letter for each document derived from the same origin,
   such as `95-region-base`, `95b-region-de-de`.
3. **Make it by recipe** where every step is one the helper can take: write
   `<name>.recipe.toml` beside the measurements, preview it with
   `.venv/bin/python3 -m tools.local.golden_confirm measure <name> --preview`, then run it.
   Open Numbers first if the helper reports it is not running.
4. **Hand the rest to the user** where a step needs Numbers' interface and the helper has no
   action for it: copy the origin into `workarea/` under the new name, open it in Numbers,
   and give the user the menu path and the one change to make. Move it into
   `tests/measurements/` once the user has saved it.
5. **Read it back** with `.venv/bin/python3 -m pybers show <document> "Table 1"` and check
   that every row 1 entry holds what its row 2 label says.
6. **Record it** in the README beside it, with its origin and what it established, and in
   the findings once it is measured.

## Hard rules

- Numbers makes every fixture and measurement. pybers never writes one, and a document
  pybers wrote is a golden.
- Derive each measurement from its origin directly, never from a sibling derived from the
  same origin.
- Never write into `tests/fixtures/` or `tests/measurements/` except to add the new
  document and its recipe.

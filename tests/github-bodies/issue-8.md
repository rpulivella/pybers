As a Python developer I want a cell to report its formatting so that I can read how a
document looks, not only what it says.

1. A cell resolves the style archives it references, and `Cell.style` reflects them.
2. Two cells that reference one style archive receive the identical `Style`, the same
   object rather than an equal one.
3. No caller can mutate a `Style` reached from a cell. The frozen contract holds on the
   READ path, not only when writing.
4. Which trailing reference slot on a cell record a given flag bit gates is decoded, and
   each bit that is established is recorded in `tests/fixtures/findings-01-values.md`
   naming the fixture that establishes it.
5. A cell carrying no style of its own is distinguishable from one whose style is present
   and entirely default.
6. A flag bit that is not established is carried through unread rather than guessed, and
   nothing synthesizes a bitmask.

## SPEC

Extracted from #1, where it was AC 7, once the fixtures showed it needs work #1 does not
contain. Filed as Concept because the blocker is open research rather than a decision, and
because the wrong way to close it is cheap and looks right.

- **The blocker.** `findings-01-values.md` records that the bytes 6-7 bitmask decides which
  trailing `uint32` references a cell record carries, and then states plainly: "**The
  individual flag bits are not decoded**, which bit implies which field is unknown, and
  guessing would be worse than saying so." Until that is done, nothing can say which
  reference on a cell is its style.
- **It is not one slot.** `findings-06-styles.md` shows the STYLE data list is
  heterogeneous and a single cell may reference two kinds at once: horizontal alignment is
  a paragraph property and vertical alignment is a cell property, so `refs=(6,1,5,1)` is a
  `TST.CellStyleArchive` and a `TSWP.ParagraphStyleArchive` together.
- **Sharing is the format's own behavior, not an implementation slip.** `34-shape` resolves
  twenty-one shapes to twelve styles, one archive backing seven drawables. A decoder that
  hands the same mutable object to every user of an archive turns one edit into a silent
  restyle of six unrelated objects, which is why AC 2 and AC 3 are about identity rather
  than about values.

Resolution through the named-style variation chain, and writing styles back, are out of
this ticket.

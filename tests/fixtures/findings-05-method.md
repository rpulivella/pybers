# Method

How these findings were produced, and the mistakes that produced them slowly.

Part of [FINDINGS.md](FINDINGS.md), which indexes every topic.

---

## Method notes, learned the hard way

- **Diff archive *contents* by identifier, not just presence.** An archive modified in place
  keeps its identifier, so a set difference over identifiers misses it entirely. This is how
  the all-caps hunt went wrong the first time.
- **Derive fixtures from one baseline by Save As.** Numbers renumbers object identifiers
  throughout a newly created document, so two files made from the template share almost no
  internal names. Save-As lineage keeps 36 of 37 members stable and is what makes a diff
  readable.
- **`TSD.DrawableSelectionArchive` (3061) and `TST.SelectionArchive` (6030) are noise** —
  they reflect what was selected when the file was saved. Filter them.
- **File size is dominated by the preview JPEGs** Numbers regenerates on each save. Not a
  content signal.

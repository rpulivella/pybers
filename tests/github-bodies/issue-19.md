As a developer revising a pull request I want its body back byte for byte so that an edit
changes the part I meant and leaves everything else exactly as it was.

1. `pr.py export-as-source <N> --body` prints the body as stored, nothing rendered,
   nothing wrapped, in the form that goes straight back to `edit`.
   1.a `--title` prints the title alone, without the `#<N>` prefix that `find` adds and
   without wrapping, so a title reused verbatim survives the trip.
2. Exporting a body and passing it straight back to `edit` leaves the pull request
   unchanged, which is the round trip that proves the export is faithful.
3. Every skill that revises a pull request body fetches it through this command rather
   than reconstructing it, and says so in its own steps.
4. `scripts/README.md` lists the command in the `pr.py` table, drawing the same
   read-for-editing against read-for-reading distinction the `ticket.py` table draws.
5. The command sits in the read-only permission grants, alongside
   `ticket.py export-as-source`.

## SPEC

- **`edit` replaces the whole body and GitHub offers no conflict detection.** A revision
  drafted from memory or from an earlier copy silently discards whatever changed in
  between, with no error and no conflict marker. `ticket.py` solved this with
  `export-as-source` and `/ticket-edit` documents the hazard at length. `pr.py` carries the
  same hazard and none of the remedy, which was hit for real on 2026-09-01 while revising
  the body of pull request 15.
- **The reader already exists.** `pr.py` defines `readPullRequestBody(token, number)` and
  uses it only to verify that an edit landed. This surfaces what is already there rather
  than adding a new call.
- **There is no `show` counterpart to add.** `ticket.py` offers a pair, `show` for reading
  and `export-as-source` for editing. `find` already prints the rendered summary for a pull
  request, so only the byte-exact half is missing.
- **This is new work rather than a restoration.** Checked on 2026-09-01: strikeglass's
  `pr.py` carries the identical five subcommands with no export, and its `ticket.py` has no
  `export-as-source` either. That command is a pybers invention, so the asymmetry here is
  pybers having solved the problem in one tool and not yet the other. Worth offering
  upstream once it exists.

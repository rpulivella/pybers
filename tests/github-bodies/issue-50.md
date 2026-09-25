As a developer opening a pull request I want the body checked against its template mechanically so that a description cannot quietly grow sections nobody sanctioned.

1. Opening or editing a pull request whose body carries a heading the template does not have is refused, and the message names the offending heading.
2. A body longer than twice the template's word count, counted with HTML comments removed from both, is refused, and the message reports both counts.
3. A body missing a heading the template carries is refused, because the template asks for `None` under a heading rather than for the heading to go.
4. Every check runs wherever a body is written, so none can be skipped by reaching for a different command.
5. `--dry-run` reports what the checks would say and opens or edits nothing.
6. Headings appear in the template's order, so every pull request reads back the same way.
7. A line that is nothing but bold text counts as a heading, so a section cannot be invented in a shape a `##` scan does not see.
8. A checkbox whose label the template does not carry is refused, while one that was ticked or removed is not, since the state belongs to the author and the label to the template.

## SPEC

- **The template is the authority in both directions for headings and in one direction for checkboxes.** `.github/pull_request_template.md` defines the sanctioned headings, and a body may neither add nor drop one: the template asks for `None` under a heading it does not need. Checkboxes are the opposite, since `/pr-draft` instructs an author to delete the ones that do not apply, so a removed checkbox is correct and a reworded label is not.
- **Both rules exist today and neither is mechanical.** `/pr-draft` states the word ceiling and forbids new sections, and both are left to whoever is writing. The section rule was broken on PR #46, which is what this ticket answers. `/pr-review-code` already records the principle: a recurring violation earns a lint rule rather than a longer rubric.
- **The same author's strikeglass repository already runs these checks** in its own preflight, and this is a port rather than an invention. Two of them are not obvious and were learned there the hard way: a line that is entirely bold reads as a section heading while being invisible to a `##` scan, which is how a pull request there grew four sections the template never had; and a word count has to strip HTML comments first, since a template made largely of instructions is otherwise counted as prose.
- `scripts/pr.py` is the only sanctioned path a body travels and already reads a body back to verify a write, so it is where a body-shaped check belongs rather than in the repository-wide preflight, which never sees one.

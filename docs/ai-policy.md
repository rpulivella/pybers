# AI use policy

Using an AI tool to write code, tests or prose for pybers is permitted. This repository is itself built partly by agents, so a rule against it would be dishonest. This project in fact began as much from a desire to push agentic coding forward as from a need to solve real problems with Python and Numbers. We are glad you are here. Please contribute.

## Ownership

You are answerable for every line in your pull request, whatever produced it. A maintainer reviews the contribution, never the tool behind it, and a defect is yours to explain and fix whether you typed it or an agent did. This includes anything in that pull request be it code, tooling, imagery, prose, comments, workflows, anything. You also answer for every ticket and comment you post, however it was produced.

## Disclosure

Nothing here asks you to say which parts a tool wrote. If you want to describe how you used an agent, the pull request body is the place for it. Keep it out of the code, the docs and the commit messages, which rules out a `Co-Authored-By` trailer, since it clutters the commit history.

## Agents must follow house rules

An agent working in this repository follows `CLAUDE.md` and the skills under `.claude/commands/`, exactly as specified. Together they set the naming, the commit format, the tests a change earns and the writing standards the prose gate enforces. A contribution that ignores them is refused, whatever produced it. Resubmitting work already closed as slop, or repeatedly ignoring this policy, such as using an AI tool to spam tickets or tests, is misconduct under the [code of conduct](../CODE_OF_CONDUCT.md).

## Unguided contributions

Check your pull request against this list before opening it. Any one of these makes it unguided:

- a change you cannot explain when a maintainer asks about it
- a description generated from the diff rather than written from what you set out to do
- a test you never ran
- a file rewritten wholesale to fix one line
- a claim about the Numbers format with no fixture or measurement behind it
- a pull request that departs from the template or omits part of it

## Resolution

A maintainer closes an unguided pull request naming the reason. It is the contributor's responsibility to perform the rework, not the maintainer's. You are welcome to open a new pull request once the reason no longer applies.

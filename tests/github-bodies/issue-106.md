As a contributor using an AI tool I want to know what this project requires of me so that I can use that tool freely and still submit work a maintainer will read.

## Acceptance criteria

1. `docs/ai-policy.md` exists and states in its opening sentence that using an AI tool to write code, tests or prose for this project is permitted.
2. The policy states that the contributor is answerable for every line they submit, whatever produced it, and that a maintainer reviews the contribution rather than the tool behind it.
3. The policy requires no attribution of which parts a tool produced, and says so plainly, so that nobody invents a disclosure ritual this project never wanted.
4. The policy names what an unguided contribution looks like, in concrete terms a contributor can check against their own pull request before opening it: a change the author cannot explain, a description generated from the diff, a test the author never ran, a file rewritten wholesale to fix one line.
5. The policy states that an agent working in this repository follows `CLAUDE.md` and the skills under `.claude/`, and that a contribution ignoring them is refused whatever produced it.
6. The policy states the consequence of an unguided contribution, which is closure with that reason given, rather than a maintainer reworking it into shape.
7. The policy is at most four hundred words, since a contributor reads it once, immediately before opening a pull request.
8. `README.md` and `CONTRIBUTING.md` each link the policy in one sentence, and neither restates its terms.

## Constraints

1. Home Assistant publishes the closest model for tone and length, at https://developers.home-assistant.io/docs/ai_policy/ . Its terms belong to that project, so it is read for shape rather than adapted.
2. This repository is itself built with an agent under `CLAUDE.md`, so any rule forbidding AI-written code would be false the day it was published.

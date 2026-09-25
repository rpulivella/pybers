As a maintainer I want the contribution model decided and `develop` protected before this repository becomes public so that the first outside pull request arrives at a repository that already knows what to do with it.

## Acceptance criteria

1. `CONTRIBUTING.md` states which model this project runs, either a pull request from anyone with every change reviewed by a maintainer, or write access held by collaborators with an outside contribution arriving from a fork.
2. `CONTRIBUTING.md` states what separates a collaborator from a maintainer, or states that nothing does and that the project uses one term.
3. `develop` carries branch protection that refuses a direct push, requires a pull request, and requires the `preflight` and `readiness` checks to pass.
4. Branch protection states whether a review approval is required, and `CONTRIBUTING.md` says the same thing, so a contributor learns the rule before GitHub enforces it.
5. The rules that hold for `develop` are recorded in `CONTRIBUTING.md` in one short section, since a repository setting is invisible to anyone reading the repository.
6. A pull request opened by an account outside the project runs both checks, and the readiness comment is posted, which needs its workflow permissions confirmed for a fork.

## Constraints

1. Branch protection is configurable only once the repository is public, so the protection half of this ticket is blocked until that day while the writing half is not.
2. A workflow triggered by a pull request from a fork runs with a read-only token, so the posting half of the readiness report needs proving against a fork rather than assuming the behavior seen on a branch.

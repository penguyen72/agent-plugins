---
name: create-pr
description: Create concise GitHub pull requests with Conventional Commit titles. Use when the user asks to summarize a branch, push it when needed, or open a PR with observed testing and optional related issues.
---

# Create a concise GitHub pull request

Create a pull request only after the required approvals. If any prerequisite or command fails, stop without creating a PR and provide the concise actionable command output.

## 1. Preflight

Verify the repository, GitHub CLI, authentication, remotes, and current branch before proposing a mutation:

```bash
git rev-parse --show-toplevel
gh --version
gh auth status
git remote -v
git branch --show-current
```

Confirm that a GitHub remote is configured and that the current-branch command returns a branch name. Stop on missing Git, `gh`, authentication, remote, or branch errors. Retain the actionable command output.

## 2. Choose base

Use an explicitly supplied base branch when one is provided. Otherwise, read the GitHub default branch:

```bash
gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'
```

Stop if the base branch cannot be determined.

## 3. Protect the default branch

If the current head branch equals the chosen base branch, stop and offer a concise feature-branch name. Obtain approval before creating it with `git switch -c <feature-branch>`.

## 4. Inspect

When network access is restricted, do not fetch remote state without approval. Inspect the branch with:

```bash
git log <base>..HEAD --oneline
git diff --stat <base>...HEAD
git diff <base>...HEAD
```

Use the observed commits and diff to describe the entire pull request.

## 5. Draft title

Use the same Conventional Commit types as `create-commit`: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, and `revert`.

Format the title as `<type>[(optional-scope)][!]: <imperative subject>`. Choose the narrowest accurate type. Use a lowercase imperative subject without a period; prefer 50 characters and enforce a 72-character maximum. Do not use emojis or vague filler such as "updates," "changes," or "various fixes." Keep issue references in a commit footer or pull request body rather than the title. Describe the complete pull request rather than copying an arbitrary commit title.

## 6. Draft body

Use one to three `## Summary` bullets and an honest `## Testing` list. Include `## Related issues` only when a reliable issue reference exists; otherwise omit that section. When no test ran, write `Not run (reason)`.

Do not invent tests or results.

Use this approved PR body template when a reliable issue exists:

```markdown
## Summary

- <observed change>

## Testing

- <observed command and result, or Not run (reason)>

## Related issues

- <reliable issue reference>
```

When no reliable issue exists, remove the `## Related issues` section from the completed body.

## 7. Review

Before any mutation, display the chosen base, current head, exact title, and complete body. Ask for approval to continue; do not infer it from an earlier approval.

## 8. Push

Obtain explicit user approval before every push, whether the branch already has an upstream or needs one created. If the head branch has no upstream, obtain separate approval before:

```bash
git push -u origin <head>
```

Stop if the push fails and retain the actionable command output.

Never force-push.

Never amend, reset, rebase, force-push, discard work, or bypass hooks.

Never rewrite history, even if separately requested.

## 9. Create

Obtain approval immediately before creating the PR:

```bash
gh pr create --base <base> --head <head> --title <title> --body-file <temporary-file>
```

Write the reviewed body to a temporary file, run the command, then remove only that temporary body file. Report the observed PR URL. Stop on PR errors and retain the actionable command output.

## 10. Failures

Stop on missing Git, `gh`, authentication, remote, base, branch, push, or PR errors. Do not create a pull request after a failure; retain the actionable command output so the user can resolve it.

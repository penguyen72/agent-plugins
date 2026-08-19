---
name: create-commit
description: Create concise Conventional Commits from repository changes. Use when the user asks to inspect, group, stage, or commit changes with clear atomic messages and approval before each commit.
---

# Create atomic Conventional Commits

Create one or more reviewed atomic commits only after explicit user approval. If a prerequisite fails, stop and provide the concise actionable reason.

## 1. Inspect

Run these commands before proposing any mutation:

```bash
git rev-parse --show-toplevel
git status --short
git diff
git diff --cached
git log -5 --oneline
```

Stop if the directory is outside Git or if no staged or unstaged changes exist.

## 2. Protect existing work

Distinguish staged files from unstaged files. Never unstage, rewrite, or discard existing work. Flag `.env` files, credentials, private keys, large generated files, and unexpected binaries before staging. Every path already in the index must appear in the exact approved atomic proposal; otherwise stop before committing and ask for a new proposal and approval.

## 3. Group

Keep one coherent unit together. Split unrelated behavior, tests, documentation, or infrastructure into separate atomic proposals. Explain any staged-set conflict and preserve existing staged work.

## 4. Format

Use only these approved types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, and `revert`.

Use `<type>[(optional-scope)][!]: <imperative subject>`. Choose the narrowest accurate type. Add a useful scope only when it clarifies the affected component. Use a lowercase imperative subject with no period; prefer 50 characters and enforce a 72-character maximum. Do not use emojis or vague filler such as "updates," "changes," or "various fixes." Keep issue references in a commit footer or pull request body rather than the title. Add an explanatory body only when necessary. For a genuine breaking change, use `!` and a `BREAKING CHANGE:` footer.

Approved examples:

```text
feat(auth): add session timeout handling
fix(api): preserve pagination cursor
docs: clarify local installation
refactor(parser): separate validation logic
```

A breaking-change example:

```text
feat(api)!: remove legacy authentication

BREAKING CHANGE: clients must use token authentication.
```

## 5. Propose

Before mutation, show every proposed commit's exact message and explicit file list. Explain why each file belongs in its proposal and wait for approval.

## 6. Approve and execute

Obtain approval for each proposed commit. For each approved proposal, stage only its explicit paths with `git add -- <paths>`, run `git diff --cached --check`, and re-check the cached diff and file set immediately before commit. Confirm every path already in the index is in the exact approved atomic proposal; otherwise stop and ask for a new proposal and approval. Only then run the normal `git commit` command so configured hooks execute. Do not use a hook-bypass option.

## 7. Verify

After the commit command succeeds, read its observed hash with `git rev-parse --short HEAD` and show the remaining `git status --short`. Never claim success from an unobserved result.

## 8. Failures

Retain actionable hook and Git error text, then stop after a failure. Never amend, reset, rebase, force or force-push, discard work, rewrite history, or bypass hooks—even if separately requested. These actions are permanently out of scope for this plugin.

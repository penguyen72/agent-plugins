# Agent Plugins Repository Design

## Purpose

Create a GitHub-hosted marketplace repository for personal plugins that can be installed by Codex and Claude Code. The repository must support cross-platform plugins as the default while allowing a plugin to target only one platform when its capabilities require that.

The first plugin, `git-craft`, standardizes concise Conventional Commit messages and GitHub pull requests. It proposes atomic commits and clear pull request content, then obtains approval before making changes to the repository or GitHub.

## Repository and Remote

- Local path: `/Users/peynguyen/Repositories/agent-plugins`
- GitHub remote: `git@github.com:penguyen72/agent-plugins.git`
- Default branch: `main`
- Repository name: `agent-plugins`
- Marketplace name: `penguyen72-plugins`
- License: MIT

## Repository Architecture

```text
agent-plugins/
├── README.md
├── LICENSE
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── git-craft/
│       ├── .codex-plugin/
│       │   └── plugin.json
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           ├── create-commit/
│           │   └── SKILL.md
│           └── create-pr/
│               └── SKILL.md
└── docs/
    └── superpowers/
        └── specs/
```

The two root marketplace catalogs expose the same repository through each platform's native installation mechanism. Each plugin is a self-contained unit under `plugins/`.

Cross-platform plugins contain both platform manifests and appear in both catalogs. Codex-only plugins contain only `.codex-plugin/plugin.json` and appear only in `.agents/plugins/marketplace.json`. Claude-only plugins contain only `.claude-plugin/plugin.json` and appear only in `.claude-plugin/marketplace.json`.

Shared behavior belongs under the plugin's `skills/` directory. Platform-specific files may be added within a plugin when needed, but a plugin must not depend on files outside its own directory. This keeps installed copies complete when a platform caches a plugin independently from the marketplace repository.

The root README will list available plugins, supported platforms, capabilities, and copy-paste installation commands.

## Initial Plugin Components

The `git-craft` plugin contains two focused skills:

- `create-commit`: inspect local changes, propose atomic Conventional Commits, and create approved commits.
- `create-pr`: inspect a branch relative to its base, propose a concise pull request, push when necessary with approval, and create the approved pull request.

The skills share formatting principles but remain independently understandable and invocable. Each `SKILL.md` contains all instructions required for its workflow. Small shared rules may be repeated to avoid runtime dependencies between skill directories.

Installed skills use the plugin namespace: `$git-craft:create-commit` and `$git-craft:create-pr` in Codex, and `/git-craft:create-commit` and `/git-craft:create-pr` in Claude Code.

## Commit Workflow

The `create-commit` skill follows this sequence:

1. Verify that the current directory is a Git repository.
2. Inspect repository status, staged and unstaged diffs, and recent commit history.
3. Identify sensitive, generated, or otherwise suspicious files and flag them before staging.
4. Determine whether the changes form one coherent commit or multiple atomic commits.
5. Propose each commit's explicit file set and complete message.
6. Ask for approval before staging and creating each commit.
7. Stage only the approved explicit paths.
8. Run the normal commit command without bypassing hooks.
9. Report the resulting commit hash or the actionable failure.

The skill must preserve existing staged work. When the staged set conflicts with the proposed atomic grouping, it explains the conflict and asks the user how to proceed. It must not amend commits, reset changes, force an operation, or skip hooks unless the user explicitly requests that separate action.

## Pull Request Workflow

The `create-pr` skill follows this sequence:

1. Verify that the current directory is a Git repository and that `gh` is installed and authenticated.
2. Determine the head branch, remote, and base branch.
3. Inspect commits and the complete base-branch diff.
4. Generate a Conventional Commit-style title and compact pull request body.
5. Show the base branch, head branch, proposed title, and proposed body.
6. If the branch lacks an upstream, ask before pushing it.
7. Ask again before running `gh pr create`.
8. Return the created pull request URL.

When the current branch is the default branch, the skill stops and offers to create a feature branch with approval. A failed prerequisite push prevents pull request creation.

## Commit and Pull Request Standard

Allowed Conventional Commit types are:

```text
feat, fix, docs, refactor, test, chore, build, ci, perf, revert
```

Commit subjects and pull request titles use this format:

```text
<type>[(optional-scope)][!]: <imperative subject>
```

Formatting rules:

- Choose the narrowest accurate type.
- Use a scope only when it clarifies the affected component.
- Write the subject in lowercase imperative form.
- Do not end the subject with punctuation.
- Prefer at most 50 characters and enforce a hard limit of 72 characters.
- Do not use emojis or vague filler such as "updates," "changes," or "various fixes."
- Keep issue references in a commit footer or pull request body rather than the title.
- Add a commit body only when the reason or important context is not clear from the subject.
- Represent genuine compatibility breaks with `!` and a `BREAKING CHANGE:` footer.

Examples:

```text
feat(auth): add session timeout handling
fix(api): preserve pagination cursor
docs: clarify local installation
refactor(parser): separate validation logic
```

## Pull Request Body

The pull request body uses this structure:

```markdown
## Summary

- What changed
- Why it changed, when that context is useful

## Testing

- Verification actually performed

## Related issues

- Closes #123
```

The summary normally contains one to three bullets. The related-issues section is omitted when no issue is available. The testing section includes only verification that was actually observed. If no testing was performed, it says so concisely and gives the reason when known.

## Safety and Error Handling

The skills stop and provide a concrete next action when:

- The current directory is not a Git repository.
- There are no relevant changes to commit.
- `gh` is unavailable or unauthenticated.
- No suitable GitHub remote exists.
- The base branch cannot be determined reliably.
- The current branch is the default branch.
- A Git hook, commit, push, or pull request command fails.

Neither skill may discard or rewrite existing work. They must not bypass failing hooks, fabricate test results, create a pull request after a failed push, or claim success without observing the successful command result. Error reports should retain the actionable part of command output without overwhelming the user.

## Validation and Testing

Repository-level validation checks that:

- Both marketplace catalogs contain valid JSON.
- Plugin directory names, manifest names, and catalog names match.
- The Codex and Claude manifests for a cross-platform plugin use the same version.
- Every catalog source points to an existing, self-contained plugin.
- Every skill contains valid `SKILL.md` frontmatter.
- Claude Code's plugin validator passes.
- Codex's plugin validator passes.

Behavior is tested in temporary Git repositories. The representative cases are:

- One coherent change produces one proposed commit.
- Unrelated changes produce multiple proposed atomic commits.
- Existing staged files remain preserved.
- A breaking change uses `!` and a `BREAKING CHANGE:` footer.
- A repository with no changes stops without committing.
- A long or vague title is rewritten within the title limit.
- A pull request body includes only observed testing.
- Related issues appear only when supplied or reliably detected.
- Failed hooks, pushes, and authentication return actionable errors.

Automated tests must not push branches or create real pull requests. Any end-to-end test that mutates GitHub requires a separate, explicit user-approved test repository.

## Versioning and Distribution

Each plugin has its own semantic version. A cross-platform plugin keeps the same version in both manifests. Changes to behavior or packaging require the appropriate plugin version bump and catalog validation before publishing.

Users install the repository as a marketplace, then select individual plugins. The initial README will document these flows using `penguyen72/agent-plugins` as the GitHub marketplace source and `penguyen72-plugins` as the marketplace identifier.

## Success Criteria

The initial release is complete when:

- The repository exposes a valid marketplace to both Codex and Claude Code.
- `git-craft` installs on both platforms from the same GitHub repository.
- Both skills generate concise, valid Conventional Commit titles.
- Commit creation, branch push, and pull request creation require clear approval at their mutation boundaries.
- The plugin handles atomic grouping and common failure states without losing or rewriting user work.
- Structural validation and representative temporary-repository tests pass.

# Agent Plugins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a dual-platform `agent-plugins` marketplace whose first plugin creates concise, approved Conventional Commits and GitHub pull requests in Codex and Claude Code.

**Architecture:** Keep each plugin self-contained under `plugins/`. The `git-craft` plugin shares two portable `SKILL.md` workflows while exposing separate Codex and Claude manifests; root catalogs adapt that plugin to each platform's marketplace schema. A dependency-free Python validator checks the cross-platform invariants, while static contract tests and isolated Git repositories cover safety-critical workflow behavior.

**Tech Stack:** Markdown Agent Skills, JSON plugin manifests, Python 3 standard library, `unittest`, Git, GitHub CLI, Codex plugin CLI, Claude Code plugin CLI.

## Global Constraints

- Repository path: `/Users/peynguyen/Repositories/agent-plugins`.
- GitHub remote: `git@github.com:penguyen72/agent-plugins.git`.
- Default branch: `main`.
- Marketplace identifier: `penguyen72-plugins`.
- License: MIT.
- Initial plugin name and directory: `git-craft`.
- Initial plugin version: `0.1.0` in both platform manifests.
- Cross-platform plugins contain both manifests and appear in both catalogs.
- Platform-specific plugins contain only the relevant manifest and catalog entry.
- Plugins must not read resources outside their own plugin directory.
- Allowed commit types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`.
- Commit and pull request titles use the narrowest accurate type and lowercase imperative subjects, prefer 50 characters, never exceed 72 characters, and have no trailing punctuation; they contain no emojis, vague filler, or issue references, which belong in a commit footer or pull request body.
- Commit creation, branch push, feature-branch creation, and pull request creation require approval before mutation.
- Never amend, reset, rebase, force or force-push, discard work, rewrite history, or bypass hooks, even if separately requested; never fabricate tests or continue to pull request creation after a failed push.
- Automated acceptance tests must not push branches or create real pull requests.

---

## File Map

- `scripts/validate_repository.py`: validate catalogs, manifests, paths, versions, and skill frontmatter without third-party dependencies.
- `tests/test_validate_repository.py`: unit-test the validator with complete and deliberately broken temporary repository trees.
- `tests/test_skill_contracts.py`: assert the installed skill text contains the agreed workflow gates, formats, and safety rules.
- `.agents/plugins/marketplace.json`: Codex marketplace catalog.
- `.claude-plugin/marketplace.json`: Claude Code marketplace catalog.
- `plugins/git-craft/.codex-plugin/plugin.json`: Codex plugin metadata.
- `plugins/git-craft/.claude-plugin/plugin.json`: Claude Code plugin metadata.
- `plugins/git-craft/skills/create-commit/SKILL.md`: atomic commit workflow.
- `plugins/git-craft/skills/create-pr/SKILL.md`: pull request workflow.
- `README.md`: plugin inventory, installation, update, usage, and development commands.
- `LICENSE`: MIT license text.

### Task 1: Cross-platform repository validator

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/validate_repository.py`
- Create: `tests/__init__.py`
- Create: `tests/test_validate_repository.py`

**Interfaces:**
- Consumes: a repository root containing `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json`, and `plugins/`.
- Produces: `validate_repository(root: pathlib.Path) -> list[str]`, returning all human-readable validation errors; CLI exit code `0` on success and `1` on validation failure.

- [ ] **Step 1: Write failing tests for a valid dual-platform fixture**

Create `tests/test_validate_repository.py` with a `build_repo(root: Path)` helper that writes a minimal `git-craft` plugin, both catalogs, both manifests at version `0.1.0`, and two skills with `name` and `description` frontmatter. Add:

```python
class ValidateRepositoryTests(unittest.TestCase):
    def test_valid_cross_platform_repository_has_no_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            self.assertEqual(validate_repository(root), [])

    def test_rejects_manifest_name_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.codex-plugin/plugin.json"
            payload = json.loads(manifest.read_text())
            payload["name"] = "wrong-name"
            manifest.write_text(json.dumps(payload))
            self.assertIn(
                "Codex manifest name 'wrong-name' does not match directory 'git-craft'",
                validate_repository(root),
            )
```

- [ ] **Step 2: Run the tests and confirm the validator is missing**

Run:

```bash
python3 -m unittest tests.test_validate_repository -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'scripts.validate_repository'`.

- [ ] **Step 3: Implement JSON, source-path, manifest, and frontmatter validation**

Create `scripts/validate_repository.py` with these exact public signatures:

```text
load_object(path: Path, errors: list[str]) -> dict[str, object] | None
parse_skill_frontmatter(path: Path, errors: list[str]) -> dict[str, str] | None
resolve_plugin_source(root: Path, source: object, platform: str, errors: list[str]) -> Path | None
validate_repository(root: Path) -> list[str]
main(argv: Sequence[str] | None = None) -> int
```

Implement the following concrete checks:

- Both root catalog files exist and contain JSON objects.
- Both catalogs use `name: penguyen72-plugins` and contain a `plugins` array.
- Codex sources have `{"source": "local", "path": "./plugins/<name>"}`.
- Claude sources are strings matching `./plugins/<name>`.
- Resolved source paths stay beneath `root/plugins`; reject absolute paths and `..` traversal.
- Every entry resolves to an existing plugin directory and the matching platform manifest.
- Entry name, directory name, and manifest `name` are identical.
- Every manifest has non-empty `name`, `version`, and `description` strings, and each version matches strict semantic version syntax such as `0.1.0`.
- When both manifests exist, their `version` values are identical.
- Each direct child of `skills/` contains `SKILL.md` with frontmatter delimited by `---` and non-empty `name` and `description` values.
- Duplicate plugin names within either catalog are errors.
- The CLI prints `Repository validation passed.` on success; on failure it prints each error prefixed with `- ` to stderr.

Use only `argparse`, `json`, `pathlib`, `re`, `sys`, and standard-library typing. Do not add PyYAML for two scalar frontmatter fields.

- [ ] **Step 4: Add failure tests for all cross-platform invariants**

Add tests named:

```python
test_rejects_missing_catalog
test_rejects_duplicate_catalog_entry
test_rejects_source_outside_plugins
test_rejects_missing_platform_manifest
test_rejects_cross_platform_version_mismatch
test_rejects_invalid_semver
test_rejects_missing_skill_frontmatter_name
test_cli_returns_one_and_prints_each_error
```

Each test mutates one part of the fixture and asserts the exact error substring associated with that mutation.

- [ ] **Step 5: Run the validator test suite**

Run:

```bash
python3 -m unittest tests.test_validate_repository -v
```

Expected: all validator tests report `ok` and the command ends with `OK`.

- [ ] **Step 6: Commit the validator**

```bash
git add scripts/__init__.py scripts/validate_repository.py tests/__init__.py tests/test_validate_repository.py
git commit -m "test: add plugin repository validator"
```

### Task 2: Marketplace catalogs and plugin manifests

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `plugins/git-craft/.codex-plugin/plugin.json`
- Create: `plugins/git-craft/.claude-plugin/plugin.json`
- Create: `README.md`
- Create: `LICENSE`
- Modify: `tests/test_validate_repository.py`

**Interfaces:**
- Consumes: `validate_repository(root)` from Task 1.
- Produces: marketplace `penguyen72-plugins` and installable plugin selector `git-craft@penguyen72-plugins` for both platforms.

- [ ] **Step 1: Add a failing integration test against the real repository**

Add:

```python
def test_checked_in_repository_is_valid(self):
    root = Path(__file__).resolve().parents[1]
    self.assertEqual(validate_repository(root), [])
```

- [ ] **Step 2: Run the integration test and confirm missing catalogs fail**

Run:

```bash
python3 -m unittest tests.test_validate_repository.ValidateRepositoryTests.test_checked_in_repository_is_valid -v
```

Expected: `FAIL` listing both missing marketplace catalog files.

- [ ] **Step 3: Create the Codex marketplace catalog**

Write `.agents/plugins/marketplace.json`:

```json
{
  "name": "penguyen72-plugins",
  "interface": {
    "displayName": "Pey Nguyen Plugins"
  },
  "plugins": [
    {
      "name": "git-craft",
      "source": {
        "source": "local",
        "path": "./plugins/git-craft"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

- [ ] **Step 4: Create the Claude marketplace catalog**

Write `.claude-plugin/marketplace.json`:

```json
{
  "name": "penguyen72-plugins",
  "owner": {
    "name": "Pey Nguyen"
  },
  "plugins": [
    {
      "name": "git-craft",
      "source": "./plugins/git-craft",
      "description": "Create concise Conventional Commits and GitHub pull requests",
      "category": "Development"
    }
  ]
}
```

- [ ] **Step 5: Create both plugin manifests**

Write `plugins/git-craft/.codex-plugin/plugin.json` as:

```json
{
  "name": "git-craft",
  "version": "0.1.0",
  "description": "Create concise Conventional Commits and GitHub pull requests",
  "author": {
    "name": "Pey Nguyen",
    "url": "https://github.com/penguyen72"
  },
  "repository": "https://github.com/penguyen72/agent-plugins",
  "license": "MIT",
  "keywords": ["git", "github", "commits", "pull-requests"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Git Craft",
    "shortDescription": "Create concise commits and pull requests.",
    "longDescription": "Propose atomic Conventional Commits and concise GitHub pull requests with approval before changes.",
    "developerName": "Pey Nguyen",
    "category": "Developer Tools",
    "capabilities": ["Read", "Write"],
    "defaultPrompt": [
      "Create concise commits for these changes.",
      "Create a pull request for this branch."
    ]
  }
}
```

Write `plugins/git-craft/.claude-plugin/plugin.json` as:

```json
{
  "name": "git-craft",
  "version": "0.1.0",
  "description": "Create concise Conventional Commits and GitHub pull requests",
  "author": {
    "name": "Pey Nguyen"
  },
  "repository": "https://github.com/penguyen72/agent-plugins",
  "license": "MIT",
  "keywords": ["git", "github", "commits", "pull-requests"],
  "skills": "./skills/"
}
```

- [ ] **Step 6: Create repository documentation and license**

Write `README.md` with:

- A one-paragraph purpose statement.
- A plugin table containing `git-craft`, both supported platforms, and the two skill names.
- Codex install commands:

```bash
codex plugin marketplace add penguyen72/agent-plugins --ref main
codex plugin add git-craft@penguyen72-plugins
```

- Claude Code session commands:

```text
/plugin marketplace add penguyen72/agent-plugins
/plugin install git-craft@penguyen72-plugins
/reload-plugins
```

- Usage examples using `$git-craft:create-commit` and `$git-craft:create-pr` for Codex and `/git-craft:create-commit` and `/git-craft:create-pr` for Claude Code.
- Development commands for the Python tests, repository validator, Codex validator, and Claude validator.
- A security note that plugins may run Git and GitHub commands and should be reviewed before installation.

Write the standard MIT license text to `LICENSE` with `Copyright (c) 2026 Pey Nguyen`.

- [ ] **Step 7: Run the checked-in repository validator**

Run:

```bash
python3 scripts/validate_repository.py .
python3 -m unittest tests.test_validate_repository -v
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
```

Expected: repository validation passes, all tests pass, and both JSON commands exit `0`.

- [ ] **Step 8: Commit marketplace packaging**

```bash
git add .agents .claude-plugin plugins/git-craft/.codex-plugin plugins/git-craft/.claude-plugin README.md LICENSE tests/test_validate_repository.py
git commit -m "feat: add cross-platform plugin marketplace"
```

### Task 3: Atomic Conventional Commit skill

**Files:**
- Create: `plugins/git-craft/skills/create-commit/SKILL.md`
- Create: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: Git status, staged and unstaged diffs, recent commit history, and explicit user approval.
- Produces: one or more approved atomic commits and their observed commit hashes; otherwise a concise actionable stop reason.

- [ ] **Step 1: Write the failing commit-skill contract test**

Create `tests/test_skill_contracts.py` with a helper that loads the frontmatter and Markdown body. Assert that `create-commit/SKILL.md`:

```python
self.assertEqual(frontmatter["name"], "create-commit")
self.assertIn("commit", frontmatter["description"].lower())
self.assertIn("git status --short", body)
self.assertIn("git diff --cached", body)
self.assertIn("explicit paths", body)
self.assertIn("approval", body.lower())
self.assertIn("BREAKING CHANGE:", body)
self.assertIn("72", body)
self.assertNotIn("git add .", body)
self.assertIn("Never amend, reset, force, discard work, or bypass hooks", body)
```

- [ ] **Step 2: Run the contract test and confirm the skill is missing**

Run:

```bash
python3 -m unittest tests.test_skill_contracts -v
```

Expected: `ERROR` with `FileNotFoundError` for `skills/create-commit/SKILL.md`.

- [ ] **Step 3: Write the `create-commit` skill**

Use this frontmatter:

```yaml
---
name: create-commit
description: Create concise Conventional Commits from repository changes. Use when the user asks to inspect, group, stage, or commit changes with clear atomic messages and approval before each commit.
---
```

The body must define these ordered sections and concrete instructions:

1. **Inspect:** run `git rev-parse --show-toplevel`, `git status --short`, `git diff`, `git diff --cached`, and `git log -5 --oneline`; stop if outside Git or if no changes exist.
2. **Protect existing work:** distinguish staged from unstaged files; never unstage, rewrite, or discard existing work; flag `.env`, credentials, private keys, large generated files, and unexpected binaries.
3. **Group:** keep one coherent unit together; split unrelated behavior, tests, documentation, or infrastructure into atomic proposals; explain any staged-set conflict.
4. **Format:** enforce the approved type list, optional useful scope, lowercase imperative subject, no period, 50-character preference, 72-character maximum, optional explanatory body, and breaking-change syntax.
5. **Propose:** show each exact message and file list before mutation.
6. **Approve and execute:** obtain approval for each proposed commit, stage only explicit paths with `git add -- <paths>`, run `git diff --cached --check`, then re-check the cached diff and file set immediately before commit. Every path already in the index must appear in the exact approved atomic proposal; otherwise stop and ask for a new proposal and approval. Only then run the normal `git commit` command so configured hooks execute.
7. **Verify:** read the resulting hash with `git rev-parse --short HEAD` and show remaining `git status --short`; never claim success from an unobserved result.
8. **Failures:** retain hook and Git error text, stop after failure, and never amend, reset, force, discard work, or skip hooks; these actions are out of scope for this plugin.

Include all four approved examples and `feat(api)!: remove legacy authentication` with a `BREAKING CHANGE:` footer.

- [ ] **Step 4: Run contract and skill validation**

Run:

```bash
python3 -m unittest tests.test_skill_contracts -v
python3 /Users/peynguyen/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/git-craft/skills/create-commit
```

Expected: contract tests pass and quick validation prints `Skill is valid!`.

- [ ] **Step 5: Commit the commit workflow**

```bash
git add plugins/git-craft/skills/create-commit/SKILL.md tests/test_skill_contracts.py
git commit -m "feat(git-craft): add commit workflow"
```

### Task 4: Concise GitHub pull request skill

**Files:**
- Create: `plugins/git-craft/skills/create-pr/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: current Git branch, GitHub remote, base-branch diff, commits, observed verification, optional issue references, and explicit approval.
- Produces: an approved GitHub pull request URL; otherwise a concise actionable stop reason without creating a PR.

- [ ] **Step 1: Add the failing pull-request contract test**

Assert that `create-pr/SKILL.md`:

```python
self.assertEqual(frontmatter["name"], "create-pr")
self.assertIn("pull request", frontmatter["description"].lower())
self.assertIn("gh auth status", body)
self.assertIn("## Summary", body)
self.assertIn("## Testing", body)
self.assertIn("## Related issues", body)
self.assertIn("gh pr create", body)
self.assertIn("approval", body.lower())
self.assertIn("72", body)
self.assertIn("Never force-push", body)
self.assertIn("Do not invent tests or results", body)
```

- [ ] **Step 2: Run the contract test and confirm the PR skill is missing**

Run:

```bash
python3 -m unittest tests.test_skill_contracts -v
```

Expected: the commit-skill test passes and the PR-skill test errors with `FileNotFoundError`.

- [ ] **Step 3: Write the `create-pr` skill**

Use this frontmatter:

```yaml
---
name: create-pr
description: Create concise GitHub pull requests with Conventional Commit titles. Use when the user asks to summarize a branch, push it when needed, or open a PR with observed testing and optional related issues.
---
```

The body must define these ordered sections and concrete instructions:

1. **Preflight:** verify Git with `git rev-parse --show-toplevel`, GitHub CLI with `gh --version`, authentication with `gh auth status`, remotes with `git remote -v`, and current branch with `git branch --show-current`.
2. **Choose base:** prefer an explicitly supplied base; otherwise read the GitHub default branch with `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`; stop if it cannot be determined.
3. **Protect the default branch:** if head equals base, stop and offer a concise feature-branch name; obtain approval before `git switch -c`.
4. **Inspect:** fetch no remote state without approval when network access is restricted; inspect `git log <base>..HEAD --oneline`, `git diff --stat <base>...HEAD`, and `git diff <base>...HEAD`.
5. **Draft title:** use the same Conventional Commit types and title constraints as `create-commit`, describing the complete PR rather than copying an arbitrary commit.
6. **Draft body:** use one to three `## Summary` bullets, an honest `## Testing` list, and optional `## Related issues`; omit the related section when no reliable issue exists and state `Not run (reason)` when no test ran.
7. **Review:** display base, head, exact title, and complete body before mutation.
8. **Push:** when no upstream exists, obtain separate approval before `git push -u origin <head>`; stop if the push fails. State `Never force-push` as a standalone safety rule.
9. **Create:** obtain approval immediately before `gh pr create --base <base> --head <head> --title <title> --body-file <temporary-file>`; remove only the temporary body file after the command; report the observed URL.
10. **Failures:** stop on missing Git, `gh`, authentication, remote, base, branch, push, or PR errors and retain the actionable command output.

Include the exact approved PR body template in the skill.

- [ ] **Step 4: Run contract and skill validation**

Run:

```bash
python3 -m unittest tests.test_skill_contracts -v
python3 /Users/peynguyen/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/git-craft/skills/create-pr
```

Expected: all contract tests pass and quick validation prints `Skill is valid!` for `create-pr`.

- [ ] **Step 5: Commit the pull request workflow**

```bash
git add plugins/git-craft/skills/create-pr/SKILL.md tests/test_skill_contracts.py
git commit -m "feat(git-craft): add pull request workflow"
```

### Task 5: Distribution validation and isolated acceptance checks

**Files:**
- Modify: `README.md`
- Create: `docs/testing/git-craft-acceptance.md`

**Interfaces:**
- Consumes: the complete repository from Tasks 1–4 and the two platform CLIs.
- Produces: recorded local validation evidence, installation instructions verified against current CLI syntax, and a release-ready `main` branch.

- [ ] **Step 1: Run all static and platform validators**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py .
python3 /Users/peynguyen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/git-craft
claude plugin validate ./plugins/git-craft --strict
git diff --check
```

Expected: all unit tests pass; repository, Codex, and Claude validators pass; `git diff --check` prints nothing.

- [ ] **Step 2: Verify current installation syntax without changing installed marketplaces**

Run:

```bash
codex plugin marketplace add --help
codex plugin add --help
claude plugin marketplace add --help
claude plugin install --help
```

Compare the help output to README commands. Modify only command spelling or flags proven stale by the installed CLI output.

- [ ] **Step 3: Create an isolated commit acceptance repository**

Create a uniquely named temporary directory:

```bash
mktemp -d /private/tmp/git-craft-acceptance.XXXXXX
```

Copy the returned absolute path into a task-specific `ACCEPTANCE_DIR` variable, then run:

```bash
git -C "$ACCEPTANCE_DIR" init -b main
git -C "$ACCEPTANCE_DIR" config user.name "Plugin Test"
git -C "$ACCEPTANCE_DIR" config user.email "plugin-test@example.com"
```

Create two unrelated tracked changes in that temporary repository using normal file-editing tools: one application file and one documentation file. From `ACCEPTANCE_DIR`, start a fresh Claude Code session with the local plugin:

```bash
claude --plugin-dir /Users/peynguyen/Repositories/agent-plugins/.worktrees/git-craft-plugin/plugins/git-craft
```

Invoke `/git-craft:create-commit`. Confirm it proposes two atomic commits, preserves any pre-staged file, shows explicit file lists, and pauses before mutation. Approve the commits because the repository is disposable; record the observed hashes and remaining clean status.

- [ ] **Step 4: Exercise non-mutating failure cases**

In disposable temporary repositories, verify and record:

- No changes produces a clear stop.
- A deliberately failing pre-commit hook is reported and not bypassed.
- A subject longer than 72 characters is rewritten.
- A breaking API fixture uses `!` and a `BREAKING CHANGE:` footer.
- A repository on `main` causes `create-pr` to offer a feature branch and pause before creating it.
- A repository without a GitHub remote stops before push or PR creation.
- A draft with no executed test says `Not run` and never claims tests passed.

Do not configure a working remote, push, or approve `gh pr create` during these acceptance checks.

- [ ] **Step 5: Record acceptance evidence**

Write `docs/testing/git-craft-acceptance.md` with:

- Date and tested plugin version `0.1.0`.
- Validator commands and exit status.
- A table containing every scenario from Steps 3–4, expected behavior, observed behavior, and pass/fail.
- A statement that no remote push or real pull request was performed.
- Any exact CLI limitation encountered; update the skill and rerun its affected check before marking that row passed.

- [ ] **Step 6: Re-run the full verification suite after acceptance-driven edits**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py .
python3 /Users/peynguyen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/git-craft
claude plugin validate ./plugins/git-craft --strict
git diff --check
git status --short
```

Expected: every validator passes, `git diff --check` is empty, and `git status --short` shows only the acceptance document or deliberate acceptance-driven edits.

- [ ] **Step 7: Commit acceptance evidence**

```bash
git add README.md docs/testing/git-craft-acceptance.md plugins/git-craft tests
git commit -m "test(git-craft): verify plugin workflows"
```

- [ ] **Step 8: Review the completed branch before publishing**

Run:

```bash
git status --short --branch
git log --oneline --decorate --max-count=8
git log --stat --oneline --max-count=8
git remote -v
```

Expected: clean `feat/git-craft-plugin`, focused Conventional Commit history, all intended repository files in the log, and `origin` set to `git@github.com:penguyen72/agent-plugins.git`.

- [ ] **Step 9: Hand the clean feature branch back to the controller**

Report the final commit list and validation evidence without pushing or changing installed marketplaces. After the whole-branch review, the controller must use `superpowers:finishing-a-development-branch` to present merge and publication options. Approval to merge or push does not imply approval to install the plugin into either local client.

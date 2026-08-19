# Git Craft acceptance evidence

Date: 2026-08-18
Tested plugin version: `0.1.0`

## Static and platform validation

| Command | Exit status | Observed result |
| --- | ---: | --- |
| `python3 -m unittest discover -s tests -v` | 0 | 18 tests passed. |
| `python3 scripts/validate_repository.py .` | 0 | `Repository validation passed.` |
| `uv run --with pyyaml python /Users/peynguyen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/git-craft` | 0 | `Plugin validation passed` in an isolated uv-provided PyYAML environment. |
| `claude plugin validate ./plugins/git-craft --strict` | 0 | Claude Code reported `Validation passed`. |
| `git diff --check` | 0 | No output. |

## Installation syntax

The installed CLIs were queried without adding or installing any marketplace:

| Command | Exit status | Result |
| --- | ---: | --- |
| `codex plugin marketplace add --help` | 0 | Supports `SOURCE` and `--ref`; the README command remains current. |
| `codex plugin add --help` | 0 | Supports `PLUGIN@MARKETPLACE`; the README command remains current. |
| `claude plugin marketplace add --help` | 0 | Supports a marketplace source; the README's Claude Code session command remains current. |
| `claude plugin install --help` | 0 | Supports `plugin@marketplace`; the README command remains current. |

The Codex help commands also emitted a non-fatal PATH-alias warning caused by this sandbox (`Operation not permitted`); their help text and exit statuses were still available. No README installation command was proven stale, so no README change was made.

## Isolated acceptance checks

The commit fixture was created at a unique disposable path under `/private/tmp` and initialized on `main` with the test identity `Plugin Test <plugin-test@example.com>`. It has an initial fixture commit, then two unrelated tracked changes: a pre-staged application change in `app.py` and an unstaged documentation change in `README.md`.

The local plugin probe was run from that fixture without any mutation permission:

```bash
claude --plugin-dir /Users/peynguyen/Repositories/agent-plugins/.worktrees/git-craft-plugin/plugins/git-craft --permission-mode plan --no-session-persistence -p "/git-craft:create-commit Inspect the repository, propose atomic commits with explicit file lists, and pause for my approval. Do not stage, commit, or otherwise mutate anything."
```

It stopped before loading the skill with exactly:

```text
Not logged in · Please run /login
```

`claude auth status` independently reported `{"loggedIn":false,"authMethod":"none","apiProvider":"firstParty"}`. This prevented every interactive skill scenario below from being run. None is marked passed on the basis of static contracts or inferred behavior.

| Scenario | Expected behavior | Observed behavior | Status |
| --- | --- | --- | --- |
| Unrelated application and documentation changes, with one file pre-staged | Propose two atomic commits with explicit file lists, preserve staged work, and pause before mutation; approved disposable commits would record hashes and clean status. | Fixture prepared as described, but Claude stopped at authentication before `/git-craft:create-commit` could run. No commits were approved or created. | Blocked — not run |
| No changes | Clearly stop without committing. | Not run: the local Claude session cannot authenticate, so the skill cannot be invoked in a fresh empty disposable repository. | Blocked — not run |
| Failing pre-commit hook | Report hook failure and do not bypass it. | Not run: authentication blocked invocation before a hook fixture could be exercised. | Blocked — not run |
| Subject longer than 72 characters | Rewrite to a compliant subject. | Not run: authentication blocked invocation before a proposal could be observed. | Blocked — not run |
| Breaking API fixture | Use `!` and a `BREAKING CHANGE:` footer. | Not run: authentication blocked invocation before a proposal could be observed. | Blocked — not run |
| `create-pr` from `main` | Offer a feature branch and pause before creating it. | Not run: authentication blocked invocation before the skill could inspect the disposable repository. | Blocked — not run |
| `create-pr` without a GitHub remote | Stop before push or PR creation. | Not run: authentication blocked invocation before the skill could inspect the disposable repository. | Blocked — not run |
| Draft with no executed test | Say `Not run` and do not claim tests passed. | Not run: authentication blocked invocation before a PR draft could be observed. | Blocked — not run |

No remote was configured in the acceptance fixture. No remote push, real pull request, marketplace addition, plugin installation, or history-rewriting operation was performed.

## Limitations

- Claude Code `2.1.229` is installed and validates the plugin, but no Claude authentication is available for a fresh local-plugin session. Interactive acceptance checks require a logged-in session and remain blocked.
- The bundled Codex validator passed with PyYAML supplied by the isolated `uv run --with pyyaml` environment; no installed environment was changed.

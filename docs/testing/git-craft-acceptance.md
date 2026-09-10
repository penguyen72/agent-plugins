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

After the user authenticated Claude Code, `claude auth status` succeeded outside the sandbox. The following bounded local-plugin print-mode probes were run from the fixture without mutation permission:

```bash
timeout 120s claude --plugin-dir /Users/peynguyen/Repositories/poopstack/.worktrees/git-craft-plugin/plugins/git-craft --permission-mode plan --output-format json -p "/git-craft:create-commit Inspect the current repository. Propose atomic commits with exact file lists, preserve the existing staged file, and pause for my approval. Do not stage, commit, or otherwise mutate anything yet."
```

```bash
timeout 90s claude --plugin-dir /Users/peynguyen/Repositories/poopstack/.worktrees/git-craft-plugin/plugins/git-craft --permission-mode plan --no-session-persistence -p "/git-craft:create-commit Inspect current changes and give only the approval-gated atomic commit proposal. Preserve the already staged app.py. Do not make any mutation."
```

Neither print-mode probe produced usable stdout or stderr within its bounded wait. An interactive local-plugin session passed Claude's workspace-trust prompt but likewise produced no proposal within the bounded wait after receiving `/git-craft:create-commit`; it was interrupted without mutating the fixture. The fixture remained at its baseline commit with `app.py` pre-staged and `README.md` unstaged.

The controller's later non-plugin diagnostic eventually returned:

```text
READY
```

It incurred approximately $0.11 and revealed heavy SessionStart customization/hooks. This is an environment-performance limitation rather than evidence of a Git Craft skill defect. Per user acceptance on 2026-08-18, the interactive checks are deferred; no scenario is marked passed on the basis of static contracts or inferred behavior.

| Scenario | Expected behavior | Observed behavior | Status |
| --- | --- | --- | --- |
| Unrelated application and documentation changes, with one file pre-staged | Propose two atomic commits with explicit file lists, preserve staged work, and pause before mutation; approved disposable commits would record hashes and clean status. | Fixture prepared as described; post-auth print and interactive probes yielded no usable proposal before their bounded waits. No commits were approved or created. | Deferred — not run (user accepted 2026-08-18) |
| No changes | Clearly stop without committing. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |
| Failing pre-commit hook | Report hook failure and do not bypass it. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |
| Subject longer than 72 characters | Rewrite to a compliant subject. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |
| Breaking API fixture | Use `!` and a `BREAKING CHANGE:` footer. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |
| `create-pr` from `main` | Offer a feature branch and pause before creating it. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |
| `create-pr` without a GitHub remote | Stop before push or PR creation. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |
| Draft with no executed test | Say `Not run` and do not claim tests passed. | Deferred because the post-auth live session did not produce a usable proposal within bounded waits. | Deferred — not run (user accepted 2026-08-18) |

No remote was configured in the acceptance fixture. No remote push, real pull request, marketplace addition, plugin installation, or history-rewriting operation was performed.

## Limitations

- Claude Code authentication succeeded, but local-plugin print and interactive sessions did not return usable proposals within bounded waits. The user accepted all live acceptance checks as deferred on 2026-08-18; no skill behavior was changed for this environmental performance issue.
- The bundled Codex validator passed with PyYAML supplied by the isolated `uv run --with pyyaml` environment; no installed environment was changed.

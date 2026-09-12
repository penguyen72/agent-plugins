# Pey Nguyen Plugins

This repository is a dual-platform marketplace for small, focused developer plugins. Git Craft turns reviewed changes into concise Conventional Commits and clear GitHub pull requests. Comprehension Profile records approved evidence about technical explanations that clicked so later components can build a small, shared explanation profile.

| Plugin | Platforms | Skills |
| --- | --- | --- |
| `git-craft` | Codex, Claude Code | `create-commit`, `create-pr` |
| `comprehension-profile` | Codex, Claude Code | `capture-learning-pattern` |

## Install with Codex

```bash
codex plugin marketplace add penguyen72/poopstack --ref main
codex plugin add git-craft@penguyen72-plugins
codex plugin add comprehension-profile@penguyen72-plugins
```

Use the installed skills:

```text
$git-craft:create-commit
$git-craft:create-pr
$comprehension-profile:capture-learning-pattern
```

## Install with Claude Code

In a Claude Code session, run:

```text
/plugin marketplace add penguyen72/poopstack
/plugin install git-craft@penguyen72-plugins
/plugin install comprehension-profile@penguyen72-plugins
/reload-plugins
```

Use the installed skills:

```text
/git-craft:create-commit
/git-craft:create-pr
/comprehension-profile:capture-learning-pattern
```

## Comprehension Profile storage

Comprehension Profile stores approved learning observations locally in
`~/.comprehension-profile/observations.jsonl`. Set the
`COMPREHENSION_PROFILE_HOME` environment variable to a non-empty path to use a
different store root. The plugin does not transmit this data.

Manual capture creates evidence only; it never creates or updates `profile.md`.
Only the future profile refiner will be allowed to write that canonical profile.
Automatic learning-moment detection is not included yet and will arrive in a
separate implementation.

Invoke `capture-learning-pattern` after a technical explanation clearly clicks.
It previews one observation and its local store path, then requires approval
before appending. Capture does not turn the candidate into a profile rule; the
future refiner is the only profile writer.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py .
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/git-craft
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/comprehension-profile
claude plugin validate ./plugins/git-craft --strict
claude plugin validate ./plugins/comprehension-profile --strict
```

## Security

Plugins may run Git and GitHub commands. Review a plugin and its requested actions before installing or approving changes.

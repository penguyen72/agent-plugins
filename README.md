# Pey Nguyen Plugins

This repository is a dual-platform marketplace for small, focused developer plugins. Its first plugin, Git Craft, helps turn reviewed changes into concise Conventional Commits and clear GitHub pull requests, with approval before it makes changes.

| Plugin | Platforms | Skills |
| --- | --- | --- |
| `git-craft` | Codex, Claude Code | `create-commit`, `create-pr` |

## Install with Codex

```bash
codex plugin marketplace add penguyen72/agent-plugins --ref main
codex plugin add git-craft@penguyen72-plugins
```

Use the installed skills:

```text
$git-craft:create-commit
$git-craft:create-pr
```

## Install with Claude Code

In a Claude Code session, run:

```text
/plugin marketplace add penguyen72/agent-plugins
/plugin install git-craft@penguyen72-plugins
/reload-plugins
```

Use the installed skills:

```text
/git-craft:create-commit
/git-craft:create-pr
```

## Development

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py .
python3 ${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/git-craft
claude plugin validate ./plugins/git-craft --strict
```

## Security

Plugins may run Git and GitHub commands. Review a plugin and its requested actions before installing or approving changes.

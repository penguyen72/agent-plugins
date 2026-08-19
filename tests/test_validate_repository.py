import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from scripts.validate_repository import main, validate_repository


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_repo(root: Path) -> None:
    plugin = root / "plugins/git-craft"
    write_json(
        root / ".agents/plugins/marketplace.json",
        {
            "name": "penguyen72-plugins",
            "plugins": [
                {
                    "name": "git-craft",
                    "source": {"source": "local", "path": "./plugins/git-craft"},
                }
            ],
        },
    )
    write_json(
        root / ".claude-plugin/marketplace.json",
        {
            "name": "penguyen72-plugins",
            "plugins": [{"name": "git-craft", "source": "./plugins/git-craft"}],
        },
    )
    for platform in (".codex-plugin", ".claude-plugin"):
        write_json(
            plugin / platform / "plugin.json",
            {
                "name": "git-craft",
                "version": "0.1.0",
                "description": "Create Git commits and pull requests.",
            },
        )
    for skill in ("create-commit", "create-pr"):
        skill_file = plugin / "skills" / skill / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(
            "---\n"
            f"name: {skill}\n"
            f"description: {skill} workflow\n"
            "---\n"
            "Instructions.\n",
            encoding="utf-8",
        )


class ValidateRepositoryTests(unittest.TestCase):
    def test_checked_in_repository_is_valid(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(validate_repository(root), [])

    def test_readme_uses_portable_codex_validator_path(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        command = re.search(
            r'python3\s+"(?P<path>[^"]+)"\s+plugins/git-craft', readme
        )
        self.assertNotIn("/Users/", readme)
        self.assertIsNotNone(command)
        validator_path = command.group("path") if command else ""
        self.assertIn("${CODEX_HOME:-$HOME/.codex}", validator_path)
        self.assertTrue(
            validator_path.endswith(
                "/skills/.system/plugin-creator/scripts/validate_plugin.py"
            )
        )

    def test_valid_cross_platform_repository_has_no_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            self.assertEqual(validate_repository(root), [])

    def test_valid_codex_only_repository_has_no_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / "plugins/git-craft/.claude-plugin/plugin.json").unlink()
            catalog = root / ".claude-plugin/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(validate_repository(root), [])

    def test_valid_claude_only_repository_has_no_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / "plugins/git-craft/.codex-plugin/plugin.json").unlink()
            catalog = root / ".agents/plugins/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(validate_repository(root), [])

    def test_rejects_manifest_name_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.codex-plugin/plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["name"] = "wrong-name"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Codex manifest name 'wrong-name' does not match directory 'git-craft'",
                validate_repository(root),
            )

    def test_rejects_missing_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / ".agents/plugins/marketplace.json").unlink()
            self.assertIn(
                "Codex marketplace catalog is missing: .agents/plugins/marketplace.json",
                validate_repository(root),
            )

    def test_rejects_duplicate_catalog_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            catalog = root / ".claude-plugin/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"].append(payload["plugins"][0])
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Claude marketplace has duplicate plugin name 'git-craft'",
                validate_repository(root),
            )

    def test_rejects_source_outside_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            catalog = root / ".agents/plugins/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"][0]["source"]["path"] = "../outside"
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Codex plugin source '../outside' must stay beneath plugins/",
                validate_repository(root),
            )

    def test_rejects_missing_platform_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / "plugins/git-craft/.claude-plugin/plugin.json").unlink()
            self.assertIn(
                "Claude manifest is missing for plugin 'git-craft'",
                validate_repository(root),
            )

    def test_rejects_cross_platform_version_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.claude-plugin/plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["version"] = "0.2.0"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Plugin 'git-craft' has mismatched Codex and Claude versions",
                validate_repository(root),
            )

    def test_rejects_cross_platform_plugin_missing_from_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            catalog = root / ".claude-plugin/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Plugin 'git-craft' has a Claude manifest but is missing from the Claude marketplace catalog",
                validate_repository(root),
            )

    def test_rejects_codex_manifest_missing_from_codex_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / "plugins/git-craft/.claude-plugin/plugin.json").unlink()
            catalog = root / ".claude-plugin/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            catalog = root / ".agents/plugins/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Plugin 'git-craft' has a Codex manifest but is missing from the Codex marketplace catalog",
                validate_repository(root),
            )

    def test_rejects_claude_manifest_missing_from_claude_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / "plugins/git-craft/.codex-plugin/plugin.json").unlink()
            catalog = root / ".agents/plugins/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            catalog = root / ".claude-plugin/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Plugin 'git-craft' has a Claude manifest but is missing from the Claude marketplace catalog",
                validate_repository(root),
            )

    def test_rejects_manifestless_plugin_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / "plugins/no-manifest").mkdir()
            self.assertIn(
                "Plugin directory has no platform manifest: plugins/no-manifest",
                validate_repository(root),
            )

    def test_rejects_physical_plugin_directory_symlink_that_escapes_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            external_plugin = root / "external-plugin"
            external_plugin.mkdir()
            (root / "plugins/escaped").symlink_to(
                external_plugin, target_is_directory=True
            )

            errors = validate_repository(root)

            self.assertIn("Plugin directory escapes plugins/: plugins/escaped", errors)
            self.assertNotIn(str(external_plugin), "\n".join(errors))

    def test_rejects_manifest_symlink_that_escapes_plugin_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.codex-plugin/plugin.json"
            manifest.unlink()
            manifest.parent.rmdir()
            external_manifest_directory = root / "external-manifest"
            external_manifest_directory.mkdir()
            manifest.parent.symlink_to(external_manifest_directory, target_is_directory=True)

            errors = validate_repository(root)

            self.assertIn(
                "Plugin path escapes its directory: "
                "plugins/git-craft/.codex-plugin/plugin.json",
                errors,
            )
            self.assertNotIn(str(external_manifest_directory), "\n".join(errors))

    def test_rejects_version_mismatch_for_plugin_missing_from_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            catalog = root / ".claude-plugin/marketplace.json"
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["plugins"] = []
            catalog.write_text(json.dumps(payload), encoding="utf-8")
            manifest = root / "plugins/git-craft/.claude-plugin/plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["version"] = "0.2.0"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Plugin 'git-craft' has mismatched Codex and Claude versions",
                validate_repository(root),
            )

    def test_rejects_invalid_semver(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.codex-plugin/plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["version"] = "1.0"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Codex manifest version for plugin 'git-craft' is not valid semantic version: '1.0'",
                validate_repository(root),
            )

    def test_rejects_semver_prerelease_with_leading_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.codex-plugin/plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["version"] = "1.0.0-01"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(
                "Codex manifest version for plugin 'git-craft' is not valid semantic version: '1.0.0-01'",
                validate_repository(root),
            )

    def test_rejects_missing_skill_frontmatter_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            skill = root / "plugins/git-craft/skills/create-commit/SKILL.md"
            skill.write_text("---\ndescription: commit workflow\n---\n", encoding="utf-8")
            self.assertIn(
                "Skill frontmatter name is missing: plugins/git-craft/skills/create-commit/SKILL.md",
                validate_repository(root),
            )

    def test_reports_skill_errors_when_manifest_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            manifest = root / "plugins/git-craft/.codex-plugin/plugin.json"
            manifest.write_text("not json", encoding="utf-8")
            manifest = root / "plugins/git-craft/.claude-plugin/plugin.json"
            manifest.write_text("not json", encoding="utf-8")
            skill = root / "plugins/git-craft/skills/create-commit/SKILL.md"
            skill.write_text("---\ndescription: commit workflow\n---\n", encoding="utf-8")
            self.assertIn(
                "Skill frontmatter name is missing: plugins/git-craft/skills/create-commit/SKILL.md",
                validate_repository(root),
            )

    def test_cli_returns_one_and_prints_each_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_repo(root)
            (root / ".agents/plugins/marketplace.json").unlink()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(main([str(root)]), 1)
            self.assertIn(
                "- Codex marketplace catalog is missing: .agents/plugins/marketplace.json",
                stderr.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()

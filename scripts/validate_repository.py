"""Validate dual-platform plugin marketplace repositories."""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Sequence


MARKETPLACE_NAME = "penguyen72-plugins"
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
PLATFORMS = {
    "Codex": (Path(".agents/plugins/marketplace.json"), ".codex-plugin"),
    "Claude": (Path(".claude-plugin/marketplace.json"), ".claude-plugin"),
}


def display_path(root: Path, path: Path) -> str:
    """Return a stable repository-relative path for an error message."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def load_object(path: Path, errors: list[str]) -> dict[str, object] | None:
    """Load a JSON object, recording a human-readable error on failure."""
    if not path.is_file():
        errors.append(f"JSON file is missing: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"Invalid JSON in {path}: {error}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"JSON file must contain an object: {path}")
        return None
    return payload


def parse_skill_frontmatter(path: Path, errors: list[str]) -> dict[str, str] | None:
    """Read the two required scalar fields from a SKILL.md frontmatter block."""
    if not path.is_file():
        errors.append(f"Skill file is missing: {path}")
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        errors.append(f"Cannot read skill file {path}: {error}")
        return None
    if not lines or lines[0] != "---":
        errors.append(f"Skill frontmatter is missing opening delimiter: {path}")
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"Skill frontmatter is missing closing delimiter: {path}")
        return None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator and key in {"name", "description"}:
            fields[key] = value.strip()
    for field in ("name", "description"):
        if not fields.get(field):
            errors.append(f"Skill frontmatter {field} is missing: {path}")
    return fields


def resolve_plugin_source(root: Path, source: object, platform: str, errors: list[str]) -> Path | None:
    """Validate and resolve one platform-specific catalog source."""
    source_path: object
    if platform == "Codex":
        if not isinstance(source, dict) or source.get("source") != "local":
            errors.append("Codex plugin source must be an object with source 'local'")
            return None
        source_path = source.get("path")
    else:
        source_path = source
    if not isinstance(source_path, str):
        errors.append(f"{platform} plugin source must be a path string")
        return None

    candidate = Path(source_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{platform} plugin source '{source_path}' must stay beneath plugins/")
        return None
    expected = re.fullmatch(r"\./plugins/([^/]+)", source_path)
    if not expected:
        errors.append(f"{platform} plugin source '{source_path}' must match ./plugins/<name>")
        return None

    plugins_root = (root / "plugins").resolve()
    resolved = (root / candidate).resolve()
    if resolved.parent != plugins_root:
        errors.append(f"{platform} plugin source '{source_path}' must stay beneath plugins/")
        return None
    return resolved


def required_string(
    manifest: dict[str, object], field: str, platform: str, plugin_name: str, errors: list[str]
) -> str | None:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{platform} manifest {field} is missing for plugin '{plugin_name}'")
        return None
    return value


def validate_manifest(path: Path, platform: str, directory_name: str, errors: list[str]) -> dict[str, object] | None:
    manifest = load_object(path, errors)
    if manifest is None:
        return None
    name = required_string(manifest, "name", platform, directory_name, errors)
    version = required_string(manifest, "version", platform, directory_name, errors)
    required_string(manifest, "description", platform, directory_name, errors)
    if name is not None and name != directory_name:
        errors.append(f"{platform} manifest name '{name}' does not match directory '{directory_name}'")
    if version is not None and not SEMVER.fullmatch(version):
        errors.append(
            f"{platform} manifest version for plugin '{directory_name}' is not valid semantic version: '{version}'"
        )
    return manifest


def validate_repository(root: Path) -> list[str]:
    """Return every detected marketplace, manifest, and skill validation error."""
    root = root.resolve()
    errors: list[str] = []
    plugin_manifests: dict[Path, dict[str, dict[str, object]]] = {}
    plugin_sources: set[Path] = set()
    catalog_names: dict[str, set[str]] = {}

    for platform, (catalog_relative, manifest_directory) in PLATFORMS.items():
        catalog_path = root / catalog_relative
        if not catalog_path.is_file():
            errors.append(f"{platform} marketplace catalog is missing: {catalog_relative.as_posix()}")
            continue
        catalog = load_object(catalog_path, errors)
        if catalog is None:
            continue
        if catalog.get("name") != MARKETPLACE_NAME:
            errors.append(f"{platform} marketplace name must be '{MARKETPLACE_NAME}'")
        entries = catalog.get("plugins")
        if not isinstance(entries, list):
            errors.append(f"{platform} marketplace plugins must be an array")
            continue

        names: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"{platform} marketplace plugin entry must be an object")
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"{platform} marketplace plugin entry has a missing name")
                continue
            if name in names:
                errors.append(f"{platform} marketplace has duplicate plugin name '{name}'")
            names.add(name)
            source = resolve_plugin_source(root, entry.get("source"), platform, errors)
            if source is None:
                continue
            if source.name != name:
                errors.append(f"{platform} catalog name '{name}' does not match directory '{source.name}'")
            if not source.is_dir():
                errors.append(f"{platform} plugin directory is missing: plugins/{source.name}")
                continue
            plugin_sources.add(source)
            manifest_path = source / manifest_directory / "plugin.json"
            if not manifest_path.is_file():
                errors.append(f"{platform} manifest is missing for plugin '{source.name}'")
        catalog_names[platform] = names

    plugins_root = root / "plugins"
    if plugins_root.is_dir():
        plugin_sources.update(path.resolve() for path in plugins_root.iterdir() if path.is_dir())

    for source in sorted(plugin_sources):
        for platform, (_, manifest_directory) in PLATFORMS.items():
            manifest_path = source / manifest_directory / "plugin.json"
            if manifest_path.is_file():
                manifest = validate_manifest(manifest_path, platform, source.name, errors)
                if manifest is not None:
                    plugin_manifests.setdefault(source, {})[platform] = manifest

    for source, manifests in plugin_manifests.items():
        codex = manifests.get("Codex")
        claude = manifests.get("Claude")
        if codex is not None and claude is not None and codex.get("version") != claude.get("version"):
            errors.append(f"Plugin '{source.name}' has mismatched Codex and Claude versions")

    for source in sorted(plugin_sources):
        codex_manifest = source / ".codex-plugin/plugin.json"
        claude_manifest = source / ".claude-plugin/plugin.json"
        if codex_manifest.is_file() and claude_manifest.is_file():
            for platform in PLATFORMS:
                if source.name not in catalog_names.get(platform, set()):
                    errors.append(
                        f"Cross-platform plugin '{source.name}' is missing from {platform} marketplace catalog"
                    )

    for source in sorted(plugin_sources):
        skills = source / "skills"
        if skills.is_dir():
            for skill_directory in sorted(path for path in skills.iterdir() if path.is_dir()):
                skill_path = skill_directory / "SKILL.md"
                skill_errors: list[str] = []
                parse_skill_frontmatter(skill_path, skill_errors)
                for error in skill_errors:
                    errors.append(error.replace(str(skill_path), display_path(root, skill_path)))
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    """Run repository validation from the command line."""
    parser = argparse.ArgumentParser(description="Validate a plugin marketplace repository.")
    parser.add_argument("root", nargs="?", default=".", type=Path)
    arguments = parser.parse_args(argv)
    errors = validate_repository(arguments.root)
    if errors:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

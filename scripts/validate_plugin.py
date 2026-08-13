#!/usr/bin/env python3
"""Validate this repository's Codex Plugin manifest and component paths.

The public Codex CLI does not currently expose a plugin validation command, so
this repository keeps a deterministic compatibility check for the manifest
contract used by the bundled Codex plugin-creator validator.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
PLUGIN_KEYS = {
    "id",
    "name",
    "version",
    "description",
    "skills",
    "apps",
    "mcpServers",
    "interface",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
}
INTERFACE_KEYS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "brandColor",
    "composerIcon",
    "logo",
    "logoDark",
    "screenshots",
    "defaultPrompt",
    "default_prompt",
}


def parse_args() -> argparse.Namespace:
    """Parse the plugin root supplied on the command line."""
    parser = argparse.ArgumentParser(description="Validate the Codex Plugin package.")
    parser.add_argument("plugin_root", help="Repository or plugin root")
    return parser.parse_args()


def non_empty_string(value: Any) -> bool:
    """Return whether a value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def validate_https_url(value: Any, field: str, errors: list[str]) -> None:
    """Validate optional public metadata URLs."""
    if value is None:
        return
    parsed = urlparse(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"`{field}` must be an absolute https URL")


def validate_relative_path(
    plugin_root: Path, value: Any, field: str, errors: list[str]
) -> None:
    """Require a manifest component path to remain inside the plugin root."""
    if not non_empty_string(value):
        errors.append(f"`{field}` must be a non-empty relative path")
        return
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"`{field}` must stay inside the plugin root")
        return
    if not (plugin_root / path).exists():
        errors.append(f"`{field}` points to a missing path: {value}")


def validate_plugin(plugin_root: Path) -> list[str]:
    """Return all compatibility errors found in a Codex Plugin package."""
    errors: list[str] = []
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["missing `.codex-plugin/plugin.json`"]
    except json.JSONDecodeError as exc:
        return [f"`.codex-plugin/plugin.json` is invalid JSON: {exc}"]

    if not isinstance(manifest, dict):
        return ["`.codex-plugin/plugin.json` must contain a JSON object"]

    for key in sorted(set(manifest) - PLUGIN_KEYS):
        errors.append(f"unsupported plugin manifest field: `{key}`")
    for field in ("name", "version", "description", "license"):
        if not non_empty_string(manifest.get(field)):
            errors.append(f"`{field}` must be a non-empty string")
    version = manifest.get("version")
    if isinstance(version, str) and SEMVER_RE.fullmatch(version) is None:
        errors.append("`version` must use strict semantic versioning")

    author = manifest.get("author")
    if not isinstance(author, dict) or not non_empty_string(author.get("name")):
        errors.append("`author.name` must be a non-empty string")
    elif set(author) - {"name", "email", "url"}:
        errors.append("`author` contains unsupported fields")
    if isinstance(author, dict):
        validate_https_url(author.get("url"), "author.url", errors)

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("`interface` must be an object")
    else:
        for key in sorted(set(interface) - INTERFACE_KEYS):
            errors.append(f"unsupported interface field: `{key}`")
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
        ):
            if not non_empty_string(interface.get(field)):
                errors.append(f"`interface.{field}` must be a non-empty string")
        prompts = interface.get("defaultPrompt", interface.get("default_prompt"))
        if not isinstance(prompts, list) or not prompts or not all(
            non_empty_string(prompt) for prompt in prompts
        ):
            errors.append("`interface.defaultPrompt` must be a non-empty string array")
        capabilities = interface.get("capabilities")
        if not isinstance(capabilities, list) or not all(
            non_empty_string(capability) for capability in capabilities
        ):
            errors.append("`interface.capabilities` must be a string array")
        for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
            validate_https_url(interface.get(field), f"interface.{field}", errors)

    if "skills" in manifest:
        skills_value = manifest["skills"]
        validate_relative_path(plugin_root, skills_value, "skills", errors)
        if non_empty_string(skills_value):
            skills_root = plugin_root / skills_value
            if skills_root.is_dir() and not any(skills_root.glob("*/SKILL.md")):
                errors.append("`skills` does not contain a discoverable `*/SKILL.md`")
    for field in ("apps",):
        if field in manifest:
            validate_relative_path(plugin_root, manifest[field], field, errors)
    if isinstance(manifest.get("mcpServers"), str):
        validate_relative_path(
            plugin_root, manifest["mcpServers"], "mcpServers", errors
        )

    if "[TODO:" in json.dumps(manifest, ensure_ascii=False):
        errors.append("plugin manifest contains an unresolved `[TODO: ...]` marker")
    return errors


def main() -> None:
    """Print a readable validation result and set the process exit code."""
    plugin_root = Path(parse_args().plugin_root).resolve()
    errors = validate_plugin(plugin_root)
    if errors:
        print("Plugin validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Plugin validation passed: {plugin_root}")


if __name__ == "__main__":
    main()

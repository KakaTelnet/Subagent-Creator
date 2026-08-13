#!/usr/bin/env python3
"""Validate this repository's Codex Plugin manifest and component paths.

The check is intentionally strict for fields used by this repository while
remaining compatible with the current official Codex Plugin package schema.
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
    "hooks",
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
    "supportURL",
    "brandColor",
    "brandColorDark",
    "composerIcon",
    "logo",
    "logoDark",
    "screenshots",
    "defaultPrompt",
}
PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
CATEGORIES = {
    "Productivity",
    "Creativity",
    "Developer Tools",
    "Business & Operations",
    "Data & Analytics",
    "Communication",
    "Education & Research",
    "Security",
    "Finance",
    "Healthcare",
    "Travel",
    "Entertainment",
    "Other",
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
    if (
        parsed is None
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or len(value) > 2048
    ):
        errors.append(f"`{field}` must be an absolute https URL")


def validate_text_field(
    value: Any,
    field: str,
    errors: list[str],
    *,
    maximum: int,
    single_line: bool = False,
) -> None:
    """Validate a required manifest text field against package limits."""
    if not non_empty_string(value):
        errors.append(f"`{field}` must be a non-empty string")
        return
    if len(value) > maximum:
        errors.append(f"`{field}` must be {maximum} characters or fewer")
    if single_line and ("\n" in value or "\r" in value):
        errors.append(f"`{field}` must fit on one line")


def validate_relative_path(
    plugin_root: Path,
    value: Any,
    field: str,
    errors: list[str],
    *,
    expected: str | None = None,
) -> None:
    """Require a manifest component path to remain inside the plugin root."""
    if not non_empty_string(value):
        errors.append(f"`{field}` must be a non-empty relative path")
        return
    if not value.startswith("./"):
        errors.append(f"`{field}` must start with `./`")
        return
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"`{field}` must stay inside the plugin root")
        return
    resolved = plugin_root / path
    if not resolved.exists():
        errors.append(f"`{field}` points to a missing path: {value}")
    elif expected == "file" and not resolved.is_file():
        errors.append(f"`{field}` must point to a regular file")
    elif expected == "directory" and not resolved.is_dir():
        errors.append(f"`{field}` must point to a directory")


def validate_hooks(plugin_root: Path, value: Any, errors: list[str]) -> None:
    """Validate official path or inline lifecycle-hook manifest forms."""
    entries = value if isinstance(value, list) else [value]
    if not entries:
        errors.append("`hooks` must not be an empty array")
        return
    for index, entry in enumerate(entries):
        field = f"hooks[{index}]" if isinstance(value, list) else "hooks"
        if isinstance(entry, str):
            validate_relative_path(
                plugin_root,
                entry,
                field,
                errors,
                expected="file",
            )
        elif not isinstance(entry, dict) or not entry:
            errors.append(f"`{field}` must be a path or a non-empty inline hooks object")


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
    validate_text_field(
        manifest.get("name"),
        "name",
        errors,
        maximum=64,
        single_line=True,
    )
    if isinstance(manifest.get("name"), str) and not PLUGIN_NAME_RE.fullmatch(
        manifest["name"]
    ):
        errors.append("`name` must use only ASCII letters, digits, `_`, or `-`")
    validate_text_field(
        manifest.get("version"),
        "version",
        errors,
        maximum=64,
        single_line=True,
    )
    validate_text_field(
        manifest.get("description"),
        "description",
        errors,
        maximum=1024,
    )
    validate_text_field(
        manifest.get("license"),
        "license",
        errors,
        maximum=128,
        single_line=True,
    )
    version = manifest.get("version")
    if isinstance(version, str) and SEMVER_RE.fullmatch(version) is None:
        errors.append("`version` must use strict semantic versioning")

    author = manifest.get("author")
    if not isinstance(author, dict) or not non_empty_string(author.get("name")):
        errors.append("`author.name` must be a non-empty string")
    elif set(author) - {"name", "email", "url"}:
        errors.append("`author` contains unsupported fields")
    if isinstance(author, dict):
        if "email" in author and not non_empty_string(author.get("email")):
            errors.append("`author.email` must be a non-empty string when provided")
        validate_https_url(author.get("url"), "author.url", errors)

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("`interface` must be an object")
    else:
        for key in sorted(set(interface) - INTERFACE_KEYS):
            errors.append(f"unsupported interface field: `{key}`")
        validate_text_field(
            interface.get("displayName"),
            "interface.displayName",
            errors,
            maximum=80,
            single_line=True,
        )
        validate_text_field(
            interface.get("shortDescription"),
            "interface.shortDescription",
            errors,
            maximum=240,
            single_line=True,
        )
        validate_text_field(
            interface.get("longDescription"),
            "interface.longDescription",
            errors,
            maximum=4000,
        )
        validate_text_field(
            interface.get("developerName"),
            "interface.developerName",
            errors,
            maximum=120,
            single_line=True,
        )
        category = interface.get("category")
        validate_text_field(
            category,
            "interface.category",
            errors,
            maximum=64,
            single_line=True,
        )
        if isinstance(category, str) and category not in CATEGORIES:
            errors.append("`interface.category` is not an official category")
        raw_prompts = interface.get("defaultPrompt")
        prompts = [raw_prompts] if isinstance(raw_prompts, str) else raw_prompts
        if not isinstance(prompts, list) or not prompts or not all(
            non_empty_string(prompt) for prompt in prompts
        ):
            errors.append(
                "`interface.defaultPrompt` must be a non-empty string or string array"
            )
        else:
            if len(prompts) > 3:
                errors.append("`interface.defaultPrompt` must contain at most three prompts")
            normalized_prompts = [" ".join(prompt.split()) for prompt in prompts]
            if len(normalized_prompts) != len(set(normalized_prompts)):
                errors.append("`interface.defaultPrompt` entries must be unique")
            for index, prompt in enumerate(prompts):
                if len(prompt) > 512 or "\n" in prompt or "\r" in prompt:
                    errors.append(
                        f"`interface.defaultPrompt[{index}]` must fit on one line and "
                        "be 512 characters or fewer"
                    )
        capabilities = interface.get("capabilities")
        if not isinstance(capabilities, list) or not all(
            non_empty_string(capability) for capability in capabilities
        ):
            errors.append("`interface.capabilities` must be a string array")
        elif len(capabilities) > 20 or any(
            len(capability) > 120 or "\n" in capability or "\r" in capability
            for capability in capabilities
        ):
            errors.append(
                "`interface.capabilities` must contain at most 20 single-line entries "
                "of 120 characters or fewer"
            )
        for field in (
            "websiteURL",
            "privacyPolicyURL",
            "termsOfServiceURL",
            "supportURL",
        ):
            validate_https_url(interface.get(field), f"interface.{field}", errors)
        for field in ("brandColor", "brandColorDark"):
            value = interface.get(field)
            if value is not None and (
                not isinstance(value, str) or HEX_COLOR_RE.fullmatch(value) is None
            ):
                errors.append(f"`interface.{field}` must be a six-digit hex color")
        for field in ("composerIcon", "logo", "logoDark"):
            if field in interface:
                validate_relative_path(
                    plugin_root,
                    interface[field],
                    f"interface.{field}",
                    errors,
                    expected="file",
                )
        screenshots = interface.get("screenshots")
        if screenshots is not None:
            if not isinstance(screenshots, list) or not screenshots:
                errors.append("`interface.screenshots` must be a non-empty path array")
            else:
                for index, screenshot in enumerate(screenshots):
                    validate_relative_path(
                        plugin_root,
                        screenshot,
                        f"interface.screenshots[{index}]",
                        errors,
                        expected="file",
                    )

    if "skills" in manifest:
        skills_value = manifest["skills"]
        validate_relative_path(
            plugin_root,
            skills_value,
            "skills",
            errors,
            expected="directory",
        )
        if non_empty_string(skills_value):
            skills_root = plugin_root / skills_value
            if skills_root.is_dir() and not any(skills_root.glob("*/SKILL.md")):
                errors.append("`skills` does not contain a discoverable `*/SKILL.md`")
    for field in ("apps", "mcpServers"):
        if field in manifest:
            validate_relative_path(
                plugin_root,
                manifest[field],
                field,
                errors,
                expected="file",
            )
    if "hooks" in manifest:
        validate_hooks(plugin_root, manifest["hooks"], errors)

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

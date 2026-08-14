#!/usr/bin/env python3
"""Check the Skill's strict projection against current official Codex sources.

The managed Agent validator intentionally accepts only fields emitted by this
Skill. This CI check downloads the official Codex JSON Schema plus the official
Subagents Markdown page and fails if any emitted field is no longer documented.
It uses only Python's standard library and never modifies the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS = PROJECT_ROOT / "skills" / "subagent-creator" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from validate_team import (  # noqa: E402
    OFFICIAL_AGENTS_KEYS_USED,
    OFFICIAL_CUSTOM_AGENT_REQUIRED_KEYS,
    OFFICIAL_ROOT_CONFIG_KEYS_USED,
    OFFICIAL_SKILL_CONFIG_KEYS_USED,
    OFFICIAL_SKILLS_KEYS_USED,
    VALID_SANDBOXES,
)


OFFICIAL_SCHEMA_URL = "https://developers.openai.com/codex/config-schema.json"
OFFICIAL_SUBAGENTS_URL = "https://developers.openai.com/codex/subagents.md"
FIELD_PATTERN = re.compile(r"^\|?\s*`([a-z][a-z0-9_]*)`\s*\|", re.MULTILINE)
FIELD_SPEC_PATTERN = re.compile(
    r"^\|?\s*`(?P<name>[a-z][a-z0-9_]*)`\s*\|\s*"
    r"(?P<type>[^|]+?)\s*\|\s*(?P<required>[^|]+?)\s*\|",
    re.MULTILINE,
)


def fetch_text(url: str) -> str:
    """Download one official source with a bounded timeout."""
    request = Request(
        url,
        headers={"User-Agent": "subagent-creator-schema-check/0.1"},
    )
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def extract_custom_agent_fields(markdown: str) -> set[str]:
    """Extract the official custom Agent table without parsing unrelated prose."""
    start_marker = "### Custom agent file schema"
    end_marker = "### Example custom agents"
    start = markdown.find(start_marker)
    end = markdown.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise ValueError("official custom Agent schema section could not be located")
    return set(FIELD_PATTERN.findall(markdown[start:end]))


def extract_custom_agent_field_specs(markdown: str) -> dict[str, tuple[str, str]]:
    """Return documented type and requiredness for custom Agent fields."""
    start_marker = "### Custom agent file schema"
    end_marker = "### Example custom agents"
    start = markdown.find(start_marker)
    end = markdown.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise ValueError("official custom Agent schema section could not be located")
    return {
        match.group("name"): (
            match.group("type").strip().casefold(),
            match.group("required").strip().casefold(),
        )
        for match in FIELD_SPEC_PATTERN.finditer(markdown[start:end])
    }


def schema_properties(schema: dict[str, Any], definition: str | None) -> set[str]:
    """Return property names from the root schema or one named definition."""
    target: Any
    if definition is None:
        target = schema
    else:
        definitions = schema.get("definitions")
        if not isinstance(definitions, dict) or definition not in definitions:
            raise ValueError(f"official schema definition is missing: {definition}")
        target = definitions[definition]
    if not isinstance(target, dict) or not isinstance(target.get("properties"), dict):
        label = "root" if definition is None else definition
        raise ValueError(f"official schema properties are missing: {label}")
    return set(target["properties"])


def schema_definition(schema: dict[str, Any], definition: str) -> dict[str, Any]:
    """Return one official schema definition as an object."""
    definitions = schema.get("definitions")
    if not isinstance(definitions, dict) or not isinstance(
        definitions.get(definition),
        dict,
    ):
        raise ValueError(f"official schema definition is missing: {definition}")
    return definitions[definition]


def resolve_schema_node(schema: dict[str, Any], node: Any) -> dict[str, Any]:
    """Resolve the simple refs/allOf wrappers used by emitted Codex fields."""
    if not isinstance(node, dict):
        return {}
    if isinstance(node.get("$ref"), str):
        prefix = "#/definitions/"
        reference = node["$ref"]
        if reference.startswith(prefix):
            return resolve_schema_node(
                schema,
                schema_definition(schema, reference.removeprefix(prefix)),
            )
    all_of = node.get("allOf")
    if isinstance(all_of, list) and len(all_of) == 1:
        return resolve_schema_node(schema, all_of[0])
    return node


def property_node(
    schema: dict[str, Any],
    definition: str | None,
    field: str,
) -> dict[str, Any]:
    """Return one resolved property node from root or a definition."""
    target = schema if definition is None else schema_definition(schema, definition)
    properties = target.get("properties") if isinstance(target, dict) else None
    if not isinstance(properties, dict):
        return {}
    return resolve_schema_node(schema, properties.get(field))


def compatibility_errors(schema: dict[str, Any], markdown: str) -> list[str]:
    """Return projected fields or constraints current sources no longer support."""
    checks = {
        "root config": (
            OFFICIAL_ROOT_CONFIG_KEYS_USED,
            schema_properties(schema, None),
        ),
        "AgentsToml": (
            OFFICIAL_AGENTS_KEYS_USED,
            schema_properties(schema, "AgentsToml"),
        ),
        "SkillsConfig": (
            OFFICIAL_SKILLS_KEYS_USED,
            schema_properties(schema, "SkillsConfig"),
        ),
        "SkillConfig": (
            OFFICIAL_SKILL_CONFIG_KEYS_USED,
            schema_properties(schema, "SkillConfig"),
        ),
        "custom Agent docs": (
            OFFICIAL_CUSTOM_AGENT_REQUIRED_KEYS,
            extract_custom_agent_fields(markdown),
        ),
    }
    errors: list[str] = []
    for label, (required, observed) in checks.items():
        missing = sorted(required - observed)
        if missing:
            errors.append(f"{label} no longer exposes projected fields: {missing}")

    expected_types = {
        (None, "developer_instructions"): "string",
        (None, "model"): "string",
        (None, "model_reasoning_effort"): "string",
        (None, "sandbox_mode"): "string",
        (None, "skills"): "object",
        ("AgentsToml", "enabled"): "boolean",
        ("AgentsToml", "max_concurrent_threads_per_session"): "integer",
        ("SkillsConfig", "config"): "array",
        ("SkillConfig", "enabled"): "boolean",
        ("SkillConfig", "path"): "string",
    }
    for (definition, field), expected_type in expected_types.items():
        node = property_node(schema, definition, field)
        if node.get("type") != expected_type:
            label = "root config" if definition is None else definition
            errors.append(
                f"{label}.{field} must remain type {expected_type}, got: "
                f"{node.get('type')!r}"
            )

    concurrency = property_node(
        schema,
        "AgentsToml",
        "max_concurrent_threads_per_session",
    )
    minimum = concurrency.get("minimum")
    if not isinstance(minimum, (int, float)) or minimum < 1:
        errors.append(
            "AgentsToml.max_concurrent_threads_per_session must retain minimum 1"
        )

    sandbox = property_node(schema, None, "sandbox_mode")
    official_sandboxes = sandbox.get("enum")
    if not isinstance(official_sandboxes, list) or not VALID_SANDBOXES.issubset(
        set(official_sandboxes)
    ):
        errors.append(
            "root config.sandbox_mode no longer accepts every emitted sandbox: "
            f"{sorted(VALID_SANDBOXES)}"
        )

    skill_config = schema_definition(schema, "SkillConfig")
    if "enabled" not in skill_config.get("required", []):
        errors.append("SkillConfig.enabled must remain required")
    config_items = property_node(schema, "SkillsConfig", "config").get("items")
    resolved_items = resolve_schema_node(schema, config_items)
    if resolved_items != schema_definition(schema, "SkillConfig"):
        errors.append("SkillsConfig.config items must continue to use SkillConfig")

    custom_specs = extract_custom_agent_field_specs(markdown)
    for field in sorted(OFFICIAL_CUSTOM_AGENT_REQUIRED_KEYS):
        field_type, required = custom_specs.get(field, ("", ""))
        if "string" not in field_type:
            errors.append(f"custom Agent docs.{field} must remain type string")
        if required not in {"yes", "required"}:
            errors.append(f"custom Agent docs.{field} must remain required")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse optional offline snapshots used by tests and local debugging."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema",
        type=Path,
        help="Read an official-format JSON Schema snapshot instead of downloading it",
    )
    parser.add_argument(
        "--document",
        type=Path,
        help="Read an official-format Subagents Markdown snapshot instead of downloading it",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Return nonzero when the strict local projection drifts from official sources."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        schema_text = (
            args.schema.read_text(encoding="utf-8")
            if args.schema is not None
            else fetch_text(OFFICIAL_SCHEMA_URL)
        )
        markdown = (
            args.document.read_text(encoding="utf-8")
            if args.document is not None
            else fetch_text(OFFICIAL_SUBAGENTS_URL)
        )
        schema = json.loads(schema_text)
        if not isinstance(schema, dict):
            raise ValueError("official Codex schema root must be an object")
        errors = compatibility_errors(schema, markdown)
    except (
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        HTTPError,
        URLError,
    ) as exc:
        print(f"Official Codex schema check failed: {exc}")
        return 1

    if errors:
        for error in errors:
            print(f"Official Codex schema incompatibility: {error}")
        return 1

    print(
        "Official Codex schema compatibility passed: "
        f"{OFFICIAL_SCHEMA_URL} and {OFFICIAL_SUBAGENTS_URL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

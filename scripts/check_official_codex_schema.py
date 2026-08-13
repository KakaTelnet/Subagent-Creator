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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = PROJECT_ROOT / "skills" / "subagent-creator" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from validate_team import (  # noqa: E402
    OFFICIAL_AGENTS_KEYS_USED,
    OFFICIAL_CUSTOM_AGENT_REQUIRED_KEYS,
    OFFICIAL_ROOT_CONFIG_KEYS_USED,
    OFFICIAL_SKILL_CONFIG_KEYS_USED,
    OFFICIAL_SKILLS_KEYS_USED,
)


OFFICIAL_SCHEMA_URL = "https://developers.openai.com/codex/config-schema.json"
OFFICIAL_SUBAGENTS_URL = "https://developers.openai.com/codex/subagents.md"
FIELD_PATTERN = re.compile(r"^\|?\s*`([a-z][a-z0-9_]*)`\s*\|", re.MULTILINE)


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


def compatibility_errors(schema: dict[str, Any], markdown: str) -> list[str]:
    """Return projected fields that current official sources no longer support."""
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

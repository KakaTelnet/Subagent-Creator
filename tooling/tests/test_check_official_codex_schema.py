#!/usr/bin/env python3
"""Unit tests for the offline Codex Schema compatibility logic."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tooling" / "scripts"))

from check_official_codex_schema import compatibility_errors  # noqa: E402


def compatible_schema() -> dict[str, object]:
    """Return the smallest official-shape schema covering emitted fields."""
    return {
        "properties": {
            "developer_instructions": {"type": "string"},
            "model": {"type": "string"},
            "model_reasoning_effort": {"$ref": "#/definitions/ReasoningEffort"},
            "sandbox_mode": {"$ref": "#/definitions/SandboxMode"},
            "skills": {"$ref": "#/definitions/SkillsConfig"},
        },
        "definitions": {
            "AgentsToml": {
                "properties": {
                    "enabled": {"type": "boolean"},
                    "max_concurrent_threads_per_session": {
                        "minimum": 1,
                        "type": "integer",
                    },
                }
            },
            "ReasoningEffort": {"minLength": 1, "type": "string"},
            "SandboxMode": {
                "enum": ["read-only", "workspace-write", "danger-full-access"],
                "type": "string",
            },
            "SkillsConfig": {
                "properties": {
                    "config": {
                        "items": {"$ref": "#/definitions/SkillConfig"},
                        "type": "array",
                    }
                },
                "type": "object",
            },
            "SkillConfig": {
                "properties": {
                    "enabled": {"type": "boolean"},
                    "path": {"type": "string"},
                },
                "required": ["enabled"],
                "type": "object",
            },
        },
    }


SUBAGENTS_DOCUMENT = """### Custom agent file schema

| Field | Type | Required |
| --- | --- | --- |
| `name` | string | Yes |
| `description` | string | Yes |
| `developer_instructions` | string | Yes |

### Example custom agents
"""


class OfficialCodexSchemaTests(unittest.TestCase):
    """Reject drift while allowing unrelated official schema expansion."""

    def test_current_projection_is_compatible(self) -> None:
        self.assertEqual(compatibility_errors(compatible_schema(), SUBAGENTS_DOCUMENT), [])

    def test_missing_projected_field_is_reported(self) -> None:
        schema = compatible_schema()
        del schema["properties"]["sandbox_mode"]  # type: ignore[index]
        errors = compatibility_errors(schema, SUBAGENTS_DOCUMENT)
        self.assertTrue(any("sandbox_mode" in error for error in errors), errors)

    def test_new_official_fields_do_not_expand_local_runtime_acceptance(self) -> None:
        schema = compatible_schema()
        schema["properties"]["future_field"] = {}  # type: ignore[index]
        self.assertEqual(compatibility_errors(schema, SUBAGENTS_DOCUMENT), [])

    def test_projected_type_drift_is_reported(self) -> None:
        schema = compatible_schema()
        schema["definitions"]["AgentsToml"]["properties"]["enabled"] = {  # type: ignore[index]
            "type": "string"
        }
        errors = compatibility_errors(schema, SUBAGENTS_DOCUMENT)
        self.assertTrue(any("AgentsToml.enabled" in error for error in errors), errors)

    def test_projected_constraint_drift_is_reported(self) -> None:
        schema = compatible_schema()
        schema["definitions"]["SandboxMode"]["enum"] = ["read-only"]  # type: ignore[index]
        errors = compatibility_errors(schema, SUBAGENTS_DOCUMENT)
        self.assertTrue(any("sandbox_mode" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)

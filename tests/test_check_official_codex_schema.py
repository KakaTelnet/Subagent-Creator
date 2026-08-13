#!/usr/bin/env python3
"""Unit tests for the offline Codex Schema compatibility logic."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_official_codex_schema import compatibility_errors  # noqa: E402


def compatible_schema() -> dict[str, object]:
    """Return the smallest official-shape schema covering emitted fields."""
    return {
        "properties": {
            "developer_instructions": {},
            "model": {},
            "model_reasoning_effort": {},
            "sandbox_mode": {},
            "skills": {},
        },
        "definitions": {
            "AgentsToml": {
                "properties": {
                    "enabled": {},
                    "max_concurrent_threads_per_session": {},
                }
            },
            "SkillsConfig": {"properties": {"config": {}}},
            "SkillConfig": {"properties": {"enabled": {}, "path": {}}},
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


if __name__ == "__main__":
    unittest.main(verbosity=2)

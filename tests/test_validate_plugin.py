#!/usr/bin/env python3
"""Regression tests for the repository-owned Codex Plugin validator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PROJECT_ROOT / "scripts" / "validate_plugin.py"


class PluginValidatorTests(unittest.TestCase):
    """Ensure CI rejects broken plugin metadata and accepts this package."""

    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        """Run the validator with the active virtual-environment Python."""
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_repository_plugin_passes(self) -> None:
        result = self.run_validator(PROJECT_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_current_official_schema_compatibility_fields_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            (temporary_root / ".codex-plugin").mkdir()
            (temporary_root / "skills" / "example").mkdir(parents=True)
            (temporary_root / "skills" / "example" / "SKILL.md").write_text(
                "---\nname: example\ndescription: Example skill.\n---\nRun it.\n",
                encoding="utf-8",
            )
            (temporary_root / "hooks").mkdir()
            (temporary_root / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {}}),
                encoding="utf-8",
            )
            (temporary_root / ".mcp.json").write_text("{}\n", encoding="utf-8")
            (temporary_root / ".app.json").write_text("{}\n", encoding="utf-8")
            manifest = {
                "id": "example",
                "name": "example",
                "version": "1.0.0",
                "description": "Example plugin",
                "license": "AGPL-3.0-only",
                "author": {"name": "Example"},
                "homepage": "https://example.com/docs",
                "repository": "https://example.com/source",
                "keywords": ["example", "testing"],
                "skills": "./skills/",
                "mcpServers": "./.mcp.json",
                "apps": "./.app.json",
                "hooks": "./hooks/hooks.json",
                "interface": {
                    "displayName": "Example",
                    "shortDescription": "Example plugin",
                    "longDescription": "Example plugin for compatibility tests.",
                    "developerName": "Example",
                    "category": "Developer Tools",
                    "capabilities": ["Write"],
                    "supportURL": "https://example.com/support",
                    "brandColor": "#123456",
                    "brandColorDark": "#ABCDEF",
                    "defaultPrompt": "Use $example.",
                },
            }
            manifest_path = temporary_root / ".codex-plugin" / "plugin.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_validator(temporary_root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_default_prompt_rejects_more_than_three_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            (temporary_root / ".codex-plugin").mkdir()
            (temporary_root / "skills" / "example").mkdir(parents=True)
            (temporary_root / "skills" / "example" / "SKILL.md").write_text(
                "---\nname: example\ndescription: Example skill.\n---\nRun it.\n",
                encoding="utf-8",
            )
            manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Example plugin",
                "license": "AGPL-3.0-only",
                "author": {"name": "Example"},
                "skills": "./skills/",
                "interface": {
                    "displayName": "Example",
                    "shortDescription": "Example plugin",
                    "longDescription": "Example plugin for validation tests.",
                    "developerName": "Example",
                    "category": "Developer Tools",
                    "capabilities": ["Write"],
                    "defaultPrompt": ["One", "Two", "Three", "Four"],
                },
            }
            manifest_path = temporary_root / ".codex-plugin" / "plugin.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_validator(temporary_root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("at most three prompts", result.stdout)

    def test_keywords_must_be_a_string_array(self) -> None:
        manifest = json.loads(
            (PROJECT_ROOT / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        manifest["keywords"] = "not-an-array"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            (temporary_root / ".codex-plugin").mkdir()
            (temporary_root / "skills" / "construct-subagent").mkdir(parents=True)
            (temporary_root / "skills" / "construct-subagent" / "SKILL.md").write_text(
                "---\nname: construct-subagent\ndescription: Example skill.\n---\nRun it.\n",
                encoding="utf-8",
            )
            (temporary_root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            result = self.run_validator(temporary_root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("`keywords` must be an array", result.stdout)

    def test_unknown_manifest_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            (temporary_root / ".codex-plugin").mkdir()
            (temporary_root / "skills" / "example").mkdir(parents=True)
            (temporary_root / "skills" / "example" / "SKILL.md").write_text(
                "---\nname: example\ndescription: Example skill.\n---\n",
                encoding="utf-8",
            )
            manifest = {
                "name": "example",
                "version": "1.0.0",
                "description": "Example plugin",
                "license": "AGPL-3.0-only",
                "author": {"name": "Example"},
                "skills": "./skills/",
                "unsupported": True,
                "interface": {
                    "displayName": "Example",
                    "shortDescription": "Example plugin",
                    "longDescription": "Example plugin for validation tests.",
                    "developerName": "Example",
                    "category": "Developer Tools",
                    "capabilities": ["Write"],
                    "defaultPrompt": ["Use $example."],
                },
            }
            manifest_path = temporary_root / ".codex-plugin" / "plugin.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_validator(temporary_root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unsupported plugin manifest field", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

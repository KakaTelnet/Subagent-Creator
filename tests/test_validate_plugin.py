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

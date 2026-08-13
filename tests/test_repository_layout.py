#!/usr/bin/env python3
"""Validate the public repository and distributable Skill layout.

These tests use only the Python standard library so contributors can verify the
repository before installing optional development tooling.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "skills" / "construct-subagent"


class RepositoryLayoutTests(unittest.TestCase):
    """Keep repository-only files separate from the installable Skill package."""

    def test_plugin_manifest_points_to_skill_directory(self) -> None:
        manifest_path = PROJECT_ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "construct-subagent")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")

    def test_dual_license_files_and_manifest_stay_consistent(self) -> None:
        manifest_path = PROJECT_ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["license"], "AGPL-3.0-only")

        license_bytes = (PROJECT_ROOT / "LICENSE").read_bytes()
        self.assertEqual(
            hashlib.sha256(license_bytes).hexdigest(),
            "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0",
        )

        commercial_notice = (PROJECT_ROOT / "COMMERCIAL-LICENSE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("商业使用本身不要求购买商业许可证", commercial_notice)
        self.assertIn("本身不是商业许可证", commercial_notice)

    def test_skill_package_contains_only_runtime_concerns(self) -> None:
        expected = {
            "SKILL.md",
            "agents/openai.yaml",
            "references/agent-team-contract.md",
            "scripts/validate_team.py",
        }
        actual = {
            str(path.relative_to(SKILL_ROOT))
            for path in SKILL_ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(actual, expected)

    def test_skill_name_matches_directory_and_reference_exists(self) -> None:
        skill_path = SKILL_ROOT / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        self.assertRegex(content, r"(?m)^name: construct-subagent$")
        match = re.search(r"\[Agent Team Contract\]\(([^)]+)\)", content)
        self.assertIsNotNone(match)
        reference = SKILL_ROOT / match.group(1)
        self.assertTrue(reference.is_file(), reference)

    def test_openai_metadata_invokes_named_skill(self) -> None:
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$construct-subagent", metadata)

    def test_runtime_codex_compatibility_gate_is_distributed(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references" / "agent-team-contract.md").read_text(
            encoding="utf-8"
        )
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        for content in (skill, contract):
            self.assertIn("BLOCKED_BY_CODEX_COMPATIBILITY", content)
            self.assertIn("runtime_codex_compatibility", content)
        self.assertIn("MINIMUM_CODEX_VERSION = (0, 145, 0)", validator)
        self.assertIn("MAXIMUM_REVIEWED_CODEX_SERIES = (0, 147)", validator)
        self.assertIn('"--codex-version"', validator)

    def test_ci_runs_skill_and_plugin_validators(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("agentskills validate skills/construct-subagent", workflow)
        self.assertIn("python3 scripts/validate_plugin.py .", workflow)

    def test_python_compatibility_is_machine_readable_and_exercised(self) -> None:
        metadata_path = PROJECT_ROOT / "pyproject.toml"
        with metadata_path.open("rb") as handle:
            metadata = tomllib.load(handle)
        self.assertEqual(metadata["project"]["requires-python"], ">=3.11")
        self.assertEqual(
            (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip(),
            "3.13.9",
        )

        workflow = (PROJECT_ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('python-version: ["3.11", "3.13"]', workflow)
        self.assertIn("python-version: ${{ matrix.python-version }}", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)

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
SKILL_ROOT = PROJECT_ROOT / "skills" / "subagent-creator"


class RepositoryLayoutTests(unittest.TestCase):
    """Keep repository-only files separate from the installable Skill package."""

    def test_plugin_manifest_points_to_skill_directory(self) -> None:
        manifest_path = PROJECT_ROOT / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "subagent-creator")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(
            manifest["author"],
            {
                "name": "KakaTelnet",
                "email": "kakatelnet@gmail.com",
                "url": "https://github.com/KakaTelnet",
            },
        )
        self.assertEqual(
            manifest["repository"],
            "https://github.com/KakaTelnet/Subagent-Creator",
        )
        self.assertEqual(manifest["interface"]["capabilities"], ["Read", "Write"])

    def test_public_marketplace_installs_the_root_plugin(self) -> None:
        marketplace_path = PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        self.assertEqual(marketplace["name"], "subagent-creator")
        self.assertEqual(
            marketplace["interface"]["displayName"], "Subagent Creator"
        )
        self.assertEqual(len(marketplace["plugins"]), 1)

        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "subagent-creator")
        self.assertEqual(
            entry["source"],
            {
                "source": "url",
                "url": "https://github.com/KakaTelnet/Subagent-Creator.git",
                "ref": "main",
            },
        )
        self.assertEqual(
            entry["policy"],
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        )
        self.assertEqual(entry["category"], "Developer Tools")

        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "codex plugin marketplace add KakaTelnet/Subagent-Creator --ref main",
            readme,
        )

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
        self.assertRegex(content, r"(?m)^name: subagent-creator$")
        match = re.search(r"\[Agent Team Contract\]\(([^)]+)\)", content)
        self.assertIsNotNone(match)
        reference = SKILL_ROOT / match.group(1)
        self.assertTrue(reference.is_file(), reference)

    def test_skill_description_is_trigger_oriented(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"(?m)^description: (.+)$", content)
        self.assertIsNotNone(match)
        description = match.group(1)
        for expected in (
            "当用户要求",
            "创建或配置 Subagent",
            "审计 Agent 团队",
            "持久调度接线",
            "全局角色库",
            "只配置团队基础设施",
        ):
            self.assertIn(expected, description)
        self.assertNotIn(".codex/agents", description)
        self.assertNotIn("BLOCKED_BY_", description)

    def test_openai_metadata_invokes_named_skill(self) -> None:
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$subagent-creator", metadata)

    def test_scope_contract_defaults_to_project_and_guards_personal(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references" / "agent-team-contract.md").read_text(
            encoding="utf-8"
        )
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        for content in (skill, contract, readme):
            self.assertIn("personal", content)
            self.assertIn("project", content)
            self.assertIn("专项声明", content)
        self.assertIn('default="project"', validator)
        self.assertIn('"--personal-scope-authorized"', validator)
        self.assertIn('self.codex_home / "agents"', validator)

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
        self.assertIn("agentskills validate skills/subagent-creator", workflow)
        self.assertIn("python3 scripts/validate_plugin.py .", workflow)
        self.assertIn("python3 scripts/check_official_codex_schema.py", workflow)
        self.assertIn("python3 scripts/check_official_plugin_schema.py", workflow)

    def test_local_codex_projection_and_official_compatibility_are_separate(self) -> None:
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        checker = (PROJECT_ROOT / "scripts" / "check_official_codex_schema.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("CUSTOM_AGENT_ALLOWED_KEYS", validator)
        self.assertIn('"local_codex_schema"', validator)
        self.assertIn("OFFICIAL_SCHEMA_URL", checker)
        self.assertIn("OFFICIAL_SUBAGENTS_URL", checker)

    def test_ci_actions_are_pinned_to_immutable_commits(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        uses_lines = [
            line.strip()
            for line in workflow.splitlines()
            if line.strip().startswith("uses:")
        ]
        self.assertTrue(uses_lines)
        for line in uses_lines:
            self.assertRegex(line, r"^uses: [^@]+@[0-9a-f]{40}(?:\s+#\s+v\d+)?$")

    def test_dependabot_tracks_python_and_action_dependencies(self) -> None:
        dependabot = (PROJECT_ROOT / ".github" / "dependabot.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("package-ecosystem: pip", dependabot)
        self.assertIn("package-ecosystem: github-actions", dependabot)

    def test_readiness_and_path_safety_contracts_are_distributed(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references" / "agent-team-contract.md").read_text(
            encoding="utf-8"
        )
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        for content in (skill, contract, validator):
            self.assertIn("AGENT_TEAM_CONFIGURATION_READY", content)
            self.assertIn("AGENT_TEAM_RUNTIME_READY", content)
            self.assertIn("AGENT_TEAM_VERIFIED", content)
            self.assertIn("HOST_VERIFIED", content)
            self.assertIn("HostCodexVersionEvidence", content)
        for content in (skill, contract):
            self.assertIn("BLOCKED_BY_UNSAFE_PATH", content)
        self.assertIn("find_symlink_component", validator)

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

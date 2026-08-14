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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = PROJECT_ROOT / "skills" / "subagent-creator"


class RepositoryLayoutTests(unittest.TestCase):
    """Keep repository-only files separate from the installable Skill package."""

    def test_maintenance_files_live_under_tooling_directory(self) -> None:
        for old_root_entry in ("requirements-dev.txt", "scripts", "tests"):
            self.assertFalse((PROJECT_ROOT / old_root_entry).exists(), old_root_entry)
        for maintained_path in (
            "requirements-dev.txt",
            "scripts/validate_plugin.py",
            "scripts/check_official_plugin_schema.py",
            "scripts/check_official_codex_schema.py",
            "tests/test_repository_layout.py",
            "tests/fixtures/forward_cases.json",
        ):
            self.assertTrue(
                (PROJECT_ROOT / "tooling" / maintained_path).is_file(),
                maintained_path,
            )
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("tmp_py/", gitignore.splitlines())

    def test_community_documents_live_under_github_directory(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        for filename in ("CONTRIBUTING.md", "SECURITY.md"):
            self.assertFalse((PROJECT_ROOT / filename).exists(), filename)
            self.assertTrue((PROJECT_ROOT / ".github" / filename).is_file(), filename)
            self.assertIn(f".github/{filename}", readme)

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
            "references/goal-execution-handoff.md",
            "references/runtime-readiness.md",
            "references/team-design.md",
            "scripts/validate_team.py",
        }
        actual = {
            str(path.relative_to(SKILL_ROOT))
            for path in SKILL_ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(actual, expected)

    def test_skill_name_matches_directory_and_references_exist(self) -> None:
        skill_path = SKILL_ROOT / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        self.assertRegex(content, r"(?m)^name: subagent-creator$")
        for label in (
            "Team Design Guide",
            "Agent Team Contract",
            "Runtime Readiness",
            "Goal Execution Handoff",
        ):
            match = re.search(rf"\[{label}\]\(([^)]+)\)", content)
            self.assertIsNotNone(match, label)
            reference = SKILL_ROOT / match.group(1)
            self.assertTrue(reference.is_file(), reference)

        direct_reference_links = {
            match.group(1)
            for match in re.finditer(
                r"\[[^\]]+\]\((references/[^)#]+\.md)\)", content
            )
        }
        reference_files = {
            str(path.relative_to(SKILL_ROOT))
            for path in (SKILL_ROOT / "references").glob("*.md")
        }
        self.assertEqual(direct_reference_links, reference_files)

    def test_skill_uses_progressive_reference_routing(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 100)
        self.assertIn("Load only the reference needed", skill)
        self.assertIn("only when external model", skill)
        for explanation_route in (
            "explaining role separation",
            "explaining generated files and their lifecycle",
            "explaining readiness levels or evidence trust",
            "For a general explanation that does not depend on",
        ):
            self.assertIn(explanation_route, skill)
        for implementation_detail in (
            "HostModelEvidence",
            "HostPermissionEvidence",
            "HostCodexVersionEvidence",
            "MINIMUM_CODEX_VERSION",
            "max_concurrent_threads_per_session = 3",
        ):
            self.assertNotIn(implementation_detail, skill)

        for reference_name in (
            "agent-team-contract.md",
            "goal-execution-handoff.md",
            "runtime-readiness.md",
            "team-design.md",
        ):
            reference = (
                SKILL_ROOT / "references" / reference_name
            ).read_text(encoding="utf-8")
            if len(reference.splitlines()) > 100:
                self.assertIn("## Contents", reference, reference_name)

    def test_successful_project_team_emits_goal_execution_handoff(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        handoff = (
            SKILL_ROOT / "references" / "goal-execution-handoff.md"
        ).read_text(encoding="utf-8")
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

        for expected in (
            "only after a successful project-scoped `CREATE` or `UPDATE`",
            "append its copyable `/goal` prompt without starting product work",
            "Do not read or emit it for other outcomes or global scope",
            "leave Goal creation and execution to the user's next request",
        ):
            self.assertIn(expected, skill)

        for expected in (
            "AGENT_TEAM_CONFIGURATION_READY",
            "Do not emit this handoff for `EXPLAIN`, `AUDIT`, global role libraries",
            "/goal 严格按照 <实现计划文件路径>",
            ".codex/agent-team.toml",
            "invoke_when",
            "Subagent 不得 commit、push、创建 PR、merge 或发布",
            "只有满足以上全部条件，才能将 GOAL 标记为 complete",
            "https://learn.chatgpt.com/use-cases/follow-goals",
        ):
            self.assertIn(expected, handoff)

        self.assertIn("可复制的 `/goal` 实现推进提示词", readme)

    def test_skill_description_is_trigger_oriented(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"(?m)^description: (.+)$", content)
        self.assertIsNotNone(match)
        description = match.group(1)
        for expected in (
            "解释、设计、创建、审计或更新",
            "当用户要求",
            "了解、创建或配置 Subagent",
            "审计 Agent 团队",
            "多模型或并行 Agent 工作流",
        ):
            self.assertIn(expected, description)
        for implementation_detail in (
            "持久调度接线",
            "全局角色库",
            "只配置团队基础设施",
            ".codex/agents",
            "BLOCKED_BY_",
        ):
            self.assertNotIn(implementation_detail, description)
        for body_contract in (
            "Default to a durable project-level team",
            "global role library",
            "Configure team infrastructure only",
            "decompose implementation tasks",
        ):
            self.assertIn(body_contract, content)

    def test_skill_separates_read_only_and_mutating_operations(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for operation in ("`EXPLAIN`", "`AUDIT`", "`CREATE`", "`UPDATE`"):
            self.assertIn(operation, skill)
        self.assertIn("`EXPLAIN` and `AUDIT` are read-only", skill)
        self.assertIn("reports proposed CREATE, UPDATE, KEEP, and RETIRE", skill)
        self.assertIn("Run this step only in `CREATE` or `UPDATE`", skill)
        self.assertIn("confirmation that no files changed", skill)

    def test_skill_is_prompt_driven_and_allows_no_team_outcome(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        design = (SKILL_ROOT / "references" / "team-design.md").read_text(
            encoding="utf-8"
        )
        contract = (
            SKILL_ROOT / "references" / "agent-team-contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("natural-language prompt", skill)
        self.assertIn("Do not require a fixed intake template", skill)
        self.assertIn("Compare every candidate role with the main Agent", skill)
        self.assertIn("NO_AGENT_TEAM_NEEDED", skill)
        self.assertIn("Do not force a one-role team", design)
        self.assertIn("pre-generation outcome, not a Manifest `status`", contract)

    def test_openai_metadata_matches_current_skill(self) -> None:
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        short_match = re.search(r'(?m)^  short_description: "([^"]+)"$', metadata)
        self.assertIsNotNone(short_match)
        self.assertGreaterEqual(len(short_match.group(1)), 25)
        self.assertLessEqual(len(short_match.group(1)), 64)

        prompt_match = re.search(r'(?m)^  default_prompt: "([^"]+)"$', metadata)
        self.assertIsNotNone(prompt_match)
        prompt = prompt_match.group(1)
        for expected in (
            "$subagent-creator",
            "explain",
            "audit",
            "create",
            "update",
            "create no team",
        ):
            self.assertIn(expected, prompt)

    def test_forward_cases_cover_new_behavior_without_leaking_oracles(self) -> None:
        fixture = json.loads(
            (
                PROJECT_ROOT
                / "tooling"
                / "tests"
                / "fixtures"
                / "forward_cases.json"
            ).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(fixture["schema_version"], 1)
        cases = fixture["cases"]
        self.assertEqual(
            {case["id"] for case in cases},
            {
                "audit-read-only",
                "explain-without-inspection",
                "no-team-needed",
                "prompt-driven-create",
                "update-idempotent",
            },
        )
        for case in cases:
            self.assertIn("$subagent-creator", case["agent_input"]["prompt"])
            self.assertNotIn("oracle", case["agent_input"])
            self.assertIn(
                case["oracle"]["operation"],
                {"EXPLAIN", "AUDIT", "CREATE", "UPDATE"},
            )
            self.assertIn(case["oracle"]["mutation"], {"none", "managed_only"})
            self.assertTrue(case["oracle"]["required_outcomes"])

    def test_scope_contract_defaults_to_project_and_guards_personal(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references" / "agent-team-contract.md").read_text(
            encoding="utf-8"
        )
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("explicitly requests global", skill)
        self.assertIn("Global scope requires an explicit statement", contract)
        self.assertIn("专项声明", readme)
        self.assertIn("project", skill)
        self.assertIn("personal", contract)
        self.assertIn("project", contract)
        self.assertIn('default="project"', validator)
        self.assertIn('"--personal-scope-authorized"', validator)
        self.assertIn('self.codex_home / "agents"', validator)

    def test_runtime_codex_compatibility_gate_is_distributed(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        runtime = (SKILL_ROOT / "references" / "runtime-readiness.md").read_text(
            encoding="utf-8"
        )
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Runtime Readiness", skill)
        self.assertIn("BLOCKED_BY_CODEX_COMPATIBILITY", runtime)
        self.assertIn("runtime_codex_compatibility", runtime)
        self.assertIn("MINIMUM_CODEX_VERSION = (0, 145, 0)", validator)
        self.assertIn("MAXIMUM_REVIEWED_CODEX_SERIES = (0, 147)", validator)
        self.assertIn('"--codex-version"', validator)

    def test_ci_runs_skill_and_plugin_validators(self) -> None:
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("agentskills validate skills/subagent-creator", workflow)
        self.assertIn(
            "python3 -m unittest discover -s tooling/tests", workflow
        )
        self.assertIn("-r tooling/requirements-dev.txt", workflow)
        self.assertIn("python3 tooling/scripts/validate_plugin.py .", workflow)
        self.assertIn(
            "python3 tooling/scripts/check_official_codex_schema.py", workflow
        )
        self.assertIn(
            "python3 tooling/scripts/check_official_plugin_schema.py", workflow
        )

    def test_local_codex_projection_and_official_compatibility_are_separate(self) -> None:
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        checker = (
            PROJECT_ROOT / "tooling" / "scripts" / "check_official_codex_schema.py"
        ).read_text(encoding="utf-8")
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
        self.assertIn("directory: /tooling", dependabot)

    def test_readiness_and_path_safety_contracts_are_distributed(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references" / "agent-team-contract.md").read_text(
            encoding="utf-8"
        )
        runtime = (SKILL_ROOT / "references" / "runtime-readiness.md").read_text(
            encoding="utf-8"
        )
        validator = (SKILL_ROOT / "scripts" / "validate_team.py").read_text(
            encoding="utf-8"
        )
        for content in (skill, runtime, validator):
            self.assertIn("AGENT_TEAM_CONFIGURATION_READY", content)
            self.assertIn("AGENT_TEAM_RUNTIME_READY", content)
            self.assertIn("AGENT_TEAM_VERIFIED", content)
        for content in (runtime, validator):
            self.assertIn("HOST_VERIFIED", content)
            self.assertIn("HostCodexVersionEvidence", content)
        self.assertIn("BLOCKED_BY_UNSAFE_PATH", contract)
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

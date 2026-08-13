#!/usr/bin/env python3
"""Regression tests for the construct-subagent team validator.

The tests create isolated temporary Codex projects, exercise successful and
failing manifests, and print the standard unittest exit status.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "skills" / "construct-subagent"
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_team.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_team import MANAGED_HEADER, TeamValidator  # noqa: E402


AGENT_TOML = f'''{MANAGED_HEADER}
name = "code_mapper"
description = "Read-only explorer for mapping implementation paths."
model = "economy-model"
model_reasoning_effort = "low"
sandbox_mode = "read-only"
developer_instructions = """
Responsibilities: map code paths and tests.
Boundaries: do not edit files or redefine requirements.
Inputs: read the Task Contract and AGENTS.md.
Outputs: return exact file references.
Escalation: return BLOCKED to the main agent on conflicts.
"""
'''


MANIFEST_TOML = '''schema_version = 1
generator = "construct-subagent"
status = "ready"
last_changed_at = "2026-08-13T16:31:00+08:00"

[project]
size = "small"
summary = "Small single-module implementation project."
complexity = ["single-module"]
task_types = ["coding", "testing"]
risks = ["regression"]
priorities = ["cost", "quality"]
artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]
constraints = ["Preserve the public contract."]

[orchestration]
coordinator = "main"
topology = "flat"
max_concurrent_agents = 2
agent_direct_dispatch = false
parallel_policy = ["Read-only analysis may run beside isolated tests."]
serial_policy = ["Serialize edits to the same file, API, or schema."]
failure_flow = ["Worker BLOCKED -> main", "Test FAILED -> main"]

[[model_registry.models]]
id = "economy-model"
availability_source = "runtime_model_registry"
capability_tier = "throughput"
cost_tier = "low"
reasoning_efforts = ["low", "medium"]
suitable_for = ["exploration", "testing"]

[[model_registry.models]]
id = "strong-model"
availability_source = "runtime_model_registry"
capability_tier = "strong"
cost_tier = "high"
reasoning_efforts = ["medium", "high"]
suitable_for = ["complex debugging", "architecture decisions"]

[[agents]]
name = "code_mapper"
file = ".codex/agents/code-mapper.toml"
description = "Read-only explorer for mapping implementation paths."
responsibilities = ["Map affected code and tests."]
boundaries = ["Do not edit files.", "Do not redefine requirements."]
model = "economy-model"
model_reasoning_effort = "low"
escalation_model = "strong-model"
escalation_reasoning_effort = "high"
escalation_triggers = ["Conflicting architecture artifacts"]
sandbox_mode = "read-only"
permission_boundaries = ["Read repository files only."]
skills = []
tools = ["repository search", "file read"]
inputs = ["Task Contract", "AGENTS.md"]
outputs = ["Evidence map with exact file references"]
invoke_when = ["Before editing an unfamiliar module"]
parallel_groups = ["read-analysis"]
serializes_with = []
cost_tier = "low"
managed = true
'''


CONFIG_TOML = '''[agents]
enabled = true
max_concurrent_threads_per_session = 2
'''


def agent_manifest(name: str, file: str) -> str:
    """Return a complete secondary Agent manifest table for ordering tests."""
    return f'''

[[agents]]
name = "{name}"
file = "{file}"
description = "Read-only explorer for mapping implementation paths."
responsibilities = ["Map affected code and tests."]
boundaries = ["Do not edit files.", "Do not redefine requirements."]
model = "economy-model"
model_reasoning_effort = "low"
escalation_model = "strong-model"
escalation_reasoning_effort = "high"
escalation_triggers = ["Conflicting architecture artifacts"]
sandbox_mode = "read-only"
permission_boundaries = ["Read repository files only."]
skills = []
tools = ["repository search", "file read"]
inputs = ["Task Contract", "AGENTS.md"]
outputs = ["Evidence map with exact file references"]
invoke_when = ["Before editing an unfamiliar module"]
parallel_groups = ["read-analysis"]
serializes_with = []
cost_tier = "low"
managed = true
'''


def manifest_with_reversed_models() -> str:
    """Return the fixture manifest with only the model tables reordered."""
    first = MANIFEST_TOML.index("[[model_registry.models]]")
    second = MANIFEST_TOML.index("[[model_registry.models]]", first + 1)
    agents = MANIFEST_TOML.index("[[agents]]")
    return (
        MANIFEST_TOML[:first]
        + MANIFEST_TOML[second:agents]
        + MANIFEST_TOML[first:second]
        + MANIFEST_TOML[agents:]
    )


class TeamValidatorTests(unittest.TestCase):
    """Exercise validation, ownership, registry, and idempotency checks."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".codex" / "agents").mkdir(parents=True)
        artifact = self.root / "ai_docs" / "notes" / "20260813-0000_product-spec.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# Product Spec\n", encoding="utf-8")
        (self.root / ".codex" / "agent-team.toml").write_text(
            MANIFEST_TOML,
            encoding="utf-8",
        )
        (self.root / ".codex" / "config.toml").write_text(CONFIG_TOML, encoding="utf-8")
        (self.root / ".codex" / "agents" / "code-mapper.toml").write_text(
            AGENT_TOML,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def validate(self) -> dict[str, object]:
        """Run the validator against the isolated fixture project."""
        return TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            runtime_sandbox="read-only",
            runtime_approval_policy="on-request",
            require_runtime_permissions=True,
        ).validate()

    def test_valid_team_passes_and_fingerprint_is_stable(self) -> None:
        first = self.validate()
        second = self.validate()
        self.assertEqual(first["status"], "PASS", first["errors"])
        self.assertEqual(first["configuration_status"], "PASS")
        self.assertEqual(first["runtime_model_availability"]["status"], "VERIFIED")
        self.assertEqual(first["runtime_permissions"]["status"], "VERIFIED")
        self.assertEqual(
            first["runtime_permissions"]["agents"][0]["configured_sandbox_default"],
            "read-only",
        )
        self.assertEqual(
            first["runtime_permissions"]["agents"][0]["comparison_status"],
            "MATCH",
        )
        self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_last_changed_at_must_be_rfc3339(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'last_changed_at = "2026-08-13T16:31:00+08:00"',
                'last_changed_at = "August 13, 2026"',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("valid RFC 3339 timestamp" in error for error in report["errors"]),
            report["errors"],
        )

    def test_project_artifact_must_be_a_file(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]',
                'artifact_paths = ["ai_docs/notes"]',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("project artifact must be a file" in error for error in report["errors"]),
            report["errors"],
        )

    def test_model_registry_must_be_sorted_by_id(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(manifest_with_reversed_models(), encoding="utf-8")
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("models must be sorted by id" in error for error in report["errors"]),
            report["errors"],
        )

    def test_agents_must_be_sorted_by_name(self) -> None:
        second_agent = self.root / ".codex" / "agents" / "analysis-worker.toml"
        second_agent.write_text(
            AGENT_TOML.replace('name = "code_mapper"', 'name = "analysis_worker"'),
            encoding="utf-8",
        )
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML
            + agent_manifest("analysis_worker", ".codex/agents/analysis-worker.toml"),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("agents must be sorted by name" in error for error in report["errors"]),
            report["errors"],
        )

    def test_multiple_agents_cannot_reference_the_same_file(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML
            + agent_manifest("verification_worker", ".codex/agents/code-mapper.toml"),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("referenced by multiple manifest Agents" in error for error in report["errors"]),
            report["errors"],
        )

    def test_escalation_assignment_must_be_strictly_stronger(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'escalation_model = "strong-model"\n'
                'escalation_reasoning_effort = "high"',
                'escalation_model = "economy-model"\n'
                'escalation_reasoning_effort = "low"',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("must be strictly stronger" in error for error in report["errors"]),
            report["errors"],
        )

    def test_same_model_with_higher_effort_is_a_valid_escalation(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'escalation_model = "strong-model"\n'
                'escalation_reasoning_effort = "high"',
                'escalation_model = "economy-model"\n'
                'escalation_reasoning_effort = "medium"',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_manifest_prose_does_not_count_as_availability_evidence(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'availability_source = "runtime_model_registry"',
                'availability_source = "I think this model exists."',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("availability_source must be one of" in error for error in report["errors"]),
            report["errors"],
        )

    def test_missing_external_runtime_evidence_is_unverified(self) -> None:
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "UNVERIFIED")
        self.assertTrue(
            any("evidence was not supplied" in error for error in report["errors"]),
            report["errors"],
        )

    def test_model_absent_from_runtime_evidence_fails(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model"},
            availability_source="runtime_model_registry",
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "FAIL")
        self.assertEqual(
            report["runtime_model_availability"]["missing_models"],
            ["strong-model"],
        )

    def test_manifest_and_external_evidence_sources_must_match(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'availability_source = "runtime_model_registry"',
                'availability_source = "codex_model_selector"',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "FAIL")
        self.assertTrue(
            any("do not match" in error for error in report["errors"]),
            report["errors"],
        )

    def test_cli_reports_configuration_and_runtime_status_separately(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--root",
                str(self.root),
                "--availability-source",
                "runtime_model_registry",
                "--available-model",
                "economy-model",
                "--available-model",
                "strong-model",
                "--runtime-sandbox",
                "read-only",
                "--runtime-approval-policy",
                "on-request",
                "--require-runtime-permissions",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "VERIFIED")
        self.assertEqual(report["runtime_permissions"]["status"], "VERIFIED")

    def test_required_runtime_permissions_without_evidence_are_unverified(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            require_runtime_permissions=True,
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "VERIFIED")
        self.assertEqual(report["runtime_permissions"]["status"], "UNVERIFIED")
        self.assertTrue(
            any("permission evidence was not supplied" in error for error in report["errors"]),
            report["errors"],
        )

    def test_parent_runtime_sandbox_override_mismatch_fails(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            runtime_sandbox="workspace-write",
            runtime_approval_policy="on-request",
            require_runtime_permissions=True,
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_permissions"]["status"], "MISMATCH")
        self.assertEqual(
            report["runtime_permissions"]["agents"][0]["comparison_status"],
            "MISMATCH",
        )
        self.assertEqual(
            report["runtime_permissions"]["observed_parent"]["sandbox_mode"],
            "workspace-write",
        )

    def test_behavioral_boundaries_are_reported_as_instruction_only(self) -> None:
        report = self.validate()
        runtime_permissions = report["runtime_permissions"]
        self.assertEqual(
            runtime_permissions["behavioral_boundary_enforcement"],
            "developer_instructions_only",
        )
        self.assertEqual(
            runtime_permissions["agents"][0]["behavioral_boundaries"],
            ["Do not edit files.", "Do not redefine requirements."],
        )

    def test_missing_registry_model_fails(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace('model = "economy-model"', 'model = "unknown-model"'),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("absent from the registry" in error for error in report["errors"]),
            report["errors"],
        )

    def test_managed_orphan_agent_fails(self) -> None:
        orphan = self.root / ".codex" / "agents" / "orphan.toml"
        orphan.write_text(
            AGENT_TOML.replace('name = "code_mapper"', 'name = "orphan"'),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("missing from the manifest" in error for error in report["errors"]),
            report["errors"],
        )

    def test_user_managed_agent_is_preserved_and_allowed(self) -> None:
        custom = self.root / ".codex" / "agents" / "user-agent.toml"
        custom.write_text(
            textwrap.dedent(
                '''\
                name = "user_agent"
                description = "A user-owned Agent."
                developer_instructions = "Do user-owned work."
                '''
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_config_concurrency_mismatch_fails(self) -> None:
        config_path = self.root / ".codex" / "config.toml"
        config_path.write_text(CONFIG_TOML.replace("= 2", "= 3"), encoding="utf-8")
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("concurrency does not match" in error for error in report["errors"]),
            report["errors"],
        )

    def test_missing_skill_binding_fails(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace('skills = []', 'skills = ["missing-skill"]'),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("does not resolve to a Skill" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

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

from validate_team import HostPermissionEvidence, MANAGED_HEADER, TeamValidator  # noqa: E402


AGENT_TOML = f'''{MANAGED_HEADER}
name = "code_mapper"
description = "Read-only explorer for mapping implementation paths."
model = "economy-model"
model_reasoning_effort = "low"
sandbox_mode = "read-only"
developer_instructions = """
Responsibilities:
- Map affected code and tests.
Boundaries:
- Do not edit files.
- Do not redefine requirements.
- Read repository files only.
Inputs:
- AGENTS.md
- Task Contract
Outputs:
- Evidence map with exact file references
Escalation:
- Conflicting architecture artifacts
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

[cost_profile]
objective = "minimize_total_cost"
total_cost_formula = "model_call_cost + coordination_overhead_cost"
baseline = "single-agent"
measurement_scope = "per-task"
metrics = ["agent_invocations", "coordination_overhead_cost", "coordination_tokens", "latency_ms", "model_call_cost", "model_input_tokens", "model_output_tokens", "success_rate", "total_cost"]

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
reasoning_efforts = ["high", "medium"]
suitable_for = ["architecture decisions", "complex debugging"]

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
tools = ["file read", "repository search"]
inputs = ["AGENTS.md", "Task Contract"]
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
tools = ["file read", "repository search"]
inputs = ["AGENTS.md", "Task Contract"]
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


def host_permission_evidence(
    *,
    sandbox: str = "read-only",
    approval_policy: str = "on-request",
    parent_sandbox: str = "read-only",
) -> HostPermissionEvidence:
    """Return trusted host evidence for the default fixture Agent."""
    return HostPermissionEvidence(
        source="spawn_session_metadata",
        agent_sandboxes={"code_mapper": sandbox},
        agent_approval_policies={"code_mapper": approval_policy},
        parent_sandbox=parent_sandbox,
        parent_approval_policy="on-request",
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
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0-alpha.6.5",
            codex_version_source="codex_cli",
        ).validate()

    def test_valid_team_passes_and_fingerprint_is_stable(self) -> None:
        first = self.validate()
        second = self.validate()
        self.assertEqual(first["status"], "PASS", first["errors"])
        self.assertEqual(first["configuration_status"], "PASS")
        self.assertEqual(
            first["runtime_model_availability"]["status"],
            "CALLER_ASSERTED",
        )
        self.assertEqual(first["runtime_permissions"]["status"], "HOST_VERIFIED")
        self.assertEqual(first["readiness_status"], "AGENT_TEAM_READY")
        self.assertEqual(first["runtime_codex_compatibility"]["status"], "VERIFIED")
        self.assertEqual(
            first["runtime_codex_compatibility"]["normalized_version"],
            "0.147.0-alpha.6.5",
        )
        self.assertEqual(
            first["runtime_codex_compatibility"]["release_channel"],
            "prerelease",
        )
        self.assertEqual(
            first["runtime_permissions"]["agents"][0]["configured_sandbox_default"],
            "read-only",
        )
        self.assertEqual(
            first["runtime_permissions"]["agents"][0]["comparison_status"],
            "MATCH",
        )
        self.assertEqual(
            first["runtime_permissions"]["agents"][0]["observed_effective"],
            {"sandbox_mode": "read-only", "approval_policy": "on-request"},
        )
        self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_successful_model_probe_upgrades_runtime_status(self) -> None:
        report = TeamValidator(
            self.root,
            probed_models={"economy-model", "strong-model"},
            model_probe_source="successful_model_probe",
        ).validate()
        self.assertEqual(
            report["runtime_model_availability"]["status"],
            "VERIFIED",
        )
        self.assertEqual(
            report["runtime_model_availability"]["evidence_level"],
            "successful_model_probe",
        )

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

    def test_cost_profile_is_required(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace("[cost_profile]", "[not_cost_profile]"),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("manifest.cost_profile must be" in error for error in report["errors"]),
            report["errors"],
        )

    def test_set_semantic_arrays_must_be_sorted_and_unique(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'priorities = ["cost", "quality"]',
                'priorities = ["quality", "cost", "cost"]',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("must be sorted and contain no duplicates" in error for error in report["errors"]),
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

    def test_serializes_with_must_reference_known_agents(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                "serializes_with = []",
                'serializes_with = ["missing_worker"]',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("references an unknown Agent" in error for error in report["errors"]),
            report["errors"],
        )

    def test_serializes_with_must_be_symmetric(self) -> None:
        second_agent = self.root / ".codex" / "agents" / "verification-worker.toml"
        second_agent.write_text(
            AGENT_TOML.replace('name = "code_mapper"', 'name = "verification_worker"'),
            encoding="utf-8",
        )
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                "serializes_with = []",
                'serializes_with = ["verification_worker"]',
            )
            + agent_manifest(
                "verification_worker",
                ".codex/agents/verification-worker.toml",
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any("serialization must be symmetric" in error for error in report["errors"]),
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
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
        )
        self.assertEqual(report["runtime_model_availability"]["status"], "UNVERIFIED")
        self.assertTrue(report["runtime_model_availability"]["configuration_usable"])
        self.assertEqual(report["runtime_model_availability"]["errors"], [])

    def test_configuration_only_model_evidence_can_still_be_ready(self) -> None:
        report = TeamValidator(
            self.root,
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0-alpha.6.5",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "UNVERIFIED")
        self.assertTrue(report["runtime_model_availability"]["configuration_usable"])
        self.assertEqual(report["readiness_status"], "AGENT_TEAM_READY")

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
            report["runtime_model_availability"]["catalog"]["missing_models"],
            ["strong-model"],
        )

    def test_catalog_assertion_is_distinct_from_manifest_provenance(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="codex_model_selector",
        ).validate()
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(
            report["runtime_model_availability"]["status"],
            "CALLER_ASSERTED",
        )
        self.assertEqual(
            report["runtime_model_availability"]["declared_sources"],
            ["runtime_model_registry"],
        )

    def test_partial_probe_evidence_fails_without_downgrading_to_asserted(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            probed_models={"economy-model"},
            model_probe_source="successful_model_probe",
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "FAIL")
        self.assertTrue(
            any("do not all have a successful probe" in error for error in report["errors"]),
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
                "--permission-evidence-source",
                "spawn_session_metadata",
                "--agent-runtime-sandbox",
                "code_mapper=read-only",
                "--agent-runtime-approval-policy",
                "code_mapper=on-request",
                "--require-runtime-permissions",
                "--codex-version",
                "codex-cli 0.147.0-alpha.6.5",
                "--codex-version-source",
                "codex_cli",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(
            report["runtime_model_availability"]["status"],
            "CALLER_ASSERTED",
        )
        self.assertEqual(report["runtime_permissions"]["status"], "CALLER_ASSERTED")
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
        )
        self.assertTrue(
            any("cannot satisfy strict" in error for error in report["errors"]),
            report["errors"],
        )
        self.assertEqual(report["runtime_codex_compatibility"]["status"], "VERIFIED")

    def test_caller_asserted_permissions_allow_configuration_only_readiness(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            agent_runtime_sandboxes={"code_mapper": "read-only"},
            agent_runtime_approval_policies={"code_mapper": "on-request"},
            permission_evidence_source="spawn_session_metadata",
            codex_version="codex-cli 0.147.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["runtime_permissions"]["status"], "CALLER_ASSERTED")
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
        )

    def test_invalid_host_approval_policy_fails(self) -> None:
        report = TeamValidator(
            self.root,
            host_permission_evidence=host_permission_evidence(
                approval_policy="approve-everything"
            ),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["runtime_permissions"]["status"], "MISMATCH")
        self.assertTrue(
            any("observed approval policy must be one of" in error for error in report["errors"]),
            report["errors"],
        )

    def test_missing_codex_version_evidence_is_unverified(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_codex_compatibility"]["status"], "UNVERIFIED")
        self.assertTrue(
            any("version evidence was not supplied" in error for error in report["errors"]),
            report["errors"],
        )

    def test_minimum_stable_codex_version_passes(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.145.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["runtime_codex_compatibility"]["status"], "VERIFIED")

    def test_prerelease_of_minimum_codex_version_is_unsupported_old(self) -> None:
        report = TeamValidator(
            self.root,
            codex_version="codex-cli 0.145.0-alpha.1",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(
            report["runtime_codex_compatibility"]["status"],
            "UNSUPPORTED_OLD",
        )

    def test_codex_below_minimum_version_is_unsupported_old(self) -> None:
        report = TeamValidator(
            self.root,
            codex_version="codex-cli 0.144.6",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(
            report["runtime_codex_compatibility"]["status"],
            "UNSUPPORTED_OLD",
        )

    def test_newer_unreviewed_codex_series_is_blocked(self) -> None:
        report = TeamValidator(
            self.root,
            codex_version="codex-cli 0.148.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(
            report["runtime_codex_compatibility"]["status"],
            "UNREVIEWED_NEWER",
        )
        self.assertTrue(
            any("maximum reviewed series" in error for error in report["errors"]),
            report["errors"],
        )

    def test_malformed_codex_version_is_unverified(self) -> None:
        report = TeamValidator(
            self.root,
            codex_version="Codex from sometime recently",
            codex_version_source="host_runtime",
        ).validate()
        self.assertEqual(report["runtime_codex_compatibility"]["status"], "UNVERIFIED")
        self.assertTrue(
            any("not parseable" in error for error in report["errors"]),
            report["errors"],
        )

    def test_required_runtime_permissions_without_evidence_are_unverified(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            require_runtime_permissions=True,
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(
            report["runtime_model_availability"]["status"],
            "CALLER_ASSERTED",
        )
        self.assertEqual(report["runtime_permissions"]["status"], "UNVERIFIED")
        self.assertTrue(
            any("permission evidence source was not supplied" in error for error in report["errors"]),
            report["errors"],
        )

    def test_agent_runtime_sandbox_mismatch_fails(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            runtime_sandbox="workspace-write",
            runtime_approval_policy="on-request",
            agent_runtime_sandboxes={"code_mapper": "workspace-write"},
            agent_runtime_approval_policies={"code_mapper": "on-request"},
            permission_evidence_source="spawn_session_metadata",
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

    def test_parent_permission_context_does_not_force_one_team_sandbox(self) -> None:
        report = TeamValidator(
            self.root,
            available_models={"economy-model", "strong-model"},
            availability_source="runtime_model_registry",
            host_permission_evidence=host_permission_evidence(
                parent_sandbox="workspace-write"
            ),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["runtime_permissions"]["status"], "HOST_VERIFIED")

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

    def test_developer_instructions_require_all_contract_sections(self) -> None:
        agent_path = self.root / ".codex" / "agents" / "code-mapper.toml"
        agent_path.write_text(
            AGENT_TOML.replace(
                "Outputs:\n- Evidence map with exact file references\n",
                "",
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("non-empty Outputs: section" in error for error in report["errors"]),
            report["errors"],
        )

    def test_developer_instructions_must_cover_manifest_items(self) -> None:
        agent_path = self.root / ".codex" / "agents" / "code-mapper.toml"
        agent_path.write_text(
            AGENT_TOML.replace(
                "- Do not edit files.",
                "- Editing is allowed when convenient.",
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("does not cover Manifest item: Do not edit files." in error for error in report["errors"]),
            report["errors"],
        )

    def test_manifest_symbolic_link_is_rejected(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        target = self.root / "manifest-target.toml"
        target.write_text(MANIFEST_TOML, encoding="utf-8")
        manifest_path.unlink()
        manifest_path.symlink_to(target)
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must not use a symbolic link" in error for error in report["errors"]),
            report["errors"],
        )

    def test_agent_symbolic_link_is_rejected(self) -> None:
        agent_path = self.root / ".codex" / "agents" / "code-mapper.toml"
        target = self.root / "agent-target.toml"
        target.write_text(AGENT_TOML, encoding="utf-8")
        agent_path.unlink()
        agent_path.symlink_to(target)
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must not use a symbolic link" in error for error in report["errors"]),
            report["errors"],
        )

    def test_project_config_symbolic_link_is_rejected(self) -> None:
        config_path = self.root / ".codex" / "config.toml"
        target = self.root / "config-target.toml"
        target.write_text(CONFIG_TOML, encoding="utf-8")
        config_path.unlink()
        config_path.symlink_to(target)
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must not use a symbolic link" in error for error in report["errors"]),
            report["errors"],
        )

    def test_agent_parent_directory_symbolic_link_is_rejected(self) -> None:
        agents_dir = self.root / ".codex" / "agents"
        target = self.root / "real-agents"
        agents_dir.rename(target)
        agents_dir.symlink_to(target, target_is_directory=True)
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must not use a symbolic link" in error for error in report["errors"]),
            report["errors"],
        )

    def test_project_artifact_symbolic_link_is_rejected(self) -> None:
        artifact = self.root / "ai_docs" / "notes" / "20260813-0000_product-spec.md"
        target = self.root / "artifact-target.md"
        target.write_text("# Product Spec\n", encoding="utf-8")
        artifact.unlink()
        artifact.symlink_to(target)
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must not use a symbolic link" in error for error in report["errors"]),
            report["errors"],
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

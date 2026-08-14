#!/usr/bin/env python3
"""Regression tests for the subagent-creator team validator.

The tests create isolated temporary Codex projects, exercise successful and
failing manifests, and print the standard unittest exit status.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = PROJECT_ROOT / "skills" / "subagent-creator"
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_team.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_team import (  # noqa: E402
    HostCodexVersionEvidence,
    HostModelEvidence,
    HostPermissionEvidence,
    MANAGED_HEADER,
    PROJECT_AGENTS_MANAGED_BLOCK,
    TeamValidator,
)


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
- Return conflicting architecture artifacts to the main Agent
"""
'''


MANIFEST_TOML = '''schema_version = 4
generator = "subagent-creator"
status = "ready"
last_changed_at = "2026-08-13T16:31:00+08:00"
scope = "project"

[context]
summary = "Small single-module implementation project."
artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]
constraints = ["Preserve the public contract."]

[orchestration]
max_concurrent_agents = 2
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
model = "economy-model"
model_reasoning_effort = "low"
escalation_model = "strong-model"
escalation_reasoning_effort = "high"
sandbox_mode = "read-only"
skills = []
invoke_when = ["Before editing an unfamiliar module"]
serializes_with = []
cost_tier = "low"
managed = true
'''


CONFIG_TOML = '''[agents]
enabled = true
max_concurrent_threads_per_session = 2
'''


PERSONAL_MANIFEST_TOML = MANIFEST_TOML.replace(
    'scope = "project"',
    'scope = "personal"',
).replace(
    'artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]',
    "artifact_paths = []",
).replace(
    'file = ".codex/agents/code-mapper.toml"',
    'file = "agents/code-mapper.toml"',
).replace(
    'summary = "Small single-module implementation project."',
    'summary = "Reusable personal code-mapping Agent profile."',
)


def agent_manifest(name: str, file: str) -> str:
    """Return a complete secondary Agent manifest table for ordering tests."""
    return f'''

[[agents]]
name = "{name}"
file = "{file}"
description = "Read-only explorer for mapping implementation paths."
model = "economy-model"
model_reasoning_effort = "low"
escalation_model = "strong-model"
escalation_reasoning_effort = "high"
sandbox_mode = "read-only"
skills = []
invoke_when = ["Before editing an unfamiliar module"]
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


def host_model_evidence(*, probed: bool = False) -> HostModelEvidence:
    """Return trusted model evidence for every model in the default fixture."""
    models = frozenset({"economy-model", "strong-model"})
    return HostModelEvidence(
        catalog_source="runtime_model_registry",
        available_models=models,
        probe_source="successful_model_probe" if probed else None,
        probed_models=models if probed else frozenset(),
    )


def host_codex_version_evidence(
    version: str = "codex-cli 0.147.0-alpha.6.5",
) -> HostCodexVersionEvidence:
    """Return a Codex version observation from the trusted host boundary."""
    return HostCodexVersionEvidence(source="codex_cli", version=version)


class TeamValidatorTests(unittest.TestCase):
    """Exercise validation, ownership, registry, and idempotency checks."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_codex_home = os.environ.get("CODEX_HOME")
        self.isolated_codex_home = self.root / "isolated-codex-home"
        os.environ["CODEX_HOME"] = str(self.isolated_codex_home)
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
        (self.root / "AGENTS.md").write_text(
            f"# Project instructions\n\n{PROJECT_AGENTS_MANAGED_BLOCK}\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        if self.previous_codex_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = self.previous_codex_home
        self.temp_dir.cleanup()

    def prepare_personal_scope(self) -> Path:
        """Create an isolated Codex home containing one personal Agent team."""
        project_agent = self.root / ".codex" / "agents" / "code-mapper.toml"
        if project_agent.exists():
            project_agent.unlink()
        codex_home = self.root / "personal-codex-home"
        (codex_home / "agents").mkdir(parents=True)
        (codex_home / "subagent-creator").mkdir()
        (codex_home / "subagent-creator" / "agent-team.toml").write_text(
            PERSONAL_MANIFEST_TOML,
            encoding="utf-8",
        )
        (codex_home / "config.toml").write_text(CONFIG_TOML, encoding="utf-8")
        (codex_home / "agents" / "code-mapper.toml").write_text(
            AGENT_TOML,
            encoding="utf-8",
        )
        return codex_home

    def validate(self) -> dict[str, object]:
        """Run the validator against the isolated fixture project."""
        return TeamValidator(
            self.root,
            host_model_evidence=host_model_evidence(),
            host_permission_evidence=host_permission_evidence(),
            host_codex_version_evidence=host_codex_version_evidence(),
            require_runtime_permissions=True,
        ).validate()

    def test_valid_team_passes_and_fingerprint_is_stable(self) -> None:
        first = self.validate()
        second = self.validate()
        self.assertEqual(first["status"], "PASS", first["errors"])
        self.assertEqual(first["configuration_status"], "PASS")
        self.assertEqual(
            first["runtime_model_availability"]["status"],
            "HOST_VERIFIED",
        )
        self.assertEqual(first["runtime_permissions"]["status"], "HOST_VERIFIED")
        self.assertEqual(first["readiness_status"], "AGENT_TEAM_RUNTIME_READY")
        self.assertEqual(first["persistent_orchestration"]["status"], "PASS")
        self.assertEqual(
            first["runtime_codex_compatibility"]["status"],
            "HOST_VERIFIED",
        )
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
            "CALLER_PROBED",
        )
        self.assertEqual(
            report["runtime_model_availability"]["evidence_level"],
            "caller_reported_successful_model_probe",
        )

    def test_trusted_model_probes_upgrade_team_to_verified(self) -> None:
        report = TeamValidator(
            self.root,
            host_model_evidence=host_model_evidence(probed=True),
            host_permission_evidence=host_permission_evidence(),
            host_codex_version_evidence=host_codex_version_evidence(
                "codex-cli 0.147.0"
            ),
            require_model_verification=True,
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["readiness_status"], "AGENT_TEAM_VERIFIED")

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

    def test_set_semantic_arrays_must_be_sorted_and_unique(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'constraints = ["Preserve the public contract."]',
                'constraints = ["Keep APIs stable.", "Keep APIs stable."]',
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
        manifest = MANIFEST_TOML.replace(
            'escalation_model = "strong-model"\n'
            'escalation_reasoning_effort = "high"',
            'escalation_model = "economy-model"\n'
            'escalation_reasoning_effort = "medium"',
        )
        first_model = manifest.index("[[model_registry.models]]")
        strong_model = manifest.index("[[model_registry.models]]", first_model + 1)
        agents = manifest.index("[[agents]]")
        manifest_path.write_text(
            manifest[:strong_model] + manifest[agents:],
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_manifest_v4_allows_no_escalation_model(self) -> None:
        manifest = MANIFEST_TOML.replace(
            'escalation_model = "strong-model"\n'
            'escalation_reasoning_effort = "high"\n',
            "",
        )
        first_model = manifest.index("[[model_registry.models]]")
        strong_model = manifest.index("[[model_registry.models]]", first_model + 1)
        agents = manifest.index("[[agents]]")
        manifest = manifest[:strong_model] + manifest[agents:]
        (self.root / ".codex" / "agent-team.toml").write_text(
            manifest,
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_manifest_v4_requires_escalation_pair(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace('escalation_model = "strong-model"\n', ""),
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must be supplied together" in error for error in report["errors"]),
            report["errors"],
        )

    def test_unused_registry_model_is_rejected(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'escalation_model = "strong-model"\n'
                'escalation_reasoning_effort = "high"\n',
                "",
            ),
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("models not assigned" in error for error in report["errors"]),
            report["errors"],
        )

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
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["local_codex_schema"]["status"], "PASS")
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
        )
        self.assertEqual(report["runtime_model_availability"]["status"], "UNVERIFIED")
        self.assertTrue(report["runtime_model_availability"]["configuration_usable"])
        self.assertEqual(report["runtime_model_availability"]["errors"], [])
        self.assertEqual(report["runtime_codex_compatibility"]["status"], "UNVERIFIED")
        self.assertEqual(report["runtime_codex_compatibility"]["errors"], [])

    def test_default_cli_returns_configuration_ready_without_host_evidence(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--root",
                str(self.root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["scope"]["requested"], "project")
        self.assertEqual(report["scope"]["display_name"], "project-level")
        self.assertEqual(report["scope"]["manifest"], "project")
        self.assertEqual(report["scope"]["authorization_status"], "NOT_REQUIRED")
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
        )

    def test_nonempty_agents_override_is_the_persistent_source(self) -> None:
        override_path = self.root / "AGENTS.override.md"
        override_path.write_text(
            f"# Temporary project override\n\n{PROJECT_AGENTS_MANAGED_BLOCK}\n",
            encoding="utf-8",
        )
        (self.root / "AGENTS.md").write_text(
            "# This file is shadowed by the override\n",
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "PASS", report["errors"])
        self.assertEqual(
            Path(report["persistent_orchestration"]["source"]).resolve(),
            override_path.resolve(),
        )

    def test_shadowed_agents_md_does_not_satisfy_persistent_wiring(self) -> None:
        (self.root / "AGENTS.override.md").write_text(
            "# Active override without the team bridge\n",
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("managed block" in error for error in report["errors"]),
            report["errors"],
        )

    def test_active_project_instructions_respect_size_limit(self) -> None:
        (self.root / "AGENTS.md").write_text(
            f"{PROJECT_AGENTS_MANAGED_BLOCK}\n" + ("x" * 33000),
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("project_doc_max_bytes" in error for error in report["errors"]),
            report["errors"],
        )

    def test_personal_scope_requires_explicit_authorization(self) -> None:
        codex_home = self.prepare_personal_scope()
        report = TeamValidator(
            self.root,
            scope="personal",
            codex_home=codex_home,
        ).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertEqual(report["scope"]["authorization_status"], "MISSING")
        self.assertTrue(
            any("explicit user declaration" in error for error in report["errors"]),
            report["errors"],
        )

    def test_explicit_personal_scope_passes_without_project_agents(self) -> None:
        codex_home = self.prepare_personal_scope()
        project_agents = self.root / ".codex" / "agents"
        for path in project_agents.glob("*.toml"):
            path.unlink()
        report = TeamValidator(
            self.root,
            scope="personal",
            codex_home=codex_home,
            personal_scope_authorized=True,
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["scope"]["requested"], "personal")
        self.assertEqual(report["scope"]["display_name"], "global")
        self.assertEqual(report["scope"]["manifest"], "personal")
        self.assertEqual(report["scope"]["authorization_status"], "CALLER_ASSERTED")
        self.assertEqual(
            Path(report["scope"]["agents_dir"]),
            codex_home / "agents",
        )
        self.assertEqual(
            report["persistent_orchestration"]["status"],
            "NOT_APPLICABLE_GLOBAL_ROLE_LIBRARY",
        )

    def test_global_role_library_cannot_satisfy_runtime_readiness(self) -> None:
        codex_home = self.prepare_personal_scope()
        report = TeamValidator(
            self.root,
            scope="personal",
            codex_home=codex_home,
            personal_scope_authorized=True,
            host_model_evidence=host_model_evidence(),
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
        )
        self.assertTrue(
            any("runtime readiness Gate" in error for error in report["errors"]),
            report["errors"],
        )

    def test_personal_scope_cli_requires_authorization_flag(self) -> None:
        codex_home = self.prepare_personal_scope()
        base_command = [
            sys.executable,
            str(VALIDATOR_PATH),
            "--root",
            str(self.root),
            "--scope",
            "personal",
            "--codex-home",
            str(codex_home),
            "--json",
        ]
        rejected = subprocess.run(
            base_command,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(
            json.loads(rejected.stdout)["scope"]["authorization_status"],
            "MISSING",
        )

        accepted = subprocess.run(
            [*base_command[:-1], "--personal-scope-authorized", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertEqual(
            json.loads(accepted.stdout)["scope"]["authorization_status"],
            "CALLER_ASSERTED",
        )

    def test_personal_manifest_cannot_persist_project_artifacts(self) -> None:
        codex_home = self.prepare_personal_scope()
        manifest_path = codex_home / "subagent-creator" / "agent-team.toml"
        manifest_path.write_text(
            PERSONAL_MANIFEST_TOML.replace(
                "artifact_paths = []",
                'artifact_paths = ["README.md"]',
            ),
            encoding="utf-8",
        )
        report = TeamValidator(
            self.root,
            scope="personal",
            codex_home=codex_home,
            personal_scope_authorized=True,
        ).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("must be empty" in error for error in report["errors"]),
            report["errors"],
        )

    def test_cross_scope_agent_name_conflict_is_rejected(self) -> None:
        codex_home = self.prepare_personal_scope()
        project_agents = self.root / ".codex" / "agents"
        (project_agents / "same-name.toml").write_text(
            AGENT_TOML,
            encoding="utf-8",
        )
        report = TeamValidator(
            self.root,
            scope="personal",
            codex_home=codex_home,
            personal_scope_authorized=True,
        ).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("conflicts with a project-level" in error for error in report["errors"]),
            report["errors"],
        )

    def test_project_scope_checks_default_codex_home_for_conflicts(self) -> None:
        global_agents = self.isolated_codex_home / "agents"
        global_agents.mkdir(parents=True)
        (global_agents / "code-mapper.toml").write_text(
            AGENT_TOML,
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("conflicts with a global" in error for error in report["errors"]),
            report["errors"],
        )

    def test_global_agent_cannot_bind_project_internal_skill(self) -> None:
        codex_home = self.prepare_personal_scope()
        project_skill = self.root / "project-only-skill"
        project_skill.mkdir()
        (project_skill / "SKILL.md").write_text(
            "---\nname: project-only-skill\ndescription: Project only.\n---\n",
            encoding="utf-8",
        )
        manifest_path = codex_home / "subagent-creator" / "agent-team.toml"
        manifest_path.write_text(
            PERSONAL_MANIFEST_TOML.replace(
                "skills = []",
                f'skills = ["{project_skill}"]',
            ),
            encoding="utf-8",
        )
        agent_path = codex_home / "agents" / "code-mapper.toml"
        agent_path.write_text(
            AGENT_TOML
            + f'\n[[skills.config]]\npath = "{project_skill}"\nenabled = true\n',
            encoding="utf-8",
        )
        report = TeamValidator(
            self.root,
            scope="personal",
            codex_home=codex_home,
            personal_scope_authorized=True,
        ).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("project-internal Skill" in error for error in report["errors"]),
            report["errors"],
        )

    def test_runtime_readiness_requires_trusted_model_catalog(self) -> None:
        report = TeamValidator(
            self.root,
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0-alpha.6.5",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(report["runtime_model_availability"]["status"], "UNVERIFIED")
        self.assertTrue(report["runtime_model_availability"]["configuration_usable"])
        self.assertEqual(
            report["readiness_status"],
            "AGENT_TEAM_CONFIGURATION_READY",
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
        self.assertEqual(
            report["runtime_codex_compatibility"]["status"],
            "CALLER_ASSERTED",
        )

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
            host_model_evidence=host_model_evidence(),
            host_permission_evidence=host_permission_evidence(),
            host_codex_version_evidence=host_codex_version_evidence(
                "codex-cli 0.145.0"
            ),
            require_runtime_permissions=True,
        ).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(
            report["runtime_codex_compatibility"]["status"],
            "HOST_VERIFIED",
        )

    def test_runtime_readiness_requires_trusted_codex_version(self) -> None:
        report = TeamValidator(
            self.root,
            host_model_evidence=host_model_evidence(),
            host_permission_evidence=host_permission_evidence(),
            require_runtime_permissions=True,
            codex_version="codex-cli 0.147.0",
            codex_version_source="codex_cli",
        ).validate()
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["configuration_status"], "PASS")
        self.assertEqual(
            report["runtime_codex_compatibility"]["status"],
            "CALLER_ASSERTED",
        )
        self.assertTrue(
            any("HostCodexVersionEvidence" in error for error in report["errors"]),
            report["errors"],
        )

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
            host_model_evidence=host_model_evidence(),
            host_permission_evidence=host_permission_evidence(
                parent_sandbox="workspace-write"
            ),
            host_codex_version_evidence=host_codex_version_evidence(
                "codex-cli 0.147.0"
            ),
            require_runtime_permissions=True,
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
            [
                "Do not edit files.",
                "Do not redefine requirements.",
                "Read repository files only.",
            ],
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

    def test_escalation_section_must_route_back_to_main_agent(self) -> None:
        agent_path = self.root / ".codex" / "agents" / "code-mapper.toml"
        agent_path.write_text(
            AGENT_TOML.replace(
                "- Return conflicting architecture artifacts to the main Agent",
                "- Retry indefinitely",
            ),
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("route blocked or failed work" in error for error in report["errors"]),
            report["errors"],
        )

    def test_native_instructions_are_the_behavioral_source_of_truth(self) -> None:
        agent_path = self.root / ".codex" / "agents" / "code-mapper.toml"
        agent_path.write_text(
            AGENT_TOML.replace(
                "- Do not edit files.",
                "- Editing is allowed when convenient.",
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["configuration_status"], "PASS", report["errors"])
        self.assertEqual(
            report["runtime_permissions"]["agents"][0]["behavioral_boundaries"],
            [
                "Editing is allowed when convenient.",
                "Do not redefine requirements.",
                "Read repository files only.",
            ],
        )

    def test_managed_agent_rejects_unknown_codex_fields(self) -> None:
        agent_path = self.root / ".codex" / "agents" / "code-mapper.toml"
        agent_path.write_text(
            AGENT_TOML.replace(
                'sandbox_mode = "read-only"',
                'sandbox_mode = "read-only"\nfuture_setting = true',
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["local_codex_schema"]["status"], "FAIL")
        self.assertTrue(
            any("unsupported fields" in error for error in report["errors"]),
            report["errors"],
        )

    def test_project_agents_table_rejects_unknown_scalar_settings(self) -> None:
        config_path = self.root / ".codex" / "config.toml"
        config_path.write_text(CONFIG_TOML + "future_setting = true\n", encoding="utf-8")
        report = self.validate()
        self.assertEqual(report["local_codex_schema"]["status"], "FAIL")
        self.assertTrue(
            any("not a supported Agent setting" in error for error in report["errors"]),
            report["errors"],
        )

    def test_legacy_manifest_v1_remains_read_compatible(self) -> None:
        legacy = MANIFEST_TOML.replace("schema_version = 4", "schema_version = 1")
        legacy = legacy.replace('scope = "project"\n', "")
        legacy = legacy.replace("[context]\n", "[project]\n")
        legacy = legacy.replace(
            "[project]\n",
            '[project]\nsize = "small"\ncomplexity = ["single-module"]\n',
        )
        legacy = legacy.replace(
            'description = "Read-only explorer for mapping implementation paths."\nmodel =',
            'description = "Read-only explorer for mapping implementation paths."\n'
            'boundaries = ["Do not edit files."]\nmodel =',
        )
        (self.root / ".codex" / "agent-team.toml").write_text(
            legacy,
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(
            report["persistent_orchestration"]["status"],
            "LEGACY_UNVERIFIED",
        )

    def test_legacy_manifest_v2_remains_read_compatible(self) -> None:
        legacy = MANIFEST_TOML.replace("schema_version = 4", "schema_version = 2")
        legacy = legacy.replace('scope = "project"\n', "")
        legacy = legacy.replace("[context]\n", "[project]\n")
        (self.root / ".codex" / "agent-team.toml").write_text(
            legacy,
            encoding="utf-8",
        )
        report = TeamValidator(self.root).validate()
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(
            report["persistent_orchestration"]["status"],
            "LEGACY_UNVERIFIED",
        )

    def test_manifest_v3_rejects_legacy_duplicate_fields(self) -> None:
        manifest = MANIFEST_TOML.replace("schema_version = 4", "schema_version = 3").replace(
            "[context]\n",
            '[context]\nsize = "small"\n',
        )
        (self.root / ".codex" / "agent-team.toml").write_text(
            manifest,
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("unsupported fields" in error for error in report["errors"]),
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

    def test_project_root_symbolic_link_is_rejected(self) -> None:
        linked_root = self.root.parent / f"{self.root.name}-linked-root"
        linked_root.symlink_to(self.root, target_is_directory=True)
        try:
            report = TeamValidator(linked_root).validate()
        finally:
            linked_root.unlink()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("root must not be a symbolic link" in error for error in report["errors"]),
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

    def test_model_cost_tier_must_be_relative_category(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'cost_tier = "low"',
                'cost_tier = "bargain"',
                1,
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("cost_tier is invalid" in error for error in report["errors"]),
            report["errors"],
        )

    def test_agent_cost_tier_must_match_assigned_model(self) -> None:
        manifest_path = self.root / ".codex" / "agent-team.toml"
        manifest_path.write_text(
            MANIFEST_TOML.replace(
                'serializes_with = []\ncost_tier = "low"',
                'serializes_with = []\ncost_tier = "medium"',
                1,
            ),
            encoding="utf-8",
        )
        report = self.validate()
        self.assertEqual(report["configuration_status"], "FAIL")
        self.assertTrue(
            any("cost_tier does not match" in error for error in report["errors"]),
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

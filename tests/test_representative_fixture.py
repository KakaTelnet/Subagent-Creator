#!/usr/bin/env python3
"""Exercise a representative generated team without real model calls."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = PROJECT_ROOT / "skills" / "construct-subagent" / "scripts"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "representative_team"
sys.path.insert(0, str(SKILL_SCRIPTS))

from validate_team import TeamValidator  # noqa: E402


def fixture_hashes() -> dict[str, str]:
    """Return stable hashes for every representative fixture file."""
    return {
        str(path.relative_to(FIXTURE_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURE_ROOT.rglob("*"))
        if path.is_file()
    }


class RepresentativeTeamFixtureTests(unittest.TestCase):
    """Validate mixed permissions, ownership preservation, and idempotency."""

    def test_representative_team_passes_without_real_model_probe(self) -> None:
        before = fixture_hashes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shutil.copytree(FIXTURE_ROOT, root, dirs_exist_ok=True)
            (root / ".codex" / "agents" / "retired").mkdir(parents=True)
            shutil.move(root / "manifest.toml", root / ".codex" / "agent-team.toml")
            shutil.move(root / "config.toml", root / ".codex" / "config.toml")
            shutil.copytree(
                root / "agents",
                root / ".codex" / "agents",
                dirs_exist_ok=True,
            )
            shutil.copytree(
                root / "retired",
                root / ".codex" / "agents" / "retired",
                dirs_exist_ok=True,
            )
            shutil.rmtree(root / "agents")
            shutil.rmtree(root / "retired")

            validator_options = {
                "available_models": {"economy-model", "strong-model"},
                "availability_source": "runtime_model_registry",
                "runtime_sandbox": "workspace-write",
                "runtime_approval_policy": "on-request",
                "agent_runtime_sandboxes": {
                    "code_mapper": "read-only",
                    "implementation_worker": "workspace-write",
                },
                "agent_runtime_approval_policies": {
                    "code_mapper": "on-request",
                    "implementation_worker": "on-request",
                },
                "permission_evidence_source": "spawn_session_metadata",
                "require_runtime_permissions": True,
                "codex_version": "codex-cli 0.147.0",
                "codex_version_source": "codex_cli",
            }
            first = TeamValidator(root, **validator_options).validate()
            second = TeamValidator(root, **validator_options).validate()

            self.assertEqual(first["status"], "PASS", first["errors"])
            self.assertEqual(first["configuration_status"], "PASS")
            self.assertEqual(
                first["runtime_model_availability"]["status"],
                "CALLER_ASSERTED",
            )
            self.assertEqual(first["runtime_permissions"]["status"], "VERIFIED")
            self.assertEqual(
                {
                    agent["name"]: agent["observed_effective"]["sandbox_mode"]
                    for agent in first["runtime_permissions"]["agents"]
                },
                {
                    "code_mapper": "read-only",
                    "implementation_worker": "workspace-write",
                },
            )
            self.assertEqual(first["fingerprint"], second["fingerprint"])
            self.assertTrue((root / ".codex" / "agents" / "user-owned.toml").is_file())
            self.assertTrue(
                (
                    root
                    / ".codex"
                    / "agents"
                    / "retired"
                    / "old-reviewer.toml.retired"
                ).is_file()
            )

        self.assertEqual(before, fixture_hashes())


if __name__ == "__main__":
    unittest.main(verbosity=2)

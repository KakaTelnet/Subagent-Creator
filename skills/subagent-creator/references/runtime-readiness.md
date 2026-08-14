# Runtime Readiness

## Contents

- [1. When to read this reference](#1-when-to-read-this-reference)
- [2. Trust boundary](#2-trust-boundary)
- [3. Model evidence](#3-model-evidence)
- [4. Permission evidence](#4-permission-evidence)
- [5. Codex compatibility evidence](#5-codex-compatibility-evidence)
- [6. Readiness levels](#6-readiness-levels)
- [7. Validation interfaces](#7-validation-interfaces)
- [8. Report interpretation](#8-report-interpretation)

## 1. When to read this reference

Read this reference only when:

- the user requests `AGENT_TEAM_RUNTIME_READY` or `AGENT_TEAM_VERIFIED`;
- model catalog, real-invocation, per-Agent permission, or Codex-version evidence is supplied;
- auditing or debugging a runtime readiness result;
- changing the validator's evidence or readiness behavior.

Ordinary team creation and configuration validation do not require runtime evidence and should stop at `AGENT_TEAM_CONFIGURATION_READY`.

## 2. Trust boundary

CLI options are caller-provided strings. They can preserve useful observations but cannot prove that the caller reported them honestly. A source label such as `host_runtime` does not change that boundary.

Only typed evidence passed directly by a trusted host adapter through the Python API may produce host-verified states:

- `HostModelEvidence`;
- `HostPermissionEvidence`;
- `HostCodexVersionEvidence`.

Do not combine typed host evidence with CLI evidence for the same category. Mixed evidence is a conflict, not corroboration.

## 3. Model evidence

The Manifest provenance values defined by [Agent Team Contract](agent-team-contract.md) record how a model candidate was selected; neither those values nor other Manifest prose prove account access.

Runtime model statuses are:

- `UNVERIFIED`: no external model evidence;
- `CALLER_ASSERTED`: CLI catalog coverage includes every assigned default and optional escalation model;
- `CALLER_PROBED`: CLI claims successful invocation coverage for every assigned model;
- `HOST_VERIFIED`: trusted host catalog coverage includes every assigned model;
- `VERIFIED`: trusted host successful-invocation coverage includes every assigned model;
- `FAIL`: supplied evidence is partial, invalid, contradictory, or missing an assigned model.

CLI catalog evidence uses `--availability-source` with repeated `--available-model`. CLI probe evidence uses `--model-probe-source successful_model_probe` with repeated `--probed-model`. Never derive either set by copying the completed Manifest.

The registry contains only models actually assigned as a default or optional escalation. A missing trusted probe does not block configuration readiness, but no result may claim successful invocation without it.

## 4. Permission evidence

Keep three concepts separate:

- `configured_sandbox_default`: the Agent TOML and Manifest value;
- `observed_effective`: the sandbox and approval policy effective for that spawned Agent;
- `observed_parent`: optional parent-thread context.

`developer_instructions` boundaries are behavioral constraints and never become sandbox guarantees.

CLI permission options are caller assertions:

- `--permission-evidence-source host_runtime|spawn_session_metadata`;
- repeated `--agent-runtime-sandbox <agent>=<mode>`;
- repeated `--agent-runtime-approval-policy <agent>=<policy>`;
- optional `--runtime-sandbox` and `--runtime-approval-policy` for parent context.

Permission statuses are:

- `UNVERIFIED`: required per-Agent observations are absent;
- `CALLER_ASSERTED`: complete matching observations were supplied through CLI;
- `HOST_VERIFIED`: complete matching observations came directly from `HostPermissionEvidence`;
- `MISMATCH`: names, values, or configured/effective sandboxes conflict.

A team may legitimately mix `read-only` and `workspace-write`. Compare each Agent independently rather than forcing the parent's single sandbox onto the whole team. Supported approval policies are `untrusted`, `on-request`, `never`, and host-normalized `granular`.

## 5. Codex compatibility evidence

Local validation uses a narrow offline projection of fields emitted by this Skill. Repository CI separately compares that projection with the current official Codex JSON Schema and Subagents documentation. Official additions do not automatically expand the local generation surface.

The reviewed runtime window is:

- minimum stable version: `0.145.0`;
- maximum reviewed series: `0.147.x`;
- `0.145.0` prereleases remain older than the stable baseline;
- newer series remain unreviewed until the contract, validator, and tests are updated.

CLI `--codex-version` plus `--codex-version-source codex_cli|host_runtime` produces at most `CALLER_ASSERTED` for an in-window version. Only `HostCodexVersionEvidence` can produce `HOST_VERIFIED`.

Compatibility statuses are:

- `UNVERIFIED`: absent, incomplete, or unparseable evidence;
- `CALLER_ASSERTED`: a CLI-reported version is inside the reviewed window;
- `HOST_VERIFIED`: a trusted host version is inside the reviewed window;
- `UNSUPPORTED_OLD`: below the minimum stable version;
- `UNREVIEWED_NEWER`: above the maximum reviewed series;
- `MISMATCH`: host and caller evidence were mixed.

An explicit invalid, old, or unreviewed version makes the enhanced validation request fail without changing the independent configuration result. If current official documentation conflicts with the local projection, return `BLOCKED_BY_CODEX_COMPATIBILITY` and update this Skill before writing unknown target formats.

## 6. Readiness levels

- `AGENT_TEAM_CONFIGURATION_READY`: the scoped Manifest, Agent files, config, ownership, paths, assignments, and project v4 persistent wiring are self-consistent. It makes no runtime claim.
- `AGENT_TEAM_RUNTIME_READY`: project scope only; configuration-ready plus persistent wiring `PASS`, trusted host catalog coverage, `HOST_VERIFIED` per-Agent permissions, and `HOST_VERIFIED` Codex compatibility.
- `AGENT_TEAM_VERIFIED`: runtime-ready plus trusted successful real invocation of every assigned model.

A global role library can report only `AGENT_TEAM_CONFIGURATION_READY`; it has no cross-project persistent orchestration and its `persistent_orchestration.status` is `NOT_APPLICABLE_GLOBAL_ROLE_LIBRARY`.

Strict options:

- `--require-runtime-readiness` requires runtime-ready. `--require-host-readiness` and `--require-runtime-permissions` are compatibility aliases;
- `--require-verification` additionally requires verified model invocations.

CLI assertions cannot satisfy either strict level.

## 7. Validation interfaces

Normal project configuration validation:

```bash
python3 scripts/validate_team.py --root <project-root>
```

Caller-reported enhancement example:

```bash
python3 scripts/validate_team.py \
  --root <project-root> \
  --availability-source runtime_model_registry \
  --available-model <default-model> \
  --permission-evidence-source spawn_session_metadata \
  --agent-runtime-sandbox <agent>=<effective-sandbox> \
  --agent-runtime-approval-policy <agent>=<effective-policy> \
  --codex-version <observed-version> \
  --codex-version-source codex_cli
```

Repeat model and per-Agent options as needed. Add probe options only for models actually invoked:

```bash
  --model-probe-source successful_model_probe \
  --probed-model <successfully-invoked-model>
```

Only a trusted host integration can construct the typed evidence needed for runtime-ready or verified.

## 8. Report interpretation

Keep these report fields independent:

- `configuration_status`;
- `local_codex_schema.status`;
- `persistent_orchestration.status`;
- `runtime_model_availability.status`;
- `runtime_permissions.status`;
- `runtime_codex_compatibility.status`;
- `readiness_status`;
- top-level `status` for whether the requested validation conditions passed.

Invalid optional evidence may make top-level `status = FAIL` while `configuration_status = PASS`. Never reinterpret configuration readiness as proof of model access, effective spawned permissions, compatible host runtime, or successful invocation.

If Python 3.11+ is unavailable, return `BLOCKED_BY_VALIDATION_ENVIRONMENT`, do not write a ready Manifest, and do not announce any READY state.

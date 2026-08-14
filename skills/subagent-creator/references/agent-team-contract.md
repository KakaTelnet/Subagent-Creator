# Agent Team Contract

## Contents

- [1. When to read this contract](#1-when-to-read-this-contract)
- [2. Scope and managed outputs](#2-scope-and-managed-outputs)
- [3. Native Agent TOML](#3-native-agent-toml)
- [4. Manifest schema](#4-manifest-schema)
- [5. Scoped Codex config](#5-scoped-codex-config)
- [6. Persistent project wiring](#6-persistent-project-wiring)
- [7. Ownership and lifecycle](#7-ownership-and-lifecycle)
- [8. Path safety and idempotency](#8-path-safety-and-idempotency)
- [9. Configuration validation Gate](#9-configuration-validation-gate)

## 1. When to read this contract

Read this contract before creating, updating, retiring, or validating any team file. Also read it for audits of scope, schema, ownership, path safety, persistent wiring, or idempotency.

For role design and model-routing decisions, read [Team Design Guide](team-design.md). For external model, permission, probe, Codex-version evidence, or readiness above configuration-ready, read [Runtime Readiness](runtime-readiness.md).

## 2. Scope and managed outputs

Project scope is the default. Global scope requires an explicit statement in the current user request such as “global Subagent” or “available to all projects.” `project` and `personal` are internal CLI/Manifest values; user-facing output calls them “project-level” and “global.”

| Scope | Agent files | Config | Manifest | Persistent project instructions |
| --- | --- | --- | --- | --- |
| Project (`project`) | `<project>/.codex/agents/<name>.toml` | `<project>/.codex/config.toml` | `<project>/.codex/agent-team.toml` | Required in active root `AGENTS.override.md` or `AGENTS.md` |
| Global role library (`personal`) | `<CODEX_HOME>/agents/<name>.toml` | `<CODEX_HOME>/config.toml` | `<CODEX_HOME>/subagent-creator/agent-team.toml` | Never modify a project instruction file |

`CODEX_HOME` uses an explicit environment value when present, otherwise `~/.codex`. The context root remains the selected project or directory even for global design; it is not a global write root.

Global authorization must come from the user, not from `--scope personal`. The validator additionally requires `--personal-scope-authorized`, records it as `CALLER_ASSERTED`, and cannot verify the original conversation. Before global writes, the main Agent reports the resolved Codex Home and exact targets.

Global roles must be reusable. Their Manifest has empty `context.artifact_paths`; their instructions contain no context-project paths, private APIs, or project-only Skills.

`NO_AGENT_TEAM_NEEDED` is a pre-generation outcome, not a Manifest `status`. When no managed team exists and no persistent Subagent is justified, write no scoped team artifacts and do not invoke the team validator.

## 3. Native Agent TOML

Every managed active Agent file starts with:

```toml
# Managed by subagent-creator. Edit via $subagent-creator.
```

Minimum shape:

```toml
name = "code_mapper"
description = "Read-only explorer for locating implementation paths."
model = "<default-model-id>"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """
Responsibilities:
- Locate entry points and affected tests.

Boundaries:
- Do not edit files or redefine requirements.

Inputs:
- Project instructions and the task contract.

Outputs:
- Return concise evidence with exact file references.

Escalation:
- Return missing inputs or conflicts to the main Agent.
"""
```

Optional Skill bindings use native Codex configuration:

```toml
[[skills.config]]
path = "/absolute/path/to/a-skill"
enabled = true
```

Only emitted native fields from the validator's strict offline projection are allowed. `name`, `description`, and `developer_instructions` are required by the official custom-Agent schema; this Skill also requires `model`, `model_reasoning_effort`, and `sandbox_mode`.

`developer_instructions` contains five non-empty sections: `Responsibilities:`, `Boundaries:`, `Inputs:`, `Outputs:`, and `Escalation:`. Escalation returns blocked or failed work to the main Agent. Behavioral prose lives only here, not in the Manifest.

Skill paths must resolve to an existing `SKILL.md` and match the Manifest. A global Agent cannot bind a Skill internal to the context project.

## 4. Manifest schema

New Manifests use schema version 4. Versions 1–3 remain read-compatible but their project wiring reports `LEGACY_UNVERIFIED` and cannot satisfy runtime readiness.

```toml
schema_version = 4
generator = "subagent-creator"
status = "ready"
last_changed_at = "2026-08-13T16:31:00+08:00"
scope = "project"

[context]
summary = "One-sentence execution profile."
artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]
constraints = ["Do not change public API without main-Agent approval."]

[orchestration]
max_concurrent_agents = 3
parallel_policy = ["Independent read-only work may run in parallel."]
serial_policy = ["Serialize edits to the same file, public API, or database schema."]
failure_flow = ["Worker BLOCKED -> main", "Test FAILED -> main"]

[[model_registry.models]]
id = "<default-model-id>"
availability_source = "runtime_model_registry"
capability_tier = "throughput"
cost_tier = "low"
reasoning_efforts = ["low", "medium"]
suitable_for = ["exploration", "repeatable tests"]

[[agents]]
name = "code_mapper"
file = ".codex/agents/code-mapper.toml"
description = "Read-only explorer for locating implementation paths."
model = "<default-model-id>"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
skills = []
invoke_when = ["Before changing an unfamiliar module"]
serializes_with = []
cost_tier = "low"
managed = true
```

Top-level rules:

- `generator` is `subagent-creator`; written `status` is `ready` only after validation.
- `last_changed_at` is an RFC 3339 timestamp with timezone and changes only for semantic team changes.
- `scope` matches validator scope.
- `context` contains only compact regeneration facts. Project artifact paths are project-relative existing regular files; global artifact paths are empty.
- `orchestration` keeps main-Agent dispatch, parallel/serial rules, failure flow, and a positive concurrency cap.
- models sort strictly by `id`; Agents sort strictly by `name`; set-semantic arrays are sorted and unique.

Model registry rules:

- register only models assigned as a default or optional escalation;
- `availability_source` is one of `runtime_model_registry`, `codex_model_selector`, `project_model_allowlist`, `successful_model_probe`, or `user_declared_allowlist`;
- `capability_tier` is `throughput`, `balanced`, or `strong`; `cost_tier` is `low`, `medium`, or `high`;
- every assigned effort appears in that model's sorted unique `reasoning_efforts`;
- provenance does not prove account access; read Runtime Readiness for external evidence semantics.

Agent entry rules:

- `file` is scoped-relative, contains no `..`, points directly to one active Agent TOML, and is referenced by only one Agent entry;
- project files use `.codex/agents/<file>.toml`; global files use `agents/<file>.toml`;
- description, model, effort, sandbox, Skills, and name match the native Agent file;
- `invoke_when` is non-empty;
- `serializes_with` references existing other Agents, never self, and is symmetric;
- `managed` is `true`;
- `escalation_model` and `escalation_reasoning_effort` are optional as a pair in v4. If present, the assignment is strictly stronger than default by capability tier and then effort; if absent, failure returns to the main Agent.

Reasoning effort order is `minimal < low < medium < high < xhigh < max < ultra`. Capability order is `throughput < balanced < strong`.

## 5. Scoped Codex config

The scoped `config.toml` contains at least:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
```

The concurrency value matches the Manifest and counts spawned Agents, not the main thread. Independent Agent TOML discovery does not require duplicate `[agents.<role>]` entries.

Modify only required `[agents]` scalars while preserving every unrelated user setting. The validator accepts only its reviewed projection for generated Agent settings and checks types and positive concurrency.

## 6. Persistent project wiring

Project Manifest v4 requires a managed block in the active root instruction file. A non-empty `AGENTS.override.md` takes precedence over `AGENTS.md`; otherwise update or create `AGENTS.md`. Never write the block only into a shadowed file.

```markdown
<!-- subagent-creator:start -->
## Agent Team Runtime Contract

- At the start of any repository task that may involve exploration, implementation, testing, debugging, review, or other work described by a project Subagent, read `.codex/agent-team.toml` before deciding whether to delegate.
- Evaluate every active `[[agents]].invoke_when` against the current task before the main Agent performs matching work.
- Treat its `[orchestration]` and `[[agents]]` entries as the source of truth for invocation, parallel or serial constraints, model escalation, and failure routing.
- When an Agent's `invoke_when` condition matches and delegation is permitted, the main Agent must delegate to that role or state why it is unsafe or unnecessary.
- The main Agent owns dispatch and final decisions; Subagents return results and do not dispatch follow-up work.
- Product requirements may only be changed by the main Agent with user authority.
<!-- subagent-creator:end -->
```

Update one complete existing block in place or append one when absent. Half markers, duplicate blocks, or conflicting user content are `BLOCKED_BY_AGENTS_MD_CONFLICT`. The active instruction file must stay within effective `project_doc_max_bytes`, default 32 KiB.

Global role libraries never write this block and report `persistent_orchestration.status = NOT_APPLICABLE_GLOBAL_ROLE_LIBRARY`.

## 7. Ownership and lifecycle

- `CREATE`: expected managed role is absent.
- `UPDATE`: an owned role exists but differs semantically.
- `KEEP`: complete expected bytes already match.
- `RETIRE`: move an obsolete owned role to scoped `agents/retired/<name>.toml.retired`; never delete it automatically.
- `BLOCKED_BY_AGENT_CONFLICT`: an active same-name file is unowned, ownership is unclear, or project/global discovery contains a same-name role.

Do not overwrite or retire user-managed Agents. Do not adopt a file merely because its contents resemble generated output. Reactivation compares the archived definition before moving or updating it.

Write active Agent files first, minimally update scoped config second, update the project instruction block when applicable, and write the Manifest last. Report actions outside the stable Manifest.

## 8. Path safety and idempotency

Resolve targets before writing. The context/project root, Codex Home, scoped configuration directories, Manifest, config, Agent files, retired targets, and project artifacts must not be symbolic links or traverse a symbolic-link component from their managed root. On detection, return `BLOCKED_BY_UNSAFE_PATH` without following the link and writing its target.

Manifest and Agent paths reject absolute paths where scope-relative paths are required and reject `..`. Project artifacts stay under the project root.

Build the complete expected state and compare exact bytes before any write. Stable semantic ordering is mandatory. Do not change files because of current time, action labels, irrelevant source edits, or table/array reordering.

Update `last_changed_at` once when semantic team content changes; otherwise retain it. The validator fingerprint proves only that inspected current inputs are stable. Prompt-driven idempotency requires a second reconciliation from the same facts that produces all KEEP and zero file diff.

## 9. Configuration validation Gate

The validator is read-only and requires Python 3.11+ because it uses `tomllib`. Use a pyenv-managed virtual environment allowed by the target project.

Project validation:

```bash
python3 scripts/validate_team.py --root <project-root>
```

Explicitly authorized global validation:

```bash
python3 scripts/validate_team.py \
  --root <context-root> \
  --scope personal \
  --codex-home <codex-home> \
  --personal-scope-authorized
```

Configuration-ready requires:

- correct scope and, for global, explicit authorization assertion;
- parseable and internally consistent Manifest, Agent TOML, and scoped config;
- strict local emitted-field projection passes;
- ownership, unique active files, cross-scope names, and path safety pass;
- assigned models, efforts, relative cost tiers, optional escalation, Skills, sorting, and serialization pass;
- project v4 persistent wiring passes, or global wiring is not applicable;
- second expected-state reconciliation is all KEEP with zero diff.

Successful normal validation reports top-level `status = PASS`, `configuration_status = PASS`, `local_codex_schema.status = PASS`, and `readiness_status = AGENT_TEAM_CONFIGURATION_READY`. It does not require model invocation, effective permission, or host-version evidence.

If external evidence is supplied or stricter readiness is requested, read Runtime Readiness and use its interfaces. Invalid optional evidence may fail the overall request while leaving independent configuration status unchanged.

If Python 3.11+ is unavailable, return `BLOCKED_BY_VALIDATION_ENVIRONMENT`, do not write a ready Manifest, and announce no READY state. Never infer product implementation, product tests, or acceptance from this validator.

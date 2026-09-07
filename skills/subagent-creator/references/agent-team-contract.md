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
- [10. Post-creation Prompt suggestion](#10-post-creation-prompt-suggestion)

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

On Codex `0.153.4`, custom Agent role application inherits the parent turn's
effective permission profile. `sandbox_mode` remains a valid native field and
is recorded as the configured default, but it is not proof of a distinct child
sandbox. A project that requires mixed per-role operating-system sandboxes
must remain blocked until trusted host evidence demonstrates that separation.

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

Codex `0.153.4` keeps this `[agents]` value as the spawned-agent cap. If the
user configuration explicitly enables `[features.multi_agent_v2]`, its
`max_concurrent_threads_per_session` counts the primary thread as well and
must equal the Manifest cap plus one; the validator checks this relationship
without rewriting the user's feature setting. Current Codex versions accept
`on-request`, `never`, and host-normalized `granular` approval policies;
`untrusted` is a legacy value supported only by the older reviewed window.

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

The block may also contain the exact optional dispatch policy from section 10, preceded by one blank line immediately before the end marker. Both the original block and this extended block are valid; the core text is unchanged. CREATE does not add this policy. When reconciling an existing team, preserve whether the policy is present and its exact bytes on every CREATE/UPDATE pass; add or remove it only when the user explicitly requests that rule change. Unknown edits inside the managed block are a conflict, not permission to reset it. Keep unrelated instructions outside the block intact.

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

## 10. Post-creation Prompt suggestion

### Output conditions

After successful CREATE with a managed team, configuration-ready or stronger validation, and a second all-KEEP/zero-diff reconciliation, append **Prompt 建议** to the completion reply. Emit one fenced, copyable prompt selected by the actual project/global scope, preceded by a sentence explaining its impact. UPDATE, EXPLAIN, AUDIT, failed/blocked requests, and NO_AGENT_TEAM_NEEDED do not automatically emit it. Do not require runtime-ready evidence for this suggestion.

Displaying the suggestion does not authorize or execute it. Project creation still installs the required base block; global creation still configures only its role library. Only a subsequent user request to apply the suggested rules authorizes the corresponding instruction update. That follow-up changes instructions only, not team roles, models, permissions, business files, or readiness status.

Before displaying a prompt, replace every angle-bracket placeholder below with the actual absolute path. Use the selected team's manifest and the actual installed contract path, not a repository-development path inferred from memory. Paths are data, not shell commands. The executor must re-read the files and resolve the active instruction source at execution time; do not depend on the phrase “the team just created” or on retained conversation history. Missing or conflicting targets require clarification, not a guessed scope. Adapt the surrounding language to the user.

Show this reminder outside the copyable prompt, beside its scope/impact sentence: **AGENTS.md（或 AGENTS.override.md）变动后，需要重启 Codex 或启动 Codex 的新会话，以加载更新后的规则。** Also show it whenever the current operation actually changes either instruction file, even if no Prompt suggestion is emitted. Deduplicate it when both conditions apply. An unchanged file does not justify saying rules were updated. The follow-up prompts below require the executor to repeat the reminder after an edit; neither creation nor follow-up should restart Codex automatically or claim that the existing session reloaded its instructions.

### Project template

Impact: “此建议用于完善当前项目的调度规则；发送后才执行，不影响全局规则。”

```text
请完善项目「<absolute-project-root>」的子 Agent 调度规则。
读取团队清单「<absolute-manifest-path>」、其引用的原生角色配置，以及
契约「<absolute-contract-path>」第 6、10 节，核实当前项目指令的生效位置。
仅在该项目当前生效的根 AGENTS.md 或 AGENTS.override.md 中，原位更新
已有 subagent-creator 调度块：保留完整基础规则，在结束标记前加入契约中
规定的 Cost-aware dispatch policy 原文；已有该段时保持不变，不重复追加。
该规则要求按任务匹配原生角色，对规则明确且可验证的工作优先选择能胜任的
低成本角色，异常返回主 Agent，遵守并发和权限约束，并如实报告执行证据。
角色和模型以实际团队配置为准；不要复制维护第二份角色表，不调整团队配置。
保留所有无关内容；清单缺失、基础块缺失或块内存在未知改动时先报告缺口，
不要重建团队或覆盖冲突。使用项目合规环境运行现有团队验证器，检查差异，
再次对账确认规则不重复、内容稳定。报告实际修改位置、检查结果及证据限制。
若本次修改了 AGENTS.md 或 AGENTS.override.md，请在完成回复中明确提醒：
“AGENTS.md（或 AGENTS.override.md）变动后，需要重启 Codex 或启动 Codex 的新会话，以加载更新后的规则。”
不要自动重启，也不要声称当前会话已重新加载规则。
```

### Global template

Impact: “此建议会更新全局调度原则，影响所有项目；发送后才执行。”

```text
请为 Codex Home「<absolute-codex-home>」配置全局子 Agent 调度原则，
这次请求授权更新该位置当前生效的 AGENTS.md 或 AGENTS.override.md。
先读取全局团队清单「<absolute-global-manifest-path>」、其引用的原生角色
配置，以及契约「<absolute-contract-path>」第 10 节，确认清单属于全局作用域。
采用契约规定的全局指令块格式与 Cost-aware dispatch policy 原文，新增或
原位更新一个全局调度块；已有相同内容时保持不变，未知改动先报告冲突。
要求按需求匹配现有角色，对规则明确且可验证的工作优先选择能胜任的
低成本角色；项目存在专用团队时结合项目规则选择，不覆盖项目专用约定。
全局规则仅引用上述全局团队清单，不写入当前项目的路径、业务约束或私有信息，
不复制维护角色表，也不改角色、模型、权限或项目文件。保留无关全局规则。
检查指令生效位置、文件差异和重复块，再次对账确认零差异；报告修改范围与
检查结果，不把规则写入解释为实际调用成功、节省费用或提升团队就绪状态。
若本次修改了 AGENTS.md 或 AGENTS.override.md，请在完成回复中明确提醒：
“AGENTS.md（或 AGENTS.override.md）变动后，需要重启 Codex 或启动 Codex 的新会话，以加载更新后的规则。”
不要自动重启，也不要声称当前会话已重新加载规则。
```

### Optional dispatch policy and follow-up lifecycle

Use this exact policy in the project extension and global instruction block. Fixed text lets validation preserve the base contract while rejecting accidental edits; the team manifest remains the source of role names and cost tiers.

```markdown
### Cost-aware dispatch policy

- Before doing matching work, select an existing custom Agent using the team manifest and native role configuration.
- For explicit inputs, established rules, and easily verifiable outputs, prefer the lowest-cost capable role using the configured cost tiers; do not infer measured savings from those tiers.
- Use the selected native custom role, not a generic Agent with the same name or copied instructions; report an unavailable role or model before choosing a fallback.
- The main Agent owns requirements, bounded assignments, exceptions, escalation, and final acceptance; follow the team's concurrency, serialization, and permission constraints.
- Return rule exceptions, conflicting evidence, and out-of-scope work to the main Agent; do not silently upgrade models or permissions.
- Explain skipped matching delegation and avoid repeating completed work without a verification reason. Report observed role/session/model evidence when available; mark missing evidence unverified and never claim actual low-cost execution from configuration alone.
```

For a global follow-up, resolve the first non-empty `AGENTS.override.md`, then `AGENTS.md` in the specified Codex Home; create `AGENTS.md` only when neither supplies instructions. Reject symbolic-link targets or parent components and preserve unrelated content. Use exactly one pair of `<!-- subagent-creator:global-dispatch:start -->` / `<!-- subagent-creator:global-dispatch:end -->` markers around a reference to the resolved global manifest, a sentence giving applicable project-team rules precedence, and the policy above. Report malformed/duplicate markers, unknown block edits, or conflicting user rules instead of overwriting them. Never place project-specific paths or the installed contract path into this reusable global block.

Project follow-ups use the existing project markers and the exact core-plus-policy format from section 6. Global follow-ups are separate user-authorized instruction edits; global team CREATE/UPDATE does not maintain these instructions. Reapplying either suggestion must preserve identical bytes when the facts have not changed. Configuration validation checks project block structure only, not actual delegation, model usage, semantic compliance of surrounding user instructions, or savings. Global role-library validation still reports `NOT_APPLICABLE_GLOBAL_ROLE_LIBRARY` and cannot certify cross-project dispatch.

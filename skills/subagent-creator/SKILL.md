---
name: subagent-creator
description: 解释、设计、创建、审计或更新 Codex 自定义 Subagent 团队。当用户要求了解、创建或配置 Subagent，设计、优化或审计 Agent 团队，构建多模型或并行 Agent 工作流，或为已经明确的开发目标配置角色、模型、sandbox、Skill、并发、串行冲突与失败升级策略时使用。
---

# Subagent Creator

## Outcome and boundary

Configure a minimal sufficient Codex Subagent team coordinated by the current main Agent. Default to a durable project-level team. Create a reusable global role library only when the user explicitly requests global or all-project availability in the current request.

Configure team infrastructure only. Do not define product requirements, complete a missing technical design, decompose implementation tasks, execute product work, or claim product verification.

## Reference routing

Load only the reference needed for the current operation:

- Read [Team Design Guide](references/team-design.md) when creating a team, changing team shape or routing, auditing whether roles remain minimal and correctly separated, or explaining role separation, merging, model, permission, and routing criteria.
- Read [Agent Team Contract](references/agent-team-contract.md) before creating, updating, retiring, or validating team files; when auditing scope, schema, ownership, path safety, persistent wiring, or idempotency; or when explaining generated files and their lifecycle.
- Read [Runtime Readiness](references/runtime-readiness.md) only when external model, permission, probe, or Codex-version evidence is supplied; when readiness above configuration-ready is requested; when explaining readiness levels or evidence trust; or when changing evidence/readiness behavior.
- Read [Goal Execution Handoff](references/goal-execution-handoff.md) only after a successful project-scoped `CREATE` or `UPDATE` has a managed team, configuration-ready or stronger evidence, and one stable implementation plan; append its copyable `/goal` prompt without starting product work. Do not read or emit it for other outcomes or global scope.
- Execute `scripts/validate_team.py` without reading its source. Read the script only to debug or change validator behavior.

For a general explanation that does not depend on team-design, file-contract, or runtime-readiness details, do not load references unnecessarily.

## Core rules

- Treat project artifacts and current repository facts as authoritative. Do not substitute chat memory for missing facts or copy full specifications into prompts.
- Keep the topology flat. The main Agent owns dispatch, requirement interpretation, integration, escalation, and final judgment; Subagents return bounded results and do not dispatch work.
- Split a role only for a material difference in model, permission, context isolation, independent parallelism, independent verification, or specialist capability. Merge otherwise.
- Prefer lower-cost routing only when capability and failure risk permit it. Never infer account model availability from public documentation or Manifest prose.
- Keep configured sandbox defaults, effective spawned permissions, and behavioral prompt boundaries distinct.
- Preserve user-owned Agents, unrelated configuration, and unrelated dirty files. Manage only marked files and the controlled project-instruction block.
- Derive team inputs from the user's natural-language prompt and authoritative project facts. Do not require a fixed intake template; inspect available facts before asking, and block only on an irreducible missing decision that would materially change scope, role topology, permissions, or model routing.
- Keep generation idempotent: reconcile the same facts to the same bytes, retain stable timestamps, and require a second all-KEEP/zero-diff pass.

## Workflow

### 1. Lock operation, scope, and context

Classify the request as `EXPLAIN`, `AUDIT`, `CREATE`, or `UPDATE`. `EXPLAIN` and `AUDIT` are read-only unless the current request explicitly authorizes applying changes. An audit reports proposed CREATE, UPDATE, KEEP, and RETIRE actions without executing them; create or update authority applies only to managed team infrastructure within the requested scope.

Use project scope unless the current request explicitly asks for global or all-project Agents. Do not infer global scope from installation location, reuse potential, an existing Codex Home, or a non-Git directory. For global work, report the resolved Codex Home and exact targets before writing.

Use the explicit target directory as the context root; otherwise use the current project root. Read applicable project instructions, write restrictions, and Git status before changing files.

### 2. Apply the requirements Gate

Proceed only when outcome, scope, non-goals, critical constraints, authoritative sources, and expected verification are clear enough to determine team shape. A global role additionally needs reusable responsibilities, invocation conditions, permission boundaries, and output expectations.

If unresolved ambiguity could change roles, permissions, or model routing, write nothing and return `BLOCKED_BY_REQUIREMENTS` with the missing decision and its effect. Do not resolve product ambiguity on the user's behalf.

### 3. Design or audit the team

When team shape is in scope, read the Team Design Guide. Inventory existing scoped configuration and ownership, derive an Execution Profile, design the smallest justified role set, and define model, effort, sandbox, Skill, invocation, serialization, output, and failure-return contracts.

Compare every candidate role with the main Agent as well as with other roles. If no persistent difference in model, permission, context isolation, independent parallelism, independent verification, or specialist capability justifies delegation and no managed team exists, write nothing and return `NO_AGENT_TEAM_NEEDED`. For an existing managed team, report proposed recoverable retirements in `AUDIT`; do not dismantle the whole team in `UPDATE` without explicit team-retirement authorization.

Use an optional escalation model only when a strictly stronger configuration exists and has a concrete trigger. Otherwise route blocked or failed work back to the main Agent.

### 4. Reconcile scoped files

Run this step only in `CREATE` or `UPDATE`. In `AUDIT`, compute and report proposed actions without writing files.

Before any file audit or mutation, read the Agent Team Contract. Form the complete expected state before writing. Apply CREATE, UPDATE, KEEP, and recoverable RETIRE actions without adopting unowned files or rewriting unrelated configuration.

Project teams must include the contract's managed block in the active root `AGENTS.override.md` or `AGENTS.md`, so future tasks load the Manifest and evaluate `invoke_when`. Global role libraries must not modify project instructions or retain project artifacts.

Reject unsafe symbolic-link paths and ownership or cross-scope name conflicts rather than guessing.

### 5. Validate and reconcile again

Use a pyenv-managed Python 3.11+ virtual environment and run the applicable validation command from the Agent Team Contract after mutation, or read-only against existing files when validation is part of an audit. `NO_AGENT_TEAM_NEEDED` with no managed team files requires no team validation. Normal validation needs no runtime evidence and may report `AGENT_TEAM_CONFIGURATION_READY`.

If external evidence or stricter readiness is involved, read Runtime Readiness first and preserve caller-asserted versus host-verified trust boundaries. Do not claim `AGENT_TEAM_RUNTIME_READY` or `AGENT_TEAM_VERIFIED` from CLI assertions.

Recompute the expected state from the same facts. Finish only when the second pass is all KEEP with zero file diff. If Python 3.11+ is unavailable, return `BLOCKED_BY_VALIDATION_ENVIRONMENT` and announce no READY state.

## Completion output

Return a concise, verifiable summary containing:

- selected operation, scope, mutation authority, and resolved managed paths;
- `NO_AGENT_TEAM_NEEDED`, readiness, or precise BLOCKED status;
- for an audit, findings, proposed actions, and confirmation that no files changed;
- for an existing or proposed team, each Agent's action, responsibility, default model, optional escalation, and sandbox;
- central dispatch plus parallel, serial, and failure routing;
- evidence trust levels and relevant gaps;
- exact changed files and any validation commands/results;
- preserved unrelated worktree changes.

For an eligible successful project team, append the Goal Execution Handoff after the verification summary, replace only its implementation-plan placeholder when the authoritative path is known, and leave Goal creation and execution to the user's next request.

Never claim that product implementation, tests, or final acceptance passed merely because the Agent Team configuration is ready.

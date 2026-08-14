# Team Design Guide

## Contents

- [1. When to read this guide](#1-when-to-read-this-guide)
- [2. Requirements Gate](#2-requirements-gate)
- [3. Current-state inventory](#3-current-state-inventory)
- [4. Execution Profile](#4-execution-profile)
- [5. Minimal sufficient roles](#5-minimal-sufficient-roles)
- [6. Model, permission, and Skill routing](#6-model-permission-and-skill-routing)
- [7. Agent behavioral contract](#7-agent-behavioral-contract)
- [8. Design result](#8-design-result)

## 1. When to read this guide

Read this guide when:

- creating a team for the first time;
- changing team shape because requirements, architecture, risks, models, cost priorities, or permissions changed;
- auditing whether existing roles are minimal, correctly separated, and appropriately routed.

Do not load this guide for a schema-only, ownership-only, path-safety, or runtime-evidence check when the intended team shape is unchanged.

## 2. Requirements Gate

For a project-level team, prefer Product Spec, Current Product Model, Change Spec, and any applicable Technical Spec, Architecture, or Verification Contract. Verify prose against the repository rather than using chat history as the only fact source.

Continue only when all of the following are sufficiently clear to determine team shape:

- intended product or engineering outcome;
- main scope, non-goals, and critical constraints;
- authoritative project artifacts or code surfaces;
- expected quality and verification boundary;
- a controlled model allowlist or a clear route for establishing one.

For a global role library, a project Product Spec is not required. The user must instead define the reusable role's responsibilities, invocation conditions, non-goals, permission boundary, and output contract. A project may be used as design evidence, but its paths, private APIs, and artifacts must not be embedded into global roles.

If unresolved ambiguity could change role count, role boundaries, permissions, or model routing:

1. do not change team files;
2. return `BLOCKED_BY_REQUIREMENTS`;
3. identify the missing artifact or decision and explain how it affects team shape;
4. stop without defining the product or completing the technical design for the user.

Small projects and narrowly reusable global roles do not require heavyweight documentation when the available facts already determine the necessary capabilities.

## 3. Current-state inventory

Inspect only the facts needed for the requested team decision:

- languages, modules, platforms, data stores, external integrations, and entry points;
- product, technical, verification, and task artifacts;
- existing scoped `config.toml`, Agent TOML files, Manifest, and active project instructions;
- available project, user, and installed Skills;
- concurrency limits, model constraints, cost/quality/speed priorities, network, and write restrictions;
- existing Agent ownership and cross-scope name conflicts.

Classify each existing Agent as managed by this Skill, user managed, or unknown. Never adopt or overwrite an unowned same-name Agent. A project/global name collision is `BLOCKED_BY_AGENT_CONFLICT` until the user chooses a rename or retirement.

Runtime model, permission, and Codex-version evidence is conditional. Read [Runtime Readiness](runtime-readiness.md) only when such evidence is supplied or a readiness level above configuration-ready is requested.

## 4. Execution Profile

Summarize the execution characteristics that materially influence team shape:

- scale: small, medium, large, or very large;
- task lanes: research, architecture, coding, refactoring, migration, testing, debugging, security, performance, UI, documentation, or integration;
- independence: separable modules and independently verifiable outputs;
- serialization: shared files, public APIs, database schema, prerequisite chains, and high-risk shared state;
- risk: architecture, data, security, compatibility, performance, and regression;
- stable constraints and artifact paths needed for future reconciliation.

Do not use this step to invent a missing Technical Design. The Manifest retains only a compact `summary`, `artifact_paths`, and `constraints`; it never copies full specifications. A global role library must keep `artifact_paths` empty.

## 5. Minimal sufficient roles

Derive capability lanes from current work and risk, then decide whether each lane warrants a separate Agent.

First compare every candidate lane with work the main Agent can perform directly. A persistent Subagent is justified only when delegation creates a material model, permission, context-isolation, independent-parallelism, independent-verification, or specialist-capability boundary. Do not force a one-role team merely to produce a Manifest.

Create a separate role only when at least one of these differs materially:

- model or reasoning effort;
- configured sandbox or permission boundary;
- context isolation;
- independent parallel work;
- independent verification responsibility;
- specialist capability or tooling.

For every proposed role, state one reason it cannot be merged. Merge roles whose model tier, sandbox, inputs, responsibility boundary, and parallel domain are effectively identical. Do not pre-create roles for hypothetical future work.

Prefer an independent reviewer/verifier when high-risk work genuinely benefits from separation. Serialize roles that may edit the same file, public contract, or database schema, or whose work has explicit prerequisites.

Keep topology flat. The main Agent owns dispatch, requirement interpretation, escalation decisions, integration, and final judgment. Subagents return bounded results and do not dispatch follow-up work.

## 6. Model, permission, and Skill routing

Choose routing using capability, task value, failure cost, invocation frequency, expected context size, and parallel fan-out:

- reserve stronger reasoning for architecture, complex failures, high-risk review, and final judgment;
- use balanced execution models for substantial implementation and bounded refactoring;
- use high-throughput lower-cost models for exploration, repeatable tests, bulk checks, and log summarization;
- use only reasoning efforts supported by the selected model;
- default to `read-only`; use `workspace-write` only for roles that must edit; require explicit user authority and an explained risk before `danger-full-access`;
- bind only existing Skills that match the role. Report missing capabilities as gaps instead of creating another Skill automatically.

An escalation assignment is optional. Add it only when a strictly stronger configuration is available and has a concrete trigger. Without one, the Agent returns the blocked or failed case to the main Agent. A fixed model in a custom Agent file is not assumed to be overridable at spawn time; frequent escalations may justify a separate role, while infrequent ones use a one-off general Agent chosen by the main Agent.

Model catalog provenance and runtime trust levels are defined in [Runtime Readiness](runtime-readiness.md). Never infer account availability from public documentation or Manifest prose.

## 7. Agent behavioral contract

Every native Agent TOML must define:

- role and responsibilities;
- boundaries and configured sandbox default;
- required inputs and authoritative artifacts;
- output contract and independent verification evidence;
- invocation conditions and serialization conflicts;
- blocked/failed return path to the main Agent;
- default model and reasoning effort;
- optional stronger escalation assignment and trigger;
- bound Skills and necessary tools.

Use five non-empty sections in `developer_instructions`: `Responsibilities:`, `Boundaries:`, `Inputs:`, `Outputs:`, and `Escalation:`. This is the only source of behavioral prose; the Manifest must not duplicate it. Prompt boundaries are behavioral instructions, not operating-system enforcement.

## 8. Design result

Before writing files, produce an internally consistent proposed state containing:

- locked scope and context root;
- compact Execution Profile;
- minimal role list with non-merge reasons;
- model, effort, sandbox, Skill, and optional escalation assignments;
- invocation and symmetric serialization relationships;
- central failure flow and concurrency cap;
- expected CREATE, UPDATE, KEEP, and RETIRE actions.

Then read [Agent Team Contract](agent-team-contract.md) before reconciling that design with files.

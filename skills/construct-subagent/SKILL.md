---
name: construct-subagent
description: 为需求和主要实施方向已经明确的 Codex 项目分析执行特点，设计并创建最小充分、项目级、可幂等演进的多模型自定义 Subagent 团队。用于准备进入技术实施、希望用低成本模型承担探索、测试、批量检查或简单编码，并为架构、复杂调试和最终判断保留强模型时；也用于审查或更新已有 `.codex/agents/*.toml`、模型分配、权限、Skill 绑定、并行和升级策略。若产品需求仍有重大歧义，停止并返回 `BLOCKED_BY_REQUIREMENTS`。不要用于产品定义、完整技术架构设计、Task 拆分、业务编码、产品测试或最终验收。
---

# Construct Subagent

## 目标

为当前项目构造一支由主 Agent 集中协调的项目级团队。根据项目事实生成角色，不套用固定的 planner/coder/tester 模板。把高成本模型用于高价值判断，把高吞吐模型用于边界清楚、失败成本低、调用频繁的工作。

只配置团队基础设施；不要执行后续 Task Engineering、编码、测试或验收。

## 核心原则

- 以项目 Artifact 为事实源，不把 Product Spec 或 Technical Spec 复制进 Agent prompt。
- 把当前主 Agent 视为 Orchestrator；除非存在独立且持久的协调职责，否则不要再创建 orchestrator 子 Agent。
- 只在模型、权限、上下文隔离、可独立并行、独立验证或专业能力至少一项不同的时候拆分角色。
- 合并职责、边界、模型和权限相同的角色；优先选择最小充分集合。
- 采用扁平拓扑。Subagent 向主 Agent 返回结果，不直接决定或派发下一步。
- 对权限分三层表述：`sandbox_mode` 是 Agent 的配置默认值；父线程当前 sandbox/approval 是 spawn 时可能重新应用的实时权限；“只运行测试”“不得改需求”等是仅靠 `developer_instructions` 实施的行为边界。不要把任一层声称为另一层的保证。
- 保留用户维护的配置和不相关改动。只更新本 Skill 明确拥有的文件或受控标记块。
- 使用当前可用模型注册表。不要永久硬编码某一组模型或假设账户一定可用。
- 让相同输入产生相同文件。不要因为再次运行而刷新时间戳、动作标签或重排内容。

## 必读契约

在设计或写文件前，完整读取 [Agent Team Contract](references/agent-team-contract.md)。它定义 Manifest、受管文件、生命周期和验证规则。

## 工作流

### 1. 解析项目根、官方能力与 Codex 兼容性

1. 将显式目标目录作为项目根；否则使用当前工作目录或 Git 根。
2. 读取适用的 `AGENTS.md`、项目 Git 状态和写入限制。不要覆盖不相关的 dirty/untracked 文件。
3. 使用 `openai-docs` 查询当前官方 **Subagents** 与 **Configuration Reference**，确认自定义 Agent 路径、必填字段、模型优先级、权限继承和 Skill 配置仍然有效。
4. 执行 `codex --version`，或读取宿主明确公开的等价运行时版本；保留原始值和来源，按契约判定是否位于已审查兼容窗口。
5. 若版本缺失、无法解析、低于最低稳定版本、高于最高已审查系列，或当前官方 schema 与本 Skill 契约冲突，不创建或修改目标团队文件；返回 `BLOCKED_BY_CODEX_COMPATIBILITY`。先更新本 Skill 的契约、验证器和测试，不要在生成目标配置时临时绕过兼容性 Gate。

当前基线只作为待验证假设：项目 Agent 位于 `.codex/agents/*.toml`，每个文件至少包含 `name`、`description`、`developer_instructions`；项目级全局设置位于 `.codex/config.toml` 的 `[agents]`。

### 2. 执行需求就绪 Gate

优先读取 Product Spec、Current Product Model、Change Spec，以及存在时的 Technical Spec、Architecture、Verification Contract。通过仓库结构和代码验证文档，不用聊天记忆替代 Artifact。

仅当以下条件成立时继续：

- 要实现或变更的产品结果可陈述；
- 主要范围、非目标和关键约束已明确；
- 不存在会改变团队形态的重大产品歧义；
- 项目很简单时，现有说明仍足以判断所需执行能力。

若不成立：

1. 不创建或修改任何团队文件；
2. 返回 `BLOCKED_BY_REQUIREMENTS`；
3. 列出缺失 Artifact、未决问题及其为何会改变 Agent 设计；
4. 停止，不代替产品定义或完整技术设计。

### 3. 盘点现状

读取并记录：

- 产品、技术、验证和任务契约；
- 仓库语言、模块、平台、数据库、外部集成和入口；
- 现有 `AGENTS.md`、`.codex/config.toml`、`.codex/agents/*.toml` 和 `.codex/agent-team.toml`；
- 项目级、用户级和已安装 Skill 的真实路径；
- 并发上限、允许/禁止模型、成本/质量/速度优先级、网络和写入约束；
- 当前父线程实际生效的 sandbox 与 approval policy；
- 当前 Codex 运行时版本及其独立来源；
- 现有 Agent 的所有权：受本 Skill 管理、用户管理或来源不明。

不要采用同名但非本 Skill 管理的 Agent。若受管角色需要使用其名称，返回 `BLOCKED_BY_AGENT_CONFLICT` 并给出冲突路径。

### 4. 建立动态 Model Registry

按以下顺序收集当前可用模型：

1. 当前运行时或 Agent 工具公开的模型 override/模型目录；
2. 当前本地 Codex 提供的模型目录、受管配置或项目明确提供的 registry；
3. 用户显式提供的允许模型及能力约束；
4. 当前官方 OpenAI 文档，只用于补充能力和定性成本信息。

对每个候选记录来源、可用性证据、支持的 reasoning effort、能力层、相对成本层和适用任务。Manifest 的 `availability_source` 只能使用契约定义的受控值。只有当前运行时 registry、当前已认证 Codex 模型选择器或本次成功模型探测能确认“可用”；不要用公开文档、静态默认配置、用户猜测或 Manifest 自己的文字推断账户权限。

保留本次运行实际观察到的独立模型集合，供验证步骤通过 `--available-model` 传入。不要从写好的 Manifest 反向生成这个集合。

若无法确认至少一个可用执行模型，或成本优化要求多个模型但无法辨别候选能力/成本，停止且返回 `BLOCKED_BY_MODEL_REGISTRY`。不要静默写入猜测模型。

### 5. 建立 Project Execution Profile

至少分析并写入 Manifest：

- 规模：small / medium / large / very-large；
- 技术复杂度：模块、前后端、数据库、分布式、AI、实时、移动、多平台、第三方集成；
- 主要任务类型：architecture、research、coding、refactoring、migration、testing、debugging、security、performance、UI、documentation、integration；
- 并行性：可独立工作、共享文件、共享接口、前置依赖和高风险共享状态；
- 风险：架构、数据、安全、兼容、性能和回归；
- 项目约束和 Artifact 路径。

不要借此补做缺失的完整 Technical Design。只基于已确认方向设计当前阶段能力。

### 6. 设计最小充分角色

从任务与风险推导能力 lane，再决定是否需要独立角色：

1. 为每个候选角色写出一条不可合并理由。
2. 若两个候选的模型层、sandbox、输入 Artifact、职责边界和并行域相同，优先合并。
3. 对高风险项目优先增加独立 Reviewer/Verifier，而不是堆叠 Coder。
4. 对只读搜索、日志归纳、重复测试等高频低风险工作优先使用低成本角色。
5. 对共享公共 API、数据库 schema、同一文件或有前置依赖的工作设置串行 Gate。
6. 不为未来可能出现但当前没有证据的工作预建角色。

每个角色必须定义：

- Role、Responsibility、Boundary；
- 默认模型与 reasoning effort；
- 升级模型、升级 effort 和触发条件；
- `sandbox_mode` 与行为性权限边界；
- 已验证存在的 Skills、必要工具、输入 Artifact 和输出契约；
- 调用时机、允许并行的组和禁止并行的冲突；
- 向主 Agent 返回 `BLOCKED` / `FAILED` 的升级策略。

### 7. 分配模型、权限和 Skill

按“能力 × 任务价值 × 失败成本 × 调用频率 × Token 消耗 × 并行数量”选择模型：

- 将强推理模型留给架构判断、重大故障、高风险审查和最终裁决；
- 将中高能力执行模型用于主要编码、复杂重构和独立模块实现；
- 将高吞吐低成本模型用于探索、测试、批量检查、日志归纳和简单修改；
- 仅使用 registry 明确支持的 reasoning effort；
- 配置默认值使用最小权限：默认为 `read-only`；只有必须修改工作区的角色才使用 `workspace-write`；除非用户明确要求且风险已解释，否则禁止 `danger-full-access`。同时记录父线程当前实时权限，不能因 Agent 文件写了 `read-only` 就推断 spawned Agent 必然只读；
- 只绑定已存在且与职责匹配的 Skill。缺失 Skill 时记录 gap 或使用基础工作规则，不要自动创建新 Skill。

固定 Agent 文件中的 `model` 会优先于 spawn override。为兼顾“便宜的默认模型”和“必要时升级”：

1. 在 Agent 文件中固定默认模型；
2. 在 Manifest 中记录 escalation model；
3. 升级触发后，让主 Agent新建一次性 `default`/通用 Agent，并显式选择升级模型、附上同一 Task Contract 和该角色边界；
4. 不要假设 spawn 参数能覆盖已固定模型的自定义 Agent 文件；
5. 只有升级流程频繁且确有上下文隔离价值时，才创建独立升级角色。

### 8. 对账并写入

先形成期望状态，再逐文件比较；内容相同则不要重写。

- `CREATE`：创建缺失的受管定义。
- `UPDATE`：仅更新团队事实已变化的受管定义。
- `KEEP`：保持语义和文件完全不变。
- `RETIRE`：将不再需要的受管 `.toml` 归档为 `.codex/agents/retired/<name>.toml.retired`，再从活动目录移除；不要删除用户管理的 Agent。

按此顺序操作：

1. 更新或创建 `.codex/agents/*.toml`；
2. 必要时只修改 `.codex/config.toml` 中明确需要的 `[agents]` 标量，不重写其他设置；
3. 只有确有长期协作 Gate 时，更新 `AGENTS.md` 中 `construct-subagent` 受控标记块；不要把完整角色 prompt 塞入 `AGENTS.md`；
4. 最后写 `.codex/agent-team.toml`；
5. 在运行结果中报告 CREATE / UPDATE / KEEP / RETIRE，不把本次动作写进 Manifest。

受管 Agent 文件首行必须是：

```toml
# Managed by construct-subagent. Edit via $construct-subagent.
```

Manifest 使用稳定的 `last_changed_at`。仅在语义内容变化时更新；相同输入下保留原值和原文件字节。

### 9. 验证

1. 本 Skill 的验证器因使用标准库 `tomllib`，要求 Python 3.11 或更高版本。先按目标 `AGENTS.md` 验证 pyenv/venv 路径和 `python3 --version`，再运行验证器。若目标项目 venv 低于 3.11，可在项目规则允许时使用独立的、pyenv 管理的 Python 3.11+ 验证专用 venv；验证器是只读的，不导入目标应用依赖。
2. 运行 `scripts/validate_team.py --root <project-root> --availability-source <source> --available-model <model-id> ... --runtime-sandbox <mode> --runtime-approval-policy <policy> --require-runtime-permissions --codex-version <observed-version> --codex-version-source <source>`，并传入本次运行实际观察到的模型、父线程权限和 Codex 版本证据。每个已观察到的模型重复一次 `--available-model`；sandbox、approval 和版本必须来自当前运行时，不能从 Agent 文件或 Manifest 反推。
3. 若无法取得 Python 3.11+ 环境，按验证脚本的同等规则人工检查并明确标注未运行脚本；不要伪造通过，也不要声明 `AGENT_TEAM_READY`。
4. 确认报告的 `configuration_status = PASS`、`runtime_model_availability.status = VERIFIED`、`runtime_permissions.status = VERIFIED` 且 `runtime_codex_compatibility.status = VERIFIED`；再确认所有活动受管 Agent 可解析、名称唯一、必填字段齐全、模型存在于 registry、Skill 路径存在、配置默认 sandbox 与 Manifest 一致且与父线程实时 sandbox 匹配。
5. 确认 `last_changed_at` 是带时区的 RFC 3339 时间戳，模型和 Agent 分别按 `id` 与 `name` 排序，每个 Agent 文件只被引用一次，Artifact 路径指向普通文件，升级配置按契约定义严格强于默认配置。
6. 确认 `.codex/config.toml` 可解析、没有显式禁用 agents，且并发上限为正数。
7. 确认并行规则覆盖同文件、公共 API、数据库 schema、前置依赖和高风险共享状态。
8. 用同一项目事实再次计算期望状态；若没有语义变化，应得到全 KEEP 且零文件 diff。
9. 缺少独立模型证据或模型不在当前外部集合中时返回 `BLOCKED_BY_MODEL_REGISTRY`；父线程权限证据缺失或实时 sandbox 与配置默认值不一致时返回 `BLOCKED_BY_RUNTIME_PERMISSIONS`；Codex 版本状态不是 `VERIFIED` 时返回 `BLOCKED_BY_CODEX_COMPATIBILITY`；只有全部完成条件成立时返回 `AGENT_TEAM_READY`。

## 完成输出

返回简洁、可核验的摘要：

1. 状态：`AGENT_TEAM_READY` 或明确的 BLOCKED 状态；
2. Project Execution Profile 摘要；
3. Agent 表：角色、CREATE/UPDATE/KEEP/RETIRE、默认模型、升级模型、sandbox、职责；
4. 中央协调、失败升级和并行/串行规则；
5. Cost Profile、模型可用性证据来源、Codex 版本与兼容性状态，以及配置状态与运行时可用性状态的明确区分；
6. Skill gaps，并明确区分 Agent 配置默认 sandbox、父线程实时 sandbox/approval 和只能靠 `developer_instructions` 实施的行为边界；
7. 写入的精确文件路径；
8. 实际运行的验证命令和结果；
9. 若 Git 原本已有改动，说明本次修改与保留的无关改动。

不要宣布产品已完成、测试已通过或最终验收通过；本 Skill 只证明 Agent Team 配置就绪。

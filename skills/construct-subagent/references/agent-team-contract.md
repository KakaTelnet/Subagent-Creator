# Agent Team Contract

## 1. 输出边界

`construct-subagent` 只拥有以下项目级输出：

- `.codex/agent-team.toml`：团队事实源，供主 Agent 和后续 Task Engineering 查询；
- `.codex/agents/<name>.toml`：Codex 原生自定义 Agent 定义；
- `.codex/agents/retired/<name>.toml.retired`：已退役且可恢复的受管定义；
- `.codex/config.toml` 的 `[agents]` 标量：团队启用状态和并发上限；
- `AGENTS.md` 中可选的受控标记块：仅放长期协作 Gate。

不要覆盖用户拥有的 Agent、其他 `.codex/config.toml` 设置或 `AGENTS.md` 其他内容。

## 2. 官方 Agent 文件

每个活动 Agent 文件使用 TOML，首行固定为：

```toml
# Managed by construct-subagent. Edit via $construct-subagent.
```

至少包含：

```toml
name = "code_mapper"
description = "Read-only explorer for locating implementation paths before edits."
model = "<verified-model-id>"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """
Read the applicable AGENTS.md and task artifacts before working.

Responsibilities:
- Locate entry points, ownership boundaries, and affected tests.

Boundaries:
- Do not edit files.
- Do not redefine product requirements or architecture.

Output:
- Return concise evidence with exact file references.

Escalation:
- Return BLOCKED to the parent when required artifacts conflict or are missing.
"""
```

Skill 绑定使用 Codex 原生配置；`path` 使用真实、已验证存在的 Skill 目录：

```toml
[[skills.config]]
path = "/absolute/path/to/a-skill"
enabled = true
```

`developer_instructions` 定义角色行为，至少覆盖职责、边界、输入、输出和升级。它引用项目 Artifact 路径或类型，不复制 Artifact 正文。

## 3. Manifest schema

`.codex/agent-team.toml` 使用以下稳定结构。字段顺序按示例保持一致，便于审查和幂等比较。

```toml
schema_version = 1
generator = "construct-subagent"
status = "ready"
last_changed_at = "2026-08-13T16:31:00+08:00"

[project]
size = "medium"
summary = "One-sentence implementation profile."
complexity = ["multi-module", "web", "database"]
task_types = ["coding", "testing", "integration"]
risks = ["compatibility", "regression"]
priorities = ["cost", "quality"]
artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]
constraints = ["Do not change public API without main-agent approval."]

[orchestration]
coordinator = "main"
topology = "flat"
max_concurrent_agents = 3
agent_direct_dispatch = false
parallel_policy = ["Read-only exploration may run with independent tests."]
serial_policy = ["Serialize edits to the same file, public API, or database schema."]
failure_flow = ["Worker BLOCKED -> main", "Test FAILED -> main -> debugger"]

[[model_registry.models]]
id = "<verified-model-id>"
availability_source = "runtime_model_registry"
capability_tier = "throughput"
cost_tier = "low"
reasoning_efforts = ["low", "medium"]
suitable_for = ["exploration", "repeatable tests", "log summarization"]

[[agents]]
name = "code_mapper"
file = ".codex/agents/code-mapper.toml"
description = "Read-only explorer for locating implementation paths before edits."
responsibilities = ["Map affected code and tests."]
boundaries = ["Do not edit files.", "Do not change product or architecture decisions."]
model = "<verified-model-id>"
model_reasoning_effort = "medium"
escalation_model = "<verified-strong-model-id>"
escalation_reasoning_effort = "high"
escalation_triggers = ["Ambiguous ownership", "Conflicting architecture artifacts"]
sandbox_mode = "read-only"
permission_boundaries = ["Read repository files; do not write or use destructive tools."]
skills = []
tools = ["repository search", "file read"]
inputs = ["Task Contract", "AGENTS.md", "Technical Spec when present"]
outputs = ["Evidence map with exact file references"]
invoke_when = ["Before a worker changes an unfamiliar module"]
parallel_groups = ["read-analysis"]
serializes_with = []
cost_tier = "low"
managed = true
```

### 3.1 顶层字段

- `schema_version`：当前固定为整数 `1`；
- `generator`：固定为 `construct-subagent`；
- `status`：验证前可在内存中视为 draft，写入就绪 Manifest 时固定为 `ready`；
- `last_changed_at`：使用带时区的 RFC 3339 时间戳，只在团队语义变化时更新。KEEP 运行不得改变；
- `project`：Project Execution Profile；
- `orchestration`：中央协调、并发、失败流和串并行约束；
- `model_registry.models`：本次设计实际引用的模型及其可用性证据；
- `agents`：活动的受管 Subagent。主 Agent 不在这里重复定义。

### 3.2 Agent 字段

每个 Agent 都必须包含示例中的全部字段。数组允许为空的只有：

- `skills`：项目没有合适 Skill 时为空并在最终结果报告 gap；
- `tools`：角色不需要额外工具时可为空；
- `serializes_with`：没有特定角色冲突时为空，但仍受全局 `serial_policy` 约束。

`parallel_groups` 至少包含一个逻辑分组。它表示可以并行的工作域，不表示同组任务天然安全；主 Agent仍需检查文件、接口、数据库和状态冲突。

`skills` 的每一项与 Agent 文件中的 `[[skills.config]] path` 一致。Skill 路径可指向含 `SKILL.md` 的目录或该 `SKILL.md` 本身；生成时优先使用目录以符合配置参考。

`sandbox_mode` 表示 Agent 文件和 Manifest 中声明的**配置默认值**，不是对 spawned Agent 最终有效权限的绝对保证。Codex 会在 spawn 时重新应用父线程当前生效的 sandbox 和 approval override；因此，配置默认值与本次父线程实际权限必须分开验证。`boundaries` 和 `permission_boundaries` 是 `developer_instructions` 实施的行为约束，不是操作系统级权限。

### 3.3 Model Registry

只登记团队实际使用的默认或升级模型。`availability_source` 必须使用以下受控值之一：

- `runtime_model_registry`：当前 Agent 工具或宿主运行时直接公开的可选模型集合；
- `codex_model_selector`：当前已认证 Codex 客户端模型选择器实际列出的模型；
- `successful_model_probe`：当前会话中对该模型的最小真实调用已经成功。

任意说明文字、公开模型文档、用户猜测、静态默认值或只存在于 Manifest 内的声明都不构成当前可用性证据。`model_catalog_json` 只有在当前 Codex 运行时已经加载并将其中模型公开为可选模型时，才能归入 `runtime_model_registry`；单独读取该文件不够。

验证时必须从上述来源取得一个独立模型集合，并通过重复的 `--available-model` 参数传入验证器；同时用 `--availability-source` 指明该集合的来源。验证器会比较外部集合、Manifest 中的 `availability_source` 以及所有默认和升级模型。Manifest 不能用自己的 `availability_source` 文字为自己作证。

`capability_tier` 使用 `strong`、`balanced` 或 `throughput`；`cost_tier` 使用 `high`、`medium` 或 `low`。这是相对成本画像，不是精确价格。

Agent 的默认与升级模型必须都在 registry 中，且 reasoning effort 必须被该模型的 `reasoning_efforts` 列出。

升级配置必须严格强于默认配置。验证器先按 `throughput < balanced < strong` 比较 `capability_tier`，能力层相同时再按 `minimal < low < medium < high < xhigh < max < ultra` 比较 reasoning effort。升级配置的二元排序必须严格更大；同一模型提高 effort 可以构成升级，同级或更弱配置不能构成升级。`suitable_for` 仍是可审查的任务适配说明，不单独作为强弱证明。

### 3.4 Runtime Permission Evidence

父线程当前生效的权限是会话事实，不写入稳定 Manifest，也不参与 `last_changed_at` 或文件 fingerprint。完成验证时必须从当前父线程上下文读取并传入：

- `--runtime-sandbox`：父线程当前生效的 sandbox；
- `--runtime-approval-policy`：父线程当前生效的 approval policy；
- `--require-runtime-permissions`：要求缺失证据或 sandbox 不一致时阻止就绪状态。

验证器逐 Agent 比较 `sandbox_mode` 配置默认值与父线程实时 sandbox。完全一致时为 `MATCH`；不一致时为 `MISMATCH`，因为父线程的实时 override 可能决定 spawned Agent 的最终 sandbox。approval policy 当前只作为父线程实时权限证据单独报告，不从提示词或 Manifest 推断。

运行时权限报告必须区分：

- `configured_sandbox_default`：Agent 文件与 Manifest 自洽的配置默认值；
- `observed_parent`：本次父线程实际观察到的 sandbox 与 approval policy；
- `comparison_status`：每个 Agent 的 `MATCH`、`MISMATCH` 或 `UNVERIFIED`；
- `behavioral_boundary_enforcement`：固定为 `developer_instructions_only`，明确行为边界不等于技术权限。

## 4. `.codex/config.toml`

项目配置至少保证：

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
```

`max_concurrent_threads_per_session` 只计 spawned Agent，不计主线程。若项目或平台限制更低，采用更低值。更新时解析现有 TOML，并对 `[agents]` 的目标标量做最小编辑；不要序列化重写整个文件。

独立 `.codex/agents/*.toml` 是当前官方首选项目发现机制，因此无需为每个 standalone Agent 再写 `[agents.<role>]` 注册项。

## 5. AGENTS.md 受控块

只有需要对所有未来任务持续生效的规则才加入：

```markdown
<!-- construct-subagent:start -->
## Agent Team Gates

- Product requirements may only be changed by the main agent with user authority.
- Failures that require public API or schema changes must be escalated to the main agent.
<!-- construct-subagent:end -->
```

已有单个完整标记块时原地更新。不存在时追加。出现半个标记、多组标记或与用户内容冲突时，停止并返回 `BLOCKED_BY_AGENTS_MD_CONFLICT`。

## 6. 生命周期与所有权

- `CREATE`：期望角色不存在；
- `UPDATE`：受管角色存在但语义与期望状态不同；
- `KEEP`：受管角色与期望状态字节一致；
- `RETIRE`：受管角色已无必要，移动到 `retired/` 并添加 `.retired` 后缀；
- `BLOCKED_BY_AGENT_CONFLICT`：同名活动文件不是受管文件，或 Manifest 所有权不清。

退役是可恢复移动，不是删除。不要自动清理 `retired/`。重新启用角色时，比较归档内容后移动、更新或创建，确保活动目录只有一个同名 Agent。

## 7. 幂等规则

以下内容不得导致变化：

- 再次运行时间；
- CREATE/UPDATE/KEEP/RETIRE 本次动作；
- 无关文件修改；
- 数组或 TOML 表的非语义性重排。

构造期望状态时使用稳定排序：模型按 `id` 严格升序，Agent 按 `name` 严格升序，集合型字符串数组按字典序；有执行顺序语义的 `failure_flow`、`parallel_policy` 和 `serial_policy` 保持逻辑顺序。每个活动 Agent 必须引用唯一的 `.codex/agents/*.toml` 文件，不能由多个 Manifest Agent 共用同一文件。`project.artifact_paths` 的每一项必须指向项目根内已存在的普通文件，不能只指向目录。

写入前比较完整目标字节。相同则不执行写操作。语义变化时统一更新 Manifest 的 `last_changed_at`，否则保留原值。

## 8. 完成 Gate

只有以下项目全部通过，才能输出 `AGENT_TEAM_READY`：

- 需求 Gate 通过；
- Project Execution Profile 完整；
- 最小充分角色和不可合并理由已经审查；
- 所有 Agent 的职责、边界、模型、权限、Skill、输入、输出和升级完整；
- 默认和升级模型均有当前可用性证据；
- 父线程实时 sandbox 和 approval policy 已独立观察，且 sandbox 与所有 Agent 配置默认值一致；
- 中央协调、失败流和串并行规则完整；
- 活动受管 Agent 无重复、无孤儿、无名称冲突；
- Manifest 的时间戳、模型/Agent 排序、Agent 文件唯一性、Artifact 文件类型和升级强度均符合本契约；
- 原生 Agent TOML、项目配置和 Manifest 可解析且一致；
- `scripts/validate_team.py` 通过；
- 第二次期望状态对账得到全 KEEP 和零文件 diff。

模型证据 Gate 使用类似以下命令；模型列表必须来自本次运行的实际来源，不要从 Manifest 反向复制：

```bash
python3 scripts/validate_team.py \
  --root <project-root> \
  --availability-source runtime_model_registry \
  --available-model <verified-default-model> \
  --available-model <verified-escalation-model> \
  --runtime-sandbox <observed-parent-sandbox> \
  --runtime-approval-policy <observed-parent-approval-policy> \
  --require-runtime-permissions
```

验证报告同时包含：

- `configuration_status`：Manifest、Agent、项目配置和文件所有权是否自洽；
- `runtime_model_availability.status`：`VERIFIED`、`UNVERIFIED` 或 `FAIL`；
- `runtime_permissions.status`：`VERIFIED`、`UNVERIFIED` 或 `MISMATCH`；
- 顶层 `status`：只有配置通过、运行时模型状态为 `VERIFIED`，并且严格模式下运行时权限状态为 `VERIFIED` 时才为 `PASS`。

`configuration_status = PASS` 不能单独支持 `AGENT_TEAM_READY`。缺少外部模型集合时，即使其他配置完全自洽，顶层状态仍必须为 `FAIL`，并报告运行时模型可用性为 `UNVERIFIED`。完成 Gate 必须使用 `--require-runtime-permissions`；缺少父线程权限证据时报告 `UNVERIFIED`，配置默认 sandbox 与父线程实时 sandbox 不一致时报告 `MISMATCH`，两者都不得宣布团队就绪。

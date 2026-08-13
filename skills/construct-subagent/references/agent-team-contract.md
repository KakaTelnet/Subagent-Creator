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
Responsibilities:
- Locate entry points, ownership boundaries, and affected tests.

Boundaries:
- Do not edit files.
- Do not redefine product requirements or architecture.
- Read repository files only.

Inputs:
- AGENTS.md
- Task Contract

Outputs:
- Return concise evidence with exact file references.

Escalation:
- Required artifacts conflict or are missing.
"""
```

Skill 绑定使用 Codex 原生配置；`path` 使用真实、已验证存在的 Skill 目录：

```toml
[[skills.config]]
path = "/absolute/path/to/a-skill"
enabled = true
```

`developer_instructions` 定义角色行为，必须包含非空的 `Responsibilities:`、`Boundaries:`、`Inputs:`、`Outputs:` 和 `Escalation:` 段。每段必须覆盖 Manifest 对应字段的原文事实；可以在这些事实之外增加自由说明，但不能省略职责、行为/权限边界、输入、输出或升级条件。它引用项目 Artifact 路径或类型，不复制 Artifact 正文。

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

[cost_profile]
objective = "minimize_total_cost"
total_cost_formula = "model_call_cost + coordination_overhead_cost"
baseline = "single-agent"
measurement_scope = "per-task"
metrics = ["agent_invocations", "coordination_overhead_cost", "coordination_tokens", "latency_ms", "model_call_cost", "model_input_tokens", "model_output_tokens", "success_rate", "total_cost"]

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
- `cost_profile`：相对单 Agent 基线衡量总费用、Token、调用次数、延迟和成功率；
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
- `project_model_allowlist`：项目受管配置明确允许的模型，仅证明配置来源；
- `successful_model_probe`：当前会话中对该模型的最小真实调用已经成功。
- `user_declared_allowlist`：用户在当前任务中明确允许的模型，仅证明配置来源。

受控来源让 Model Registry 可审查，但不自动证明当前账户能够真实调用模型。任意说明文字、公开模型文档、用户猜测或只存在于 Manifest 内的自由文本都不能充当来源。`model_catalog_json` 只有在当前 Codex 运行时已经加载并将其中模型公开为可选模型时，才能归入 `runtime_model_registry`；单独读取该文件只能作为 `project_model_allowlist`。

运行时证据分成两层：

- `--availability-source` 与重复的 `--available-model` 表示调用者从当前 runtime registry 或 model selector 观察到的模型集合，报告为 `CALLER_ASSERTED`；它比 Manifest 自述更强，但验证器不能证明调用者没有伪造参数；
- `--model-probe-source successful_model_probe` 与重复的 `--probed-model` 表示本次运行已成功真实调用的模型集合，只有覆盖全部必需模型时报告为 `VERIFIED`。

没有外部模型证据时报告 `UNVERIFIED`，但只要 Model Registry、Agent 分配和 reasoning effort 配置有效，团队配置仍可使用。若调用者主动提供了目录或探测证据，但其中缺少必需模型，则报告 `FAIL` 并阻止就绪状态。真实探测是增强证据，不是生成配置的强制前提。

`capability_tier` 使用 `strong`、`balanced` 或 `throughput`；`cost_tier` 使用 `high`、`medium` 或 `low`。这是相对成本画像，不是精确价格。

Agent 的默认与升级模型必须都在 registry 中，且 reasoning effort 必须被该模型的 `reasoning_efforts` 列出。

升级配置必须严格强于默认配置。验证器先按 `throughput < balanced < strong` 比较 `capability_tier`，能力层相同时再按 `minimal < low < medium < high < xhigh < max < ultra` 比较 reasoning effort。升级配置的二元排序必须严格更大；同一模型提高 effort 可以构成升级，同级或更弱配置不能构成升级。`suitable_for` 仍是可审查的任务适配说明，不单独作为强弱证明。

### 3.4 Cost Profile

多 Agent 通常比同类单 Agent 运行消耗更多 Token，因此“使用低价模型”不等于总 Token 或总费用一定下降。`cost_profile` 固定使用：

- `objective = "minimize_total_cost"`；
- `total_cost_formula = "model_call_cost + coordination_overhead_cost"`；
- `baseline = "single-agent"` 与 `measurement_scope = "per-task"`；
- `metrics` 同时记录模型输入/输出 Token、协调 Token、Agent 调用次数、模型费用、协调费用、总费用、端到端延迟和任务成功率。

只有相对单 Agent 基线的总费用、延迟和成功率同时可接受时，才能声称成本路由有效。不要把更低的单模型价格或某个 Agent 的 Token 降幅直接表述为整体节省。

### 3.5 Runtime Permission Evidence

权限是会话事实，不写入稳定 Manifest，也不参与 `last_changed_at` 或文件 fingerprint。验证器区分两种证据边界：

- CLI 的 `--permission-evidence-source`、`--agent-runtime-sandbox` 和 `--agent-runtime-approval-policy` 都是调用者提供的字符串，即使来源标签写成 `host_runtime` 或 `spawn_session_metadata`，也只能报告为 `CALLER_ASSERTED`；
- 只有宿主集成直接通过 Python API 提供 `HostPermissionEvidence`，且逐 Agent 证据完整、合法并匹配配置默认值时，才报告 `HOST_VERIFIED`。

CLI 可传入：

- `--permission-evidence-source host_runtime|spawn_session_metadata`：证据来源；
- `--agent-runtime-sandbox <agent>=<mode>`：该 Agent 实际生效的 sandbox；
- `--agent-runtime-approval-policy <agent>=<policy>`：该 Agent 实际生效的 approval policy；
- `--require-runtime-permissions`：要求每个 Agent 的证据完整且达到 `HOST_VERIFIED`；CLI 自报参数不能满足该严格条件。

`--runtime-sandbox` 和 `--runtime-approval-policy` 可继续记录父线程上下文，但不再拿一个父线程 sandbox 与所有 Agent 默认值逐一强制相等。验证器逐 Agent 比较自己的 `sandbox_mode` 配置默认值与该 Agent 的实际有效 sandbox，因此同一团队可以同时包含 `read-only` 和 `workspace-write` Agent。approval policy 只接受当前官方标识 `untrusted`、`on-request`、`never` 或宿主归一化的 `granular`。缺失为 `UNVERIFIED`，非法或不一致为 `MISMATCH`，完全一致为 `MATCH`。

运行时权限报告必须区分：

- `configured_sandbox_default`：Agent 文件与 Manifest 自洽的配置默认值；
- `observed_effective`：该 Agent 本次实际生效的 sandbox 与 approval policy；
- `observed_parent`：可选的父线程 sandbox 与 approval policy 上下文；
- `comparison_status`：每个 Agent 的 `MATCH`、`MISMATCH` 或 `UNVERIFIED`；
- `status`：整体为 `HOST_VERIFIED`、`CALLER_ASSERTED`、`UNVERIFIED` 或 `MISMATCH`；
- `evidence_trust`：`host_verified`、`caller_asserted` 或 `none`；
- `behavioral_boundary_enforcement`：固定为 `developer_instructions_only`，明确行为边界不等于技术权限。

### 3.6 Runtime Codex Compatibility Evidence

Codex 自定义 Agent 是原生运行时配置，格式可能随 Codex 演进。目标团队文件只能在本 Skill 已审查的兼容窗口内生成或宣布就绪：

- 最低稳定兼容版本：`0.145.0`。该版本是官方 changelog 中 multi-agent v2 标记稳定并把设置统一到 `[agents]` 的首个稳定版本；
- 最高已审查系列：`0.147.x`。patch、build metadata，以及最低稳定版本之后且仍位于已审查系列内的宿主预发布后缀不单独触发阻塞；
- `0.145.0` 自身的预发布版本仍早于最低稳定基线；
- 高于 `0.147.x` 的版本不推断向后兼容。先根据最新官方 Subagents 与 Configuration Reference 更新本契约、验证器和回归测试，再扩大窗口；
- 不设置“静默兼容”或用户文字绕过。未审查新系列必须返回 `BLOCKED_BY_CODEX_COMPATIBILITY`。

运行时版本是会话事实，不写入 `.codex/agent-team.toml`，不参与 `last_changed_at` 或文件 fingerprint。验证时必须独立观察并传入：

- `--codex-version`：`codex --version` 的原始输出，或宿主明确公开的等价当前版本；
- `--codex-version-source`：`codex_cli` 或 `host_runtime`。

验证器报告以下状态：

- `VERIFIED`：版本可解析，且处于最低稳定版本与最高已审查系列之间；
- `UNVERIFIED`：缺少版本、来源缺失/非法或版本无法解析；
- `UNSUPPORTED_OLD`：版本低于最低稳定兼容版本；
- `UNREVIEWED_NEWER`：版本高于最高已审查系列。

只有 `runtime_codex_compatibility.status = VERIFIED` 才能宣布 `AGENT_TEAM_READY`。版本检查不能替代每次运行时的官方 schema 查询；二者任一冲突都必须在写目标项目文件前阻止。

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

构造期望状态时使用稳定排序：模型按 `id` 严格升序，Agent 按 `name` 严格升序，集合型字符串数组按字典序且不得重复；有执行顺序语义的 `failure_flow`、`parallel_policy` 和 `serial_policy` 保持逻辑顺序。`serializes_with` 只能引用存在的其他 Agent，不能引用自己，并且关系必须对称。每个活动 Agent 必须引用唯一的 `.codex/agents/*.toml` 文件，不能由多个 Manifest Agent 共用同一文件。`project.artifact_paths` 的每一项必须指向项目根内已存在的普通文件，不能只指向目录。

所有受管路径及其从项目根开始的父目录都必须是普通目录或普通文件，不能是符号链接。写入前使用不跟随链接的文件状态检查；发现 `.codex`、`.codex/agents`、Manifest、项目配置、活动 Agent 或 Artifact 路径包含符号链接时，停止并返回 `BLOCKED_BY_UNSAFE_PATH`，不得读取链接目标后继续写入。

写入前比较完整目标字节。相同则不执行写操作。语义变化时统一更新 Manifest 的 `last_changed_at`，否则保留原值。

## 8. 完成 Gate

完成状态分为两层：

- `AGENT_TEAM_CONFIGURATION_READY`：Manifest、Agent 文件、项目配置、所有权、指令契约、路径安全、模型分配和编排规则自洽，可以使用配置；它不声称当前 spawned Agent 权限已经由宿主验证；
- `AGENT_TEAM_READY`：在配置就绪基础上，Codex 兼容性为 `VERIFIED`，且每个 Agent 的实际权限由宿主 API 直接提供并达到 `HOST_VERIFIED`。

只有以下项目全部通过，才能输出 `AGENT_TEAM_READY`：

- 需求 Gate 通过；
- Project Execution Profile 完整；
- 最小充分角色和不可合并理由已经审查；
- 所有 Agent 的职责、边界、模型、权限、Skill、输入、输出和升级完整；
- 默认和升级模型均有有效的受控配置来源；真实模型探测作为增强证据单独报告；
- Cost Profile 包含总费用公式以及 Token、调用次数、延迟和成功率指标；
- 当前 Codex 版本有独立来源，且运行时兼容性状态为 `VERIFIED`；
- 每个 Agent 的实际 sandbox 和 approval policy 已从可信来源独立观察，且实际 sandbox 与该 Agent 配置默认值一致；
- 中央协调、失败流和串并行规则完整；
- 活动受管 Agent 无重复、无孤儿、无名称冲突；
- 所有受管路径无符号链接，Agent instructions 覆盖 Manifest 的职责、边界、输入、输出和升级事实；
- Manifest 的时间戳、模型/Agent 排序、Agent 文件唯一性、Artifact 文件类型和升级强度均符合本契约；
- 原生 Agent TOML、项目配置和 Manifest 可解析且一致；
- `scripts/validate_team.py` 通过；
- 第二次期望状态对账得到全 KEEP 和零文件 diff。

配置与调用者声明证据可使用类似以下命令；模型列表必须来自本次运行的实际来源，不要从 Manifest 反向复制：

```bash
python3 scripts/validate_team.py \
  --root <project-root> \
  --availability-source runtime_model_registry \
  --available-model <verified-default-model> \
  --available-model <verified-escalation-model> \
  --runtime-sandbox <observed-parent-sandbox> \
  --runtime-approval-policy <observed-parent-approval-policy> \
  --permission-evidence-source spawn_session_metadata \
  --agent-runtime-sandbox <agent-name>=<observed-effective-sandbox> \
  --agent-runtime-approval-policy <agent-name>=<observed-effective-policy> \
  --codex-version <observed-codex-version> \
  --codex-version-source codex_cli
```

每个 Agent 都要重复一组 `--agent-runtime-sandbox` 与 `--agent-runtime-approval-policy`。该命令可以证明配置自洽并记录 `CALLER_ASSERTED` 权限，但因为 CLI 参数仍由调用者填写，不能单独产生 `AGENT_TEAM_READY`。只有宿主集成直接调用验证器并提供 `HostPermissionEvidence` 才能升级为 `HOST_VERIFIED`。若本次还完成了真实模型调用，可额外传入：

```bash
  --model-probe-source successful_model_probe \
  --probed-model <probed-default-model> \
  --probed-model <probed-escalation-model>
```

验证报告同时包含：

- `configuration_status`：Manifest、Agent、项目配置和文件所有权是否自洽；
- `readiness_status`：`AGENT_TEAM_CONFIGURATION_READY`、`AGENT_TEAM_READY` 或 `BLOCKED_BY_CONFIGURATION`；
- `runtime_model_availability.status`：`VERIFIED`、`CALLER_ASSERTED`、`UNVERIFIED` 或 `FAIL`；
- `runtime_permissions.status`：`HOST_VERIFIED`、`CALLER_ASSERTED`、`UNVERIFIED` 或 `MISMATCH`；
- `runtime_codex_compatibility.status`：`VERIFIED`、`UNVERIFIED`、`UNSUPPORTED_OLD` 或 `UNREVIEWED_NEWER`；
- 顶层 `status`：本次请求的验证条件是否通过；主动提供但矛盾的模型证据不得为 `FAIL`；严格模式下运行时权限必须为 `HOST_VERIFIED`，Codex 兼容性必须为 `VERIFIED`。模型真实探测不是顶层 `PASS` 的强制条件。

`configuration_status = PASS` 表示团队配置可以使用，并对应 `AGENT_TEAM_CONFIGURATION_READY`，但不能据此声称模型已经真实调用成功或 spawned Agent 权限已经由宿主验证。模型没有外部证据时报告 `UNVERIFIED`，目录证据完整时为 `CALLER_ASSERTED`，只有真实探测覆盖全部必需模型时为 `VERIFIED`。权限由 CLI 完整提供且匹配时为 `CALLER_ASSERTED`；任一 Agent 缺少证据时为 `UNVERIFIED`，值非法或实际 sandbox 与自身配置默认值不一致时为 `MISMATCH`。只有宿主直接证据为 `HOST_VERIFIED` 才能宣布 `AGENT_TEAM_READY`。Codex 版本证据缺失、过旧或高于已审查系列时不得宣布完整就绪，且不得先写目标团队文件再补做兼容性判断。

# Agent Team Contract

## 1. 输出边界

`subagent-creator` 支持两个互斥作用域：项目级和全局。默认始终是项目级；全局必须由用户在本次请求中专项声明，不得从目录、安装方式或角色可复用性推断。`project` 和 `personal` 仅作为 CLI、Manifest 与代码内部标识；面向用户统一称“项目级”和“全局”。

| 作用域 | Agent | 配置 | 生成器账本 | `AGENTS.md` |
| --- | --- | --- | --- | --- |
| 项目级（内部 `project`，默认） | `<project>/.codex/agents/<name>.toml` | `<project>/.codex/config.toml` 的 `[agents]` | `<project>/.codex/agent-team.toml` | 可选受控标记块 |
| 全局（内部 `personal`，需明确声明） | `<CODEX_HOME>/agents/<name>.toml` | `<CODEX_HOME>/config.toml` 的 `[agents]` | `<CODEX_HOME>/subagent-creator/agent-team.toml` | 不修改 |

两种作用域都可在各自 `agents/retired/<name>.toml.retired` 保存已退役且可恢复的受管定义。`CODEX_HOME` 优先使用当前环境的显式值，否则为 `~/.codex`。全局作用域的上下文根仍是当前项目或用户指定目录，只用于设计，不作为全局配置的写入根。

全局作用域的专项声明必须来自当前用户请求，例如“创建全局 Subagent”或“让所有项目可用”。历史偏好、推测或调用者自己添加 `--scope personal` 都不能替代用户授权。验证器要求同时传入 `--personal-scope-authorized`，但该标志只能记录为 `CALLER_ASSERTED`；执行 Skill 的主 Agent 仍负责核对原始用户文字，并在写入前展示解析后的 Codex Home 与精确目标文件。

不要覆盖用户拥有的 Agent、当前作用域 `config.toml` 的其他设置或 `AGENTS.md` 其他内容。

## 2. 官方 Agent 文件

每个活动 Agent 文件使用 TOML，首行固定为：

```toml
# Managed by subagent-creator. Edit via $subagent-creator.
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

`developer_instructions` 是角色行为契约的唯一事实源，必须包含非空的 `Responsibilities:`、`Boundaries:`、`Inputs:`、`Outputs:` 和 `Escalation:` 段。Manifest 不再复制这些段的正文。它引用项目 Artifact 路径或类型，不复制 Artifact 正文。

## 3. Manifest schema

当前作用域的 `agent-team.toml` 使用以下稳定结构。字段顺序按示例保持一致，便于审查和幂等比较。

```toml
schema_version = 3
generator = "subagent-creator"
status = "ready"
last_changed_at = "2026-08-13T16:31:00+08:00"
scope = "project"

[context]
summary = "One-sentence implementation profile."
artifact_paths = ["ai_docs/notes/20260813-0000_product-spec.md"]
constraints = ["Do not change public API without main-agent approval."]

[orchestration]
max_concurrent_agents = 3
parallel_policy = ["Read-only exploration may run with independent tests."]
serial_policy = ["Serialize edits to the same file, public API, or database schema."]
failure_flow = ["Worker BLOCKED -> main", "Test FAILED -> main -> debugger"]

[[model_registry.models]]
id = "<default-model-id>"
availability_source = "runtime_model_registry"
capability_tier = "throughput"
cost_tier = "low"
reasoning_efforts = ["low", "medium"]
suitable_for = ["exploration", "repeatable tests", "log summarization"]

[[model_registry.models]]
id = "<strong-model-id>"
availability_source = "runtime_model_registry"
capability_tier = "strong"
cost_tier = "high"
reasoning_efforts = ["high", "medium"]
suitable_for = ["architecture decisions", "complex debugging"]

[[agents]]
name = "code_mapper"
file = ".codex/agents/code-mapper.toml"
description = "Read-only explorer for locating implementation paths before edits."
model = "<default-model-id>"
model_reasoning_effort = "medium"
escalation_model = "<strong-model-id>"
escalation_reasoning_effort = "high"
sandbox_mode = "read-only"
skills = []
invoke_when = ["Before a worker changes an unfamiliar module"]
serializes_with = []
cost_tier = "low"
managed = true
```

### 3.1 顶层字段

- `schema_version`：新生成 Manifest 固定为整数 `3`；验证器继续只读兼容仅支持项目级作用域的旧版 `1` 和 `2`；
- `generator`：固定为 `subagent-creator`；
- `status`：验证前可在内存中视为 draft，写入就绪 Manifest 时固定为 `ready`；
- `last_changed_at`：使用带时区的 RFC 3339 时间戳，只在团队语义变化时更新。KEEP 运行不得改变；
- `scope`：固定为内部标识 `project` 或 `personal`，且必须与调用验证器时选择的作用域一致；
- `context`：仅保留重新生成所需的摘要、Artifact 路径和约束；全局作用域的 `artifact_paths` 必须为空，防止全局 Agent 固化项目依赖；
- `orchestration`：中央协调、并发、失败流和串并行约束；
- `model_registry.models`：本次设计实际引用的模型及其可用性证据；
- `agents`：活动的受管 Subagent。主 Agent 不在这里重复定义。

### 3.2 Agent 字段

Manifest 是生成器的轻量账本，不是第二份 Agent prompt。每个 Agent 只保存所有权、模型路由、配置默认 sandbox、Skill 绑定、调用时机和串行冲突。职责、边界、输入、输出与升级触发正文只写入原生 Agent TOML 的 `developer_instructions`。

每个 Agent 都必须包含示例中的全部字段。数组允许为空的只有：

- `skills`：项目没有合适 Skill 时为空并在最终结果报告 gap；
- `serializes_with`：没有特定角色冲突时为空，但仍受全局 `serial_policy` 约束。

`skills` 的每一项与 Agent 文件中的 `[[skills.config]] path` 一致。Skill 路径可指向含 `SKILL.md` 的目录或该 `SKILL.md` 本身；生成时优先使用目录以符合配置参考。

`sandbox_mode` 表示 Agent 文件和 Manifest 中声明的**配置默认值**，不是对 spawned Agent 最终有效权限的绝对保证。Codex 会在 spawn 时重新应用父线程当前生效的 sandbox 和 approval override；因此，配置默认值与本次父线程实际权限必须分开验证。`developer_instructions` 中的 `Boundaries:` 是行为约束，不是操作系统级权限。

项目级作用域的 `agents.file` 使用项目相对路径，例如 `.codex/agents/code-mapper.toml`；全局作用域使用 Codex Home 相对路径，例如 `agents/code-mapper.toml`。两者都禁止绝对路径和 `..`。全局 Agent 的 instructions 不得嵌入上下文项目的路径、私有 API 或只在该项目存在的 Artifact。

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

`capability_tier` 使用 `strong`、`balanced` 或 `throughput`；`cost_tier` 使用 `high`、`medium` 或 `low`。这是相对成本画像，不是精确价格。在满足能力和失败风险要求的前提下优先选择相对低成本模型；本 Skill 不采集运行指标，也不证明多 Agent 一定更省。

Agent 的默认与升级模型必须都在 registry 中，且 reasoning effort 必须被该模型的 `reasoning_efforts` 列出。

升级配置必须严格强于默认配置。验证器先按 `throughput < balanced < strong` 比较 `capability_tier`，能力层相同时再按 `minimal < low < medium < high < xhigh < max < ultra` 比较 reasoning effort。升级配置的二元排序必须严格更大；同一模型提高 effort 可以构成升级，同级或更弱配置不能构成升级。`suitable_for` 仍是可审查的任务适配说明，不单独作为强弱证明。

### 3.4 Runtime Permission Evidence

权限是会话事实，不写入稳定 Manifest，也不参与 `last_changed_at` 或文件 fingerprint。验证器区分两种证据边界：

- CLI 的 `--permission-evidence-source`、`--agent-runtime-sandbox` 和 `--agent-runtime-approval-policy` 都是调用者提供的字符串，即使来源标签写成 `host_runtime` 或 `spawn_session_metadata`，也只能报告为 `CALLER_ASSERTED`；
- 只有宿主集成直接通过 Python API 提供 `HostPermissionEvidence`，且逐 Agent 证据完整、合法并匹配配置默认值时，才报告 `HOST_VERIFIED`。

CLI 可传入：

- `--permission-evidence-source host_runtime|spawn_session_metadata`：证据来源；
- `--agent-runtime-sandbox <agent>=<mode>`：该 Agent 实际生效的 sandbox；
- `--agent-runtime-approval-policy <agent>=<policy>`：该 Agent 实际生效的 approval policy；
- `--require-host-readiness`：显式要求可选的 `AGENT_TEAM_READY` 宿主增强，必须同时取得 `HOST_VERIFIED` 权限与兼容的运行时版本；CLI 自报参数不能满足该严格条件。`--require-runtime-permissions` 保留为兼容别名。

`--runtime-sandbox` 和 `--runtime-approval-policy` 可继续记录父线程上下文，但不再拿一个父线程 sandbox 与所有 Agent 默认值逐一强制相等。验证器逐 Agent 比较自己的 `sandbox_mode` 配置默认值与该 Agent 的实际有效 sandbox，因此同一团队可以同时包含 `read-only` 和 `workspace-write` Agent。approval policy 只接受当前官方标识 `untrusted`、`on-request`、`never` 或宿主归一化的 `granular`。缺失为 `UNVERIFIED`，非法或不一致为 `MISMATCH`，完全一致为 `MATCH`。

运行时权限报告必须区分：

- `configured_sandbox_default`：Agent 文件与 Manifest 自洽的配置默认值；
- `observed_effective`：该 Agent 本次实际生效的 sandbox 与 approval policy；
- `observed_parent`：可选的父线程 sandbox 与 approval policy 上下文；
- `comparison_status`：每个 Agent 的 `MATCH`、`MISMATCH` 或 `UNVERIFIED`；
- `status`：整体为 `HOST_VERIFIED`、`CALLER_ASSERTED`、`UNVERIFIED` 或 `MISMATCH`；
- `evidence_trust`：`host_verified`、`caller_asserted` 或 `none`；
- `behavioral_boundary_enforcement`：固定为 `developer_instructions_only`，明确行为边界不等于技术权限。

### 3.5 Codex Schema 与可选运行时兼容证据

Codex 自定义 Agent 是原生运行时配置，格式可能随 Codex 演进。本 Skill 通过两种互不替代的检查控制风险：

- 默认、本地、离线检查：严格验证本 Skill 会生成的 Agent 字段、`skills.config` 与项目 `[agents]` 字段；这是 `AGENT_TEAM_CONFIGURATION_READY` 的强制条件；
- CI 官方兼容检查：下载当前官方 Codex JSON Schema 和 Subagents 文档，确认本地投影中的每个字段仍受支持。官方新增字段不会自动扩大本地生成范围；字段被移除或改名时 CI 失败，必须先更新契约、验证器和测试；
- 可选宿主增强：记录当前 Codex 版本，判断该具体宿主是否位于已审查运行时窗口。缺少版本证据不阻止配置生成，只使宿主兼容性保持 `UNVERIFIED`，因此不能升级为 `AGENT_TEAM_READY`。

当前可选运行时窗口为：

- 最低稳定兼容版本：`0.145.0`。该版本是官方 changelog 中 multi-agent v2 标记稳定并把设置统一到 `[agents]` 的首个稳定版本；
- 最高已审查系列：`0.147.x`。patch、build metadata，以及最低稳定版本之后且仍位于已审查系列内的宿主预发布后缀不单独触发阻塞；
- `0.145.0` 自身的预发布版本仍早于最低稳定基线；
- 高于 `0.147.x` 的版本不推断向后兼容。先根据最新官方 Subagents 与 Configuration Reference 更新本契约、验证器和回归测试，再扩大窗口；
- 显式提供的版本过旧、格式错误或属于未审查新系列时，运行时兼容检查失败；`configuration_status` 仍独立反映文件配置是否有效。

运行时版本是会话事实，不写入当前作用域的 `agent-team.toml`，不参与 `last_changed_at` 或文件 fingerprint。需要宿主增强时独立观察并传入：

- `--codex-version`：`codex --version` 的原始输出，或宿主明确公开的等价当前版本；
- `--codex-version-source`：`codex_cli` 或 `host_runtime`。

验证器报告以下状态：

- `VERIFIED`：版本可解析，且处于最低稳定版本与最高已审查系列之间；
- `UNVERIFIED`：缺少版本、来源缺失/非法或版本无法解析；
- `UNSUPPORTED_OLD`：版本低于最低稳定兼容版本；
- `UNREVIEWED_NEWER`：版本高于最高已审查系列。

只有 `runtime_codex_compatibility.status = VERIFIED` 才能宣布 `AGENT_TEAM_READY`。它不是 `AGENT_TEAM_CONFIGURATION_READY` 的前提，也不能替代本地严格 Schema 检查或 CI 官方兼容检查。若执行 Skill 时最新官方文档已与本地投影冲突，返回 `BLOCKED_BY_CODEX_COMPATIBILITY`，不要生成未知格式。

## 4. 作用域配置

当前作用域的 `config.toml` 至少保证：

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
```

`max_concurrent_threads_per_session` 只计 spawned Agent，不计主线程。若项目或平台限制更低，采用更低值。更新时解析现有 TOML，并对 `[agents]` 的目标标量做最小编辑；不要序列化重写整个文件。

独立 Agent TOML 是当前官方首选发现机制，因此无需为每个 standalone Agent 再写 `[agents.<role>]` 注册项。项目级作用域使用 `.codex/agents/*.toml`；全局作用域使用 `<CODEX_HOME>/agents/*.toml`。更新全局 `config.toml` 时同样只允许最小修改 `[agents]`，不得重写用户的模型、MCP、approval 或其他全局设置。

## 5. AGENTS.md 受控块

只有需要对所有未来任务持续生效的规则才加入：

```markdown
<!-- subagent-creator:start -->
## Agent Team Gates

- Product requirements may only be changed by the main agent with user authority.
- Failures that require public API or schema changes must be escalated to the main agent.
<!-- subagent-creator:end -->
```

已有单个完整标记块时原地更新。不存在时追加。出现半个标记、多组标记或与用户内容冲突时，停止并返回 `BLOCKED_BY_AGENTS_MD_CONFLICT`。

本节仅适用于项目级作用域。全局作用域不得向上下文项目或任何其他项目写入 `AGENTS.md`。

## 6. 生命周期与所有权

- `CREATE`：期望角色不存在；
- `UPDATE`：受管角色存在但语义与期望状态不同；
- `KEEP`：受管角色与期望状态字节一致；
- `RETIRE`：受管角色已无必要，移动到当前作用域的 `agents/retired/` 并添加 `.retired` 后缀；
- `BLOCKED_BY_AGENT_CONFLICT`：同名活动文件不是受管文件，或 Manifest 所有权不清。

退役是可恢复移动，不是删除。不要自动清理 `retired/`。重新启用角色时，比较归档内容后移动、更新或创建，确保活动目录只有一个同名 Agent。生成前同时检查上下文项目和当前全局 Agent 目录；同名跨作用域定义可能造成发现歧义，必须返回 `BLOCKED_BY_AGENT_CONFLICT` 并交由用户改名或退休其中一个。

## 7. 幂等规则

以下内容不得导致变化：

- 再次运行时间；
- CREATE/UPDATE/KEEP/RETIRE 本次动作；
- 无关文件修改；
- 数组或 TOML 表的非语义性重排。

构造期望状态时使用稳定排序：模型按 `id` 严格升序，Agent 按 `name` 严格升序，集合型字符串数组按字典序且不得重复；有执行顺序语义的 `failure_flow`、`parallel_policy` 和 `serial_policy` 保持逻辑顺序。`serializes_with` 只能引用存在的其他 Agent，不能引用自己，并且关系必须对称。每个活动 Agent 必须引用当前作用域唯一的 Agent TOML 文件，不能由多个 Manifest Agent 共用同一文件。项目级作用域的 `context.artifact_paths` 每一项必须指向项目根内已存在的普通文件，不能只指向目录；全局作用域必须为空。

所有受管路径及其从对应作用域根开始的父目录都必须是普通目录或普通文件，不能是符号链接。项目级作用域从项目根检查；全局作用域从 Codex Home 检查。写入前使用不跟随链接的文件状态检查；发现目标配置目录、Agent、Manifest、配置或项目 Artifact 路径包含符号链接时，停止并返回 `BLOCKED_BY_UNSAFE_PATH`，不得读取链接目标后继续写入。

写入前比较完整目标字节。相同则不执行写操作。语义变化时统一更新 Manifest 的 `last_changed_at`，否则保留原值。

## 8. 完成 Gate

完成状态分为两层：

- `AGENT_TEAM_CONFIGURATION_READY`：Manifest、Agent 文件、作用域配置、所有权、指令契约、路径安全、模型分配和编排规则自洽，可以使用配置；它不声称当前 spawned Agent 权限已经由宿主验证；
- `AGENT_TEAM_READY`：在配置就绪基础上，Codex 兼容性为 `VERIFIED`，且每个 Agent 的实际权限由宿主 API 直接提供并达到 `HOST_VERIFIED`。

正常完成以下项目后输出 `AGENT_TEAM_CONFIGURATION_READY`，并以退出码 `0` 结束：

- 作用域已锁定；全局作用域具有用户本次请求中的专项声明，项目级作用域无需声明；
- 对应作用域的需求 Gate 通过；
- 已分析执行特点，Manifest 只保留重新生成所需的摘要、Artifact 和约束；全局作用域不保留项目 Artifact；
- 最小充分角色和不可合并理由已经审查；
- 所有 Agent 的职责、边界、模型、权限、Skill、输入、输出和升级完整；
- 默认和升级模型均有有效的受控配置来源；真实模型探测作为增强证据单独报告；
- 中央协调、失败流和串并行规则完整；
- 活动受管 Agent 无重复、无孤儿、无名称冲突；
- 所有受管路径无符号链接，原生 Agent instructions 的五个行为段均非空；
- Manifest 的时间戳、模型/Agent 排序、Agent 文件唯一性、Artifact 文件类型和升级强度均符合本契约；
- 原生 Agent TOML、作用域配置和 Manifest 可解析且一致，并通过本地严格 Codex Schema 投影；
- `scripts/validate_team.py` 通过；
- 第二次期望状态对账得到全 KEEP 和零文件 diff。

正常配置验证不要求任何宿主或真实调用证据：

```bash
python3 scripts/validate_team.py --root <project-root>
```

全局作用域只有在用户已明确声明时使用，并要求显式授权参数；`personal` 仅是机器接口标识：

```bash
python3 scripts/validate_team.py \
  --root <context-root> \
  --scope personal \
  --codex-home <codex-home> \
  --personal-scope-authorized
```

只有在配置就绪基础上，当前 Codex 版本具有独立来源且为 `VERIFIED`，并且每个 Agent 的实际 sandbox 与 approval policy 由可信宿主直接观察、匹配配置默认值且达到 `HOST_VERIFIED`，才升级为可选的 `AGENT_TEAM_READY`。

配置与调用者声明证据可使用类似以下增强命令；模型列表必须来自本次运行的实际来源，不要从 Manifest 反向复制：

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

- `scope`：请求作用域、Manifest 作用域、全局授权状态及实际受管路径；
- `configuration_status`：Manifest、Agent、作用域配置和文件所有权是否自洽；
- `local_codex_schema.status`：受管 Agent TOML 和当前作用域 `[agents]` 是否通过本 Skill 的离线严格字段投影；
- `readiness_status`：`AGENT_TEAM_CONFIGURATION_READY`、`AGENT_TEAM_READY` 或 `BLOCKED_BY_CONFIGURATION`；
- `runtime_model_availability.status`：`VERIFIED`、`CALLER_ASSERTED`、`UNVERIFIED` 或 `FAIL`；
- `runtime_permissions.status`：`HOST_VERIFIED`、`CALLER_ASSERTED`、`UNVERIFIED` 或 `MISMATCH`；
- `runtime_codex_compatibility.status`：`VERIFIED`、`UNVERIFIED`、`UNSUPPORTED_OLD` 或 `UNREVIEWED_NEWER`；
- 顶层 `status`：本次请求的验证条件是否通过。默认情况下配置有效即可为 `PASS`；主动提供但不完整、非法或矛盾的外部证据会使本次请求为 `FAIL`，但不会篡改独立的 `configuration_status`；`--require-host-readiness` 模式还要求权限为 `HOST_VERIFIED`、Codex 兼容性为 `VERIFIED`。模型真实探测不是顶层 `PASS` 的强制条件。

`configuration_status = PASS` 表示团队配置可以使用，并对应 `AGENT_TEAM_CONFIGURATION_READY`，但不能据此声称模型已经真实调用成功或 spawned Agent 权限已经由宿主验证。模型没有外部证据时报告 `UNVERIFIED`，目录证据完整时为 `CALLER_ASSERTED`，只有真实探测覆盖全部必需模型时为 `VERIFIED`。权限由 CLI 完整提供且匹配时为 `CALLER_ASSERTED`；任一 Agent 缺少证据时为 `UNVERIFIED`，值非法或实际 sandbox 与自身配置默认值不一致时为 `MISMATCH`。只有宿主直接证据为 `HOST_VERIFIED` 才能宣布 `AGENT_TEAM_READY`。Codex 版本缺失时仅保持 `UNVERIFIED`；显式过旧、非法或高于已审查系列的证据会使增强检查失败。

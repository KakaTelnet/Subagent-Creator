# Subagent Creator

- 本 Skill 用于创建可由主 Agent 调度的 Codex Subagent；默认只在当前项目生效，用户明确声明时也可创建全局 Agent，供所有项目使用。
- 子 Agent 按照职责、风险和调用频率选择当前可用模型：
  - 强推理模型用于架构判断、复杂调试和高风险审查；
  - 平衡型执行模型用于主要实现和边界明确的修复；
  - 低成本高吞吐模型用于检索、重复测试和日志归纳。

## Demo

下面是一种可能的团队配置。实际角色、模型和数量会根据项目需求与当前可用模型动态调整。

```text
主线程：强推理模型
负责总体规划、拆解、调度和最终验收

├─ coder：平衡型执行模型
│  负责实现和修复代码
│
├─ tester：低成本高吞吐模型
│  负责运行测试、补充测试、整理失败信息
│
└─ debugger：强推理模型
   负责分析复杂失败、重新形成修复方案
```

# 详细介绍

## 背景

Codex Subagent 可以并行承担代码检索、实现、测试、调试和审查，但“能创建很多 Agent”并不等于“应该创建很多 Agent”。手工配置团队时，常见问题包括：

- 套用固定角色模板，项目越简单，额外协调成本反而越高；
- 所有任务都使用高成本模型，重复检索和批量检查消耗过多资源；
- 把公开模型列表误当成当前账户真实可用的模型，配置生成后无法运行；
- 在过旧或尚未审查的新 Codex 版本中沿用旧 Agent schema，导致配置与运行时冲突；
- 混淆 Agent 的默认 sandbox、父线程实时权限和提示词行为约束，导致安全边界被夸大；
- 再次生成配置时覆盖用户维护的 Agent，或仅因时间变化制造无意义 diff；
- 配置文件能够解析，就直接宣布团队可用，却没有验证模型、权限和文件所有权。

`subagent-creator` 把这些问题收敛为一条可重复执行的工作流：

```text
项目事实
  -> 本地严格 Codex Schema 投影
  -> 需求就绪 Gate
  -> 受控模型 Registry
  -> Execution Profile
  -> 最小充分角色与串并行规则
  -> 受控写入和幂等对账
  -> 配置验证 + 可选宿主增强证据
```

Skill 使用三级就绪状态：配置与项目持久接线自洽时返回 `AGENT_TEAM_CONFIGURATION_READY`；可信宿主进一步验证模型目录、逐 Agent 权限和 Codex 兼容性后返回 `AGENT_TEAM_RUNTIME_READY`；全部引用模型都由可信宿主完成真实调用后才返回 `AGENT_TEAM_VERIFIED`。全局作用域只是可复用角色库，最高只报告配置就绪。

## 它解决什么问题

`subagent-creator` 不是一套固定的 planner/coder/tester 模板。它会读取明确的需求、当前上下文和运行时能力，判断需要哪些执行角色，再生成对应作用域的 Codex Agent 配置。简单需求可以只有少量角色；只有当模型、权限、上下文隔离、并行边界或验证职责确实不同，才会拆出新的 Agent。

### 默认项目级，显式选择全局

Skill 支持两个作用域：

| 作用域 | 何时使用 | Agent 位置 | 生成器账本 |
| --- | --- | --- | --- |
| `project` | 默认；只服务当前仓库 | `<project>/.codex/agents/*.toml` | `<project>/.codex/agent-team.toml` |
| 全局（内部标识 `personal`） | 用户在本次请求中明确说“全局”或“所有项目可用” | `<CODEX_HOME>/agents/*.toml`，默认即 `~/.codex/agents/*.toml` | `<CODEX_HOME>/subagent-creator/agent-team.toml` |

没有全局专项声明时，Skill 不会询问或推断，直接生成项目级配置。全局写入前会复述实际 Codex Home 和目标路径；它不会修改上下文项目的 `AGENTS.md`，也不会把某个项目的私有路径固化进全局 Agent。

### 按项目设计团队，而不是套模板

Skill 会分析项目规模、技术复杂度、主要任务、共享文件、公共接口、数据库状态和回归风险。两个职责相近且权限、模型和并行域相同的角色会被合并；没有当前需求依据的角色不会被提前创建。

### 把模型成本用在正确的位置

高吞吐、低成本模型适合只读探索、重复测试和日志归纳；强模型保留给架构判断、复杂故障和高风险审查。默认模型总会写入团队 Manifest；只有存在明确、更强且可用的候选时才写可选升级模型，否则失败直接返回主 Agent。验证结果会区分配置有效、调用者转述、可信运行时目录和真实调用探测。

成本只用于生成配置时的模型路由：在满足能力和失败风险要求的前提下，优先让高频、低风险、边界清楚的工作使用相对低成本模型。本 Skill 不采集实际 Token、费用、调用次数、延迟或成功率，也不证明多 Agent 一定更省。

### 明确权限的三层含义

生成结果会分别记录：

- Agent 文件中的 `sandbox_mode` 配置默认值；
- 每个 Agent 本次运行实际生效的 sandbox 和 approval policy；
- 父线程本次运行的权限上下文；
- 只能依靠 `developer_instructions` 约束的角色行为边界。

它不会把“提示词要求只读”描述成系统级只读，也不会用父线程的单一 sandbox 错误否定由 `read-only` 与 `workspace-write` 组成的混合权限团队。严格验证会逐 Agent 对比配置默认值和实际有效权限。命令行转述的权限证据只标记为 `CALLER_ASSERTED`；只有宿主 API 直接提供的证据才能标记为 `HOST_VERIFIED`。

### 安全地演进已有团队

Skill 只管理带有明确所有权标记的 Agent 文件，并使用 `CREATE`、`UPDATE`、`KEEP`、`RETIRE` 对账期望状态。用户维护的 Agent 和无关配置会被保留；退役角色会进入可恢复的 `retired/` 目录，而不是被直接删除。相同事实再次执行提示词驱动的期望状态对账时，应得到全 `KEEP` 和零文件 diff。验证器 fingerprint 只证明现有受检文件稳定，最终幂等证据来自第二次对账和实际 diff。

受管路径及其从作用域根开始的父目录不能是符号链接。发现目标 Codex 配置目录、Agent、Manifest、配置或项目 Artifact 路径包含链接时，Skill 会停止并返回 `BLOCKED_BY_UNSAFE_PATH`，避免读取一个路径却覆盖另一个文件。

## 使用前提

使用前，请确认：

- 产品结果、主要范围、非目标和关键约束已经明确；
- 项目中有可供读取的 Product Spec、Change Spec、Technical Spec、Architecture 或等价事实来源；
- 项目、用户或当前 Codex 运行时能提供明确的模型 allowlist；真实模型调用探测是可选的增强证据；
- 若希望取得可选的 `AGENT_TEAM_RUNTIME_READY` 或 `AGENT_TEAM_VERIFIED`，需要可信宿主集成直接提供模型目录、逐 Agent 权限、Codex 版本和必要时的真实调用证据，且版本位于本 Skill 已审查的 `0.145.0` 至 `0.147.x` 兼容窗口；普通配置生成不要求这些证据；
- 允许 Skill 在目标作用域维护 Codex 配置；全局写入还必须由用户在本次请求中明确声明；
- 目标项目能提供由 pyenv 管理、Python 3.11 或更高版本的虚拟环境，用于运行只读验证器。

如果需求歧义会改变团队形态，Skill 会返回 `BLOCKED_BY_REQUIREMENTS`，不会先猜测需求再写配置。

## 安装

### 作为本地 Skill 使用

克隆仓库后，把完整的 `skills/subagent-creator/` 目录复制到 Codex 的用户级 Skill 目录：

```bash
git clone https://github.com/KakaTelnet/Subagent-Creator.git
mkdir -p ~/.agents/skills
cp -R Subagent-Creator/skills/subagent-creator ~/.agents/skills/
```

Codex 会从 `$HOME/.agents/skills` 发现用户级 Skill。如果安装后没有立即出现，请重启 Codex。也可以把该目录放入目标仓库的 `.agents/skills/`，让 Skill 只对该仓库生效。

### 作为 Plugin 使用

仓库同时提供 `.codex-plugin/plugin.json` 和单 Plugin marketplace。通过 Codex CLI 添加该公开 marketplace：

```bash
codex plugin marketplace add KakaTelnet/Subagent-Creator --ref main
codex plugin marketplace list
```

然后重启 ChatGPT 桌面应用，在 Plugins Directory 中选择 `Subagent Creator` 来源并安装。后续可使用以下命令获取 marketplace 更新：

```bash
codex plugin marketplace upgrade subagent-creator
```

Skill 目录安装和 Plugin marketplace 安装提供的是同一个 `$subagent-creator`。通常选择一种渠道即可；若同时安装，Codex 可能显示两个同名 Skill。Plugin 打包与 marketplace 规则参见 OpenAI 官方的 [Package your plugin](https://developers.openai.com/plugins/build/plugins) 文档。

## 快速开始

在**需要配置 Subagent 团队的目标项目根目录**打开 Codex，然后输入：

```text
使用 $subagent-creator，根据这个项目当前的需求、代码和验证约束，构建最小充分的 Codex Subagent 团队。
```

也可以附加成本、质量或并发偏好，例如：

```text
使用 $subagent-creator 为当前项目构建团队。优先控制成本；只读探索和重复测试尽量使用低成本模型，高风险审查保留强模型，并发上限为 3。
```

Skill 随后会：

1. 读取适用的 `AGENTS.md`、Git 状态、产品/技术/验证文档和现有 Agent 配置；
2. 使用离线严格字段投影检查将生成的原生 Agent 配置，并在可用时分层记录调用者转述或宿主直证的 Codex 版本；
3. 检查需求是否足以决定团队形态；
4. 从受控 allowlist 建立模型 Registry，并在可用时附加运行时目录或真实调用证据；
5. 生成 Execution Profile，并推导最小充分角色；
6. 定义每个角色的职责、边界、默认模型、可选升级条件、权限、输入输出和并行规则；
7. 对账并最小化修改当前作用域配置；
8. 运行验证器，并再次对账以确认幂等性。

上面的请求默认生成项目级 Agent。若确实希望所有项目都可发现，必须专项声明，例如：

```text
使用 $subagent-creator 创建全局 Subagent，让它在所有 Codex 项目中可用。请写入我的 Codex Home，不要生成项目级 Agent。
```

全局角色应描述可复用工作，而不是绑定当前仓库。例如“只读审查文档一致性”适合全局作用域；“修改这个项目的支付模块”应保留为项目级作用域。

## 生成结果

根据作用域，Skill 可能维护以下内容：

| 文件 | 作用 |
| --- | --- |
| 项目级：`.codex/agent-team.toml`；全局：`<CODEX_HOME>/subagent-creator/agent-team.toml` | 轻量生成器账本，记录作用域、所有权、模型路由、调用时机和编排规则；不复制 Agent prompt |
| 项目级：`.codex/agents/*.toml`；全局：`<CODEX_HOME>/agents/*.toml` | Codex 原生自定义 Agent 定义 |
| 当前作用域 `config.toml` 的 `[agents]` | Agent 启用状态和并发上限；不会重写其他设置 |
| 项目根当前生效的 `AGENTS.override.md` 或 `AGENTS.md` 受控标记块 | 项目级 Manifest v4 的必需持久调度入口；全局角色库不修改 |
| 当前作用域 `agents/retired/*.toml.retired` | 已退役但可恢复的受管 Agent |

完成报告会给出：

- `AGENT_TEAM_CONFIGURATION_READY`、`AGENT_TEAM_RUNTIME_READY`、`AGENT_TEAM_VERIFIED` 或明确的 BLOCKED 状态；
- 每个角色的 `CREATE` / `UPDATE` / `KEEP` / `RETIRE` 动作；
- 默认模型、可选升级模型、sandbox、职责和调用时机；
- 中央协调、失败升级、并行和串行规则；
- 模型配置、目录声明与真实探测的分层状态，以及 Codex 版本兼容性、逐 Agent 运行时权限和配置一致性的验证结果；
- 实际写入的文件及运行过的验证命令。

## 何时不应该使用

以下工作不属于本 Skill：

- 定义产品需求或替用户解决重大需求歧义；
- 完成整套技术架构设计；
- 把需求拆成实施 Task；
- 编写业务代码、执行产品测试或给出最终验收结论；
- 在没有受控模型 allowlist 时猜测模型配置，或把没有真实调用的模型描述为探测通过。

这些工作应该先由相应的产品、架构、Task Engineering 或开发流程完成，再使用 `subagent-creator` 配置执行团队。

## 验证器

Skill 包含只读验证器 `skills/subagent-creator/scripts/validate_team.py`。它会联合检查轻量 Manifest、Agent TOML 的严格本地 Codex 字段投影、五段原生指令契约、Skill 路径、模型分配、升级强度、相对成本层级、文件所有权、符号链接和项目并发配置。逐 Agent 实际权限、真实模型调用与当前 Codex 版本属于独立的可选增强证据。

验证器要求 Python 3.11+；无法取得该环境时返回 `BLOCKED_BY_VALIDATION_ENVIRONMENT`，不授予 READY。默认只传 `--root` 时验证项目级配置和持久接线，配置通过即返回 `AGENT_TEAM_CONFIGURATION_READY`。全局角色库必须同时传入 `--scope personal --codex-home <path> --personal-scope-authorized`。CLI 模型目录、模型探测、权限和 Codex 版本证据分别只达到 `CALLER_ASSERTED`、`CALLER_PROBED`、`CALLER_ASSERTED` 和 `CALLER_ASSERTED`；只有宿主通过 Python API 直接提供 `HostModelEvidence`、`HostPermissionEvidence` 与 `HostCodexVersionEvidence` 才能升级到 runtime-ready 或 verified。

## 仓库验证

仓库测试使用隔离 fixture 覆盖 Manifest v1–v3 读取兼容与 v4 持久接线、默认项目级行为、全局显式授权、可选升级、混合权限、模型/权限证据分层、本地严格 Codex 字段、指令契约、符号链接、相对成本层级和失败路径，不要求 CI 真实调用模型。CI 会读取当前官方 Codex JSON Schema 与 Subagents 文档，确认本 Skill 生成字段的存在性、类型和关键约束仍受支持；官方新增字段不会自动放宽本地严格范围。

```bash
source ./venv/bin/activate
which python3
which pip3
python3 -m unittest discover -s tests -p 'test_*.py' -v
agentskills validate skills/subagent-creator
python3 scripts/validate_plugin.py .
python3 scripts/check_official_codex_schema.py
python3 scripts/check_official_plugin_schema.py
```

## 开发与贡献

贡献边界、虚拟环境要求和验证命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。

## 许可证

开源版本采用 [AGPL-3.0-only](LICENSE)；需要闭源使用时可申请[商业许可证](COMMERCIAL-LICENSE.md)。Skill 生成的 Agent 配置归使用者所有，不会仅因由本项目生成而自动适用 AGPL。

Copyright (C) 2026 KakaTelnet and contributors.

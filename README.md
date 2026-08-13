# Construct Subagent

为Codex项目创建多路子Agent，以供主Agent按需调度。
子Agent按照功能配置对应的模型。
使用Luna低成本模型应对检索、重复测试、日志归纳等低推理需求。
核心模块开发使用Sol等高级模型以保证质量。

## 背景

Codex Subagent 可以并行承担代码检索、实现、测试、调试和审查，但“能创建很多 Agent”并不等于“应该创建很多 Agent”。手工配置团队时，常见问题包括：

- 套用固定角色模板，项目越简单，额外协调成本反而越高；
- 所有任务都使用高成本模型，重复检索和批量检查消耗过多资源；
- 把公开模型列表误当成当前账户真实可用的模型，配置生成后无法运行；
- 混淆 Agent 的默认 sandbox、父线程实时权限和提示词行为约束，导致安全边界被夸大；
- 再次生成配置时覆盖用户维护的 Agent，或仅因时间变化制造无意义 diff；
- 配置文件能够解析，就直接宣布团队可用，却没有验证模型、权限和文件所有权。

`construct-subagent` 把这些问题收敛为一条可重复执行的工作流：

```text
项目事实
  -> 需求就绪 Gate
  -> 当前可用模型 Registry
  -> Project Execution Profile
  -> 最小充分角色与串并行规则
  -> 受控写入和幂等对账
  -> 模型、权限、配置联合验证
```

只有全部 Gate 和验证都通过，Skill 才会返回 `AGENT_TEAM_READY`。

## 它解决什么问题

`construct-subagent` 不是一套固定的 planner/coder/tester 模板。它会读取当前项目的真实文档、代码、配置和运行时能力，判断项目此刻需要哪些执行角色，再生成项目级 Codex Agent 配置。简单项目可以只有少量角色；只有当模型、权限、上下文隔离、并行边界或验证职责确实不同，才会拆出新的 Agent。

### 按项目设计团队，而不是套模板

Skill 会分析项目规模、技术复杂度、主要任务、共享文件、公共接口、数据库状态和回归风险。两个职责相近且权限、模型和并行域相同的角色会被合并；没有当前需求依据的角色不会被提前创建。

### 把模型成本用在正确的位置

高吞吐、低成本模型适合只读探索、重复测试和日志归纳；强模型保留给架构判断、复杂故障和高风险审查。默认模型与升级模型都会写入团队 Manifest，并要求具备本次运行观察到的可用性证据。

### 明确权限的三层含义

生成结果会分别记录：

- Agent 文件中的 `sandbox_mode` 配置默认值；
- 父线程本次运行实际生效的 sandbox 和 approval policy；
- 只能依靠 `developer_instructions` 约束的角色行为边界。

它不会把“提示词要求只读”描述成系统级只读，也不会忽略父线程权限对 spawned Agent 的影响。

### 安全地演进已有团队

Skill 只管理带有明确所有权标记的 Agent 文件，并使用 `CREATE`、`UPDATE`、`KEEP`、`RETIRE` 对账期望状态。用户维护的 Agent 和无关配置会被保留；退役角色会进入可恢复的 `retired/` 目录，而不是被直接删除。相同输入再次运行时应得到全 `KEEP` 和零文件 diff。

## 使用前提

使用前，请确认：

- 产品结果、主要范围、非目标和关键约束已经明确；
- 项目中有可供读取的 Product Spec、Change Spec、Technical Spec、Architecture 或等价事实来源；
- 当前 Codex 运行时能够提供真实的可用模型信息；
- 允许 Skill 在目标项目中维护 `.codex/` 配置；
- 目标项目能提供由 pyenv 管理、Python 3.11 或更高版本的虚拟环境，用于运行只读验证器。

如果需求歧义会改变团队形态，Skill 会返回 `BLOCKED_BY_REQUIREMENTS`，不会先猜测需求再写配置。

## 安装

### 作为本地 Skill 使用

克隆仓库后，把完整的 `skills/construct-subagent/` 目录复制到 Codex 的用户级 Skill 目录：

```bash
git clone https://github.com/KakaTelnet/Construct-Subagent.git
mkdir -p ~/.agents/skills
cp -R Construct-Subagent/skills/construct-subagent ~/.agents/skills/
```

Codex 会从 `$HOME/.agents/skills` 发现用户级 Skill。如果安装后没有立即出现，请重启 Codex。也可以把该目录放入目标仓库的 `.agents/skills/`，让 Skill 只对该仓库生效。

### 作为 Plugin 使用

仓库根目录已经提供 `.codex-plugin/plugin.json`，可以接入本地、仓库或团队 Plugin marketplace。具体接入方式参见 OpenAI 官方的 [Package your plugin](https://developers.openai.com/plugins/build/plugins) 文档。

## 快速开始

在**需要配置 Subagent 团队的目标项目根目录**打开 Codex，然后输入：

```text
使用 $construct-subagent，根据这个项目当前的需求、代码和验证约束，构建最小充分的 Codex Subagent 团队。
```

也可以附加成本、质量或并发偏好，例如：

```text
使用 $construct-subagent 为当前项目构建团队。优先控制成本；只读探索和重复测试尽量使用低成本模型，高风险审查保留强模型，并发上限为 3。
```

Skill 随后会：

1. 读取适用的 `AGENTS.md`、Git 状态、产品/技术/验证文档和现有 Agent 配置；
2. 检查需求是否足以决定团队形态；
3. 从当前运行时建立可验证的模型 Registry；
4. 生成 Project Execution Profile，并推导最小充分角色；
5. 定义每个角色的职责、边界、默认模型、升级条件、权限、输入输出和并行规则；
6. 对账并最小化修改项目配置；
7. 运行验证器，并再次对账以确认幂等性。

## 生成结果

根据项目需要，Skill 可能维护以下内容：

| 文件 | 作用 |
| --- | --- |
| `.codex/agent-team.toml` | 团队事实源，记录项目执行画像、模型、角色、成本和编排规则 |
| `.codex/agents/*.toml` | Codex 原生自定义 Agent 定义 |
| `.codex/config.toml` 的 `[agents]` | Agent 启用状态和并发上限；不会重写其他设置 |
| `AGENTS.md` 受控标记块 | 仅保存需要长期生效的协作 Gate |
| `.codex/agents/retired/*.toml.retired` | 已退役但可恢复的受管 Agent |

完成报告会给出：

- `AGENT_TEAM_READY` 或明确的 BLOCKED 状态；
- 每个角色的 `CREATE` / `UPDATE` / `KEEP` / `RETIRE` 动作；
- 默认模型、升级模型、sandbox、职责和调用时机；
- 中央协调、失败升级、并行和串行规则；
- 模型可用性、运行时权限和配置一致性的独立验证结果；
- 实际写入的文件及运行过的验证命令。

## 何时不应该使用

以下工作不属于本 Skill：

- 定义产品需求或替用户解决重大需求歧义；
- 完成整套技术架构设计；
- 把需求拆成实施 Task；
- 编写业务代码、执行产品测试或给出最终验收结论；
- 在没有当前模型可用性证据时猜测模型配置。

这些工作应该先由相应的产品、架构、Task Engineering 或开发流程完成，再使用 `construct-subagent` 配置执行团队。

## 验证器

Skill 包含只读验证器 `skills/construct-subagent/scripts/validate_team.py`。它会联合检查团队 Manifest、Agent TOML、Skill 路径、模型分配、升级强度、文件所有权、项目并发配置和父线程实时权限。

验证器要求 Python 3.11+。模型列表、sandbox 和 approval policy 必须来自当前运行时，不能从已经生成的 Manifest 反向复制。缺少这些外部证据时，即使配置本身可以解析，也不能得到就绪状态。

## 开发与贡献

贡献边界、虚拟环境要求和验证命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。

## 许可证

本项目采用双重授权：

- 开源版本使用 [AGPL-3.0-only](LICENSE)；
- 需要闭源集成、闭源再分发或合同支持的组织，可以申请[独立商业许可证](COMMERCIAL-LICENSE.md)。

商业使用本身不要求购买商业许可证；完整遵守 AGPL 即可免费商用。Skill 在目标项目中生成的配置，不会仅因“由本项目生成”而自动适用 AGPL。

Copyright (C) 2026 KakaTelnet and contributors.

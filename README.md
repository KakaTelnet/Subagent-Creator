# construct-subagent

`construct-subagent` 是一个面向 Codex 项目的 Skill-only Plugin。它分析项目执行特征，构建最小充分的项目级 Subagent 团队，并把边界清楚、风险较低的任务路由给成本更低的模型。

该 Skill 只配置团队基础设施，不负责产品定义、完整技术架构、业务编码或最终验收。

## 仓库结构

```text
.codex-plugin/plugin.json            Codex Plugin manifest
skills/construct-subagent/           可安装的 Skill 包
  SKILL.md                            Skill 入口与工作流
  agents/openai.yaml                  Codex UI 元数据
  references/agent-team-contract.md   团队配置契约
  scripts/validate_team.py            生成结果验证器
tests/                                仓库级回归测试
scripts/validate_plugin.py             Plugin manifest 兼容性校验器
requirements-dev.txt                  CI 校验依赖
.python-version                       pyenv 的贡献者默认 Python 版本
pyproject.toml                        Python 最低版本等机器可读元数据
```

## 使用

通过 Codex 的本地 Plugin 工作流加载本仓库，或把 `skills/construct-subagent/` 作为独立 Skill 安装。调用时使用：

```text
Use $construct-subagent to design and configure the minimal sufficient project-specific Codex subagent team.
```

Skill 会先检查需求是否就绪、当前账户真实可用的模型，以及父线程当前 sandbox/approval，再决定角色、默认模型、升级路径、权限和并发关系。报告会把 Agent 配置默认权限、父线程实时权限和提示词行为边界分开；只有全部验证通过时才返回 `AGENT_TEAM_READY`。

## Python 兼容性

验证器和仓库测试要求 Python 3.11 或更高版本，因为验证器使用标准库 `tomllib`。`pyproject.toml` 声明最低版本为 3.11；`.python-version` 将贡献者的 pyenv 默认版本固定为 3.13.9，但它不是最低版本约束。CI 同时在 Python 3.11 和 3.13 上运行完整校验。

被检查的目标项目可以使用更低版本的 Python。此时应使用独立的、由 pyenv 管理的 Python 3.11+ 虚拟环境运行只读验证器，不需要改变目标应用的运行时或依赖。

## 开发验证

项目 Python 命令必须在 pyenv 创建的虚拟环境中执行：

```bash
source ./venv/bin/activate
which python3
which pip3
python3 --version
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
agentskills validate skills/construct-subagent
python3 scripts/validate_plugin.py .
python3 skills/construct-subagent/scripts/validate_team.py --help
```

提交前还应使用 Codex 自带的 `skill-creator` 与 `plugin-creator` 验证器分别检查 Skill 包和 Plugin 根目录。

## 授权方式

本项目采用双重授权：

- 开源授权：[`AGPL-3.0-only`](LICENSE)。个人和企业均可使用、修改及分发，但必须遵守 AGPL 的源码开放、许可证保留和网络交互等义务。
- 商业授权：无法或不希望遵守 AGPL、需要闭源集成、闭源再分发或合同支持的组织，可以申请[独立商业许可证](COMMERCIAL-LICENSE.md)。

商业使用本身不强制购买商业许可证；完整遵守 AGPL 即可免费商用。运行本 Skill 生成的项目配置不会仅因“由本项目生成”而自动适用 AGPL；若生成内容本身复制或改编了本项目中受保护的实质性内容，则仍可能受到 AGPL 约束。

Copyright (C) 2026 KakaTelnet and contributors.

贡献方式参见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题参见 [SECURITY.md](SECURITY.md)。

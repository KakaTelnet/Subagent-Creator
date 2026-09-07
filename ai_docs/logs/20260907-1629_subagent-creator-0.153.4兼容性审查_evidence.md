# Codex CLI 0.153.4 兼容性审查证据

COMPATIBILITY_STATUS: PASS

审查时间：2026-09-07（Asia/Shanghai）

## 被测宿主

- 可执行文件：`/Applications/ChatGPT.app/Contents/Resources/codex`
- 版本：`codex-cli 0.153.4`
- 二进制 SHA-256：`a30ec314bbd0e3721632234d07db7c99855db3b9f1e32dbe8c791947f07e7629`
- 实际功能开关：`multi_agent stable true`；`multi_agent_v2 stable false`
- 完整 CLI/功能输出：`20260907-1629_Subagent端到端验收_SC-E2E-20260907-162952_evidence/E0_host_cli.txt`

## 官方实现与文档核对

审查了官方 Subagents 文档、AGENTS.md 文档，以及官方 `rust-v0.153.4` 源码和 Schema：

- [官方 Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)：自定义 Agent 文件位于 `.codex/agents/`；官方字段包含 `name`、`description`、`developer_instructions`，并说明角色配置与父会话运行时权限的关系。
- [官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：确认新运行/会话启动时构建项目指令链，支持本方案对持久接线的新会话验证。
- [Codex 0.153.4 config 实现](https://raw.githubusercontent.com/openai/codex/rust-v0.153.4/codex-rs/core/src/config/mod.rs)：确认 `untrusted` 已不再支持；确认显式 `[features.multi_agent_v2]` 并发上限包含主线程，而 `[agents]` 上限按生成子 Agent 计数。
- [Codex 0.153.4 Agent role 实现](https://raw.githubusercontent.com/openai/codex/rust-v0.153.4/codex-rs/core/src/agent/role.rs)：确认角色覆盖字段包含模型、effort、features、skills 等，但没有把 `sandbox_mode` 作为角色覆盖字段；角色生效时仍受父会话运行时权限配置约束。
- [Codex 0.153.4 官方 Schema](https://raw.githubusercontent.com/openai/codex/rust-v0.153.4/codex-rs/core/config.schema.json)：确认当前 Agent/agents、审批策略、V2 并发、sandbox 和 Skill 字段的原生形状。

## 最小适配

适配文件：

- `skills/subagent-creator/scripts/validate_team.py`
- `skills/subagent-creator/references/runtime-readiness.md`
- `skills/subagent-creator/references/agent-team-contract.md`
- `skills/subagent-creator/references/team-design.md`
- `tooling/tests/test_validate_team.py`
- `tooling/tests/test_repository_layout.py`

适配内容：

1. 将审查窗口从 `0.147.x` 扩展到有官方实现证据覆盖的 `0.153.x`，并新增 `0.153.0+` 对 `untrusted` 审批策略的拒绝；不是仅修改上限。
2. 将审批策略按运行时版本选择：旧窗口保留 `untrusted`，当前版本只接受 `granular`、`never`、`on-request`，并在报告中输出 `accepted_approval_policies`。
3. 对显式启用的 `features.multi_agent_v2` 校验并发值必须等于 Manifest 子 Agent 上限加一，避免主线程计数口径不一致；不改写用户配置。
4. 在契约和设计文档中明确：0.153.4 的角色 `sandbox_mode` 是配置声明，不足以证明子 Agent 获得独立 OS sandbox；没有可信宿主观测时，混合 sandbox 运行就绪保持未验证/阻断。

## 验证结果

- `pip3 show skills-ref`：通过，见 `E0_static_checks.txt`。
- 单元测试：`Ran 105 tests ... OK`。
- `agentskills validate skills/subagent-creator`：通过。
- `tooling/scripts/validate_plugin.py .`：通过。
- `tooling/scripts/check_official_codex_schema.py`：通过。
- `tooling/scripts/check_official_plugin_schema.py`：通过。
- `git diff --check`：通过。
- 完整输出：`20260907-1629_Subagent端到端验收_SC-E2E-20260907-162952_evidence/E0_static_checks.txt`。

未修改全局配置，未安装/升级/降级客户端，未新增依赖，未 commit/push。原始 SC-E2E-01 BLOCKED 报告保持不变。

# Goal Execution Handoff

Use this handoff only after a project-scoped `CREATE` or `UPDATE` has produced
a managed team and reached `AGENT_TEAM_CONFIGURATION_READY` or a stronger
readiness state. The implementation plan must already be authoritative and
stable enough to execute.

Do not emit this handoff for `EXPLAIN`, `AUDIT`, global role libraries,
`NO_AGENT_TEAM_NEEDED`, or any blocked result. Do not start the Goal or execute
product work as part of `subagent-creator`; return the template as the user's
next-step prompt.

Replace `<实现计划文件路径>` only when one authoritative plan path is known.
Otherwise preserve the placeholder and tell the user to replace it. Keep every
other instruction intact unless a project instruction or current user request
requires a stricter boundary.

The `/goal` behavior and enablement syntax below follow the official OpenAI
[Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals) guidance.

## Copyable prompt

```text
/goal 严格按照 <实现计划文件路径> 完成全部范围内的实现工作，持续推进，直到计划规定的所有验收条件通过、所有必需测试通过、没有剩余必做任务，并提交最终验证报告。

开始执行前：

1. 读取当前生效的 AGENTS.override.md 或 AGENTS.md。
2. 读取 .codex/agent-team.toml 和全部 active Agent 定义。
3. 读取 <实现计划文件路径>，以及计划引用的需求、架构、接口契约和测试资料。
4. 将实现计划视为执行事实来源，不重新定义需求，不自行扩展范围。
5. 检查每个 Agent 的 invoke_when，并将计划任务映射到合适的 Subagent。
6. 汇报本 GOAL 的目标、停止条件、任务依赖顺序、Subagent 分工和验证路径，然后立即开始执行。

Subagent 调度要求：

- 当 invoke_when 匹配时，主 Agent 必须调用对应 Subagent；如果不调用，必须说明具体原因。
- 每次委派只包含一个独立目标，并明确允许修改的文件、前置条件、禁止事项、验收命令和返回格式。
- 只并行执行文件写入不冲突、共享状态不冲突、测试资源不冲突且能够独立验收的任务。
- 修改同一文件、公共接口、数据库 Schema、依赖文件或共享测试设施的任务必须串行。
- Subagent 不得再次派生 Subagent。
- Subagent 不得 commit、push、创建 PR、merge 或发布。
- Subagent 遇到需求冲突、权限不足、验证失败或超出范围时，必须把证据和阻塞原因返回主 Agent。
- 主 Agent 负责整合所有结果、检查 diff、运行父级回归测试并作出最终判断。

推进要求：

- 按实现计划的依赖顺序和检查点持续推进。
- 每完成一个检查点，更新任务状态和 GOAL 进度，并记录对应的代码、测试和验证证据。
- 遇到普通测试失败时，在范围内诊断、修复并重新验证，不要因为一次失败停止整个 GOAL。
- 只有遇到无法从项目事实解决、且会实质改变需求、权限、范围或架构的决策时，才暂停并请求用户输入。
- 不得因为 Token、回合结束或部分测试通过而提前宣布完成。
- 未经当前用户明确授权，不得 commit、push、merge、部署或发布。

GOAL 完成条件：

- 实现计划中所有范围内任务均为 Done；
- 每项验收标准都有对应通过证据；
- 聚焦测试和完整回归测试全部通过；
- Skill、静态检查、构建或项目规定的其他门禁全部通过；
- 主 Agent 已审查最终 diff 和工作树范围；
- 没有遗漏的必做任务或未说明的阻塞项；
- 最终报告列出完成内容、Subagent 实际调用情况、变更文件、验证命令、验证结果和剩余风险。

只有满足以上全部条件，才能将 GOAL 标记为 complete；否则保持 GOAL active，或在确实无法继续时报告精确 blocker。
```

If `/goal` is unavailable, tell the user to enable it with
`codex features enable goals` or this Codex configuration:

```toml
[features]
goals = true
```

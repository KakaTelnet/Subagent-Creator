# Representative project instructions

<!-- subagent-creator:start -->
## Agent Team Runtime Contract

- At the start of any repository task that may involve exploration, implementation, testing, debugging, review, or other work described by a project Subagent, read `.codex/agent-team.toml` before deciding whether to delegate.
- Evaluate every active `[[agents]].invoke_when` against the current task before the main Agent performs matching work.
- Treat its `[orchestration]` and `[[agents]]` entries as the source of truth for invocation, parallel or serial constraints, model escalation, and failure routing.
- When an Agent's `invoke_when` condition matches and delegation is permitted, the main Agent must delegate to that role or state why it is unsafe or unnecessary.
- The main Agent owns dispatch and final decisions; Subagents return results and do not dispatch follow-up work.
- Product requirements may only be changed by the main Agent with user authority.
<!-- subagent-creator:end -->

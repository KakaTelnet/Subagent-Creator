# Repository Agent Guidance

## Scope

- Treat `skills/construct-subagent/` as the complete distributable Skill package.
- Keep repository documentation, CI, and regression tests outside the Skill package.
- Keep runtime references one level below `SKILL.md` in `references/`.

## Change rules

- Preserve the Skill's requirement, model-registry, ownership, and idempotency gates.
- Update the contract, validator, and tests together when changing the generated team schema.
- Do not commit generated target-project `.codex/` files, virtual environments, caches, or temporary output.
- Use a pyenv-managed Python through `./venv`, verify `python3` and `pip3` paths before execution, and keep permanent tests under `tests/`.

## Required checks

- Run the repository unit tests.
- Validate `skills/construct-subagent/` with the pinned `skills-ref` package's `agentskills` command.
- Validate the repository root with `scripts/validate_plugin.py`.

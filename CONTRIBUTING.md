# Contributing

感谢参与 `construct-subagent`。

## 变更边界

- 将可安装、运行时必需的内容放在 `skills/construct-subagent/`。
- 将仓库级回归测试放在 `tests/`，不要把测试或开发记录塞进 Skill 包。
- 保持 `SKILL.md` 精简；详细 schema、示例和长期契约放入 `references/`。
- 不要提交 `venv/`、缓存、临时输出或目标项目生成的 `.codex/` 文件。
- 修改 Agent Team schema 时，同步更新契约、验证器和回归测试。

## 验证

在 pyenv 管理的虚拟环境中运行：

```bash
source ./venv/bin/activate
which python3
which pip3
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 skills/construct-subagent/scripts/validate_team.py --help
```

Pull Request 应说明行为变化、兼容性影响和实际运行的验证命令。涉及模型或 Codex 配置 schema 的变化，还应附当前官方文档依据。

## 贡献授权

项目公开版本以 `AGPL-3.0-only` 发布，同时允许项目维护者为不希望遵守 AGPL 的用户提供独立商业许可证。为保证项目能够持续采用双重授权，提交贡献即表示你确认：

1. 你拥有该贡献的版权，或已获得足够授权提交该贡献；
2. 你保留对贡献的版权；
3. 你向 KakaTelnet 和本项目维护者授予永久、全球性、非独占、免版税且不可撤销的权利，允许其使用、复制、修改、公开展示、公开执行、分发、再许可，并将该贡献同时置于 `AGPL-3.0-only` 或独立商业许可条款之下；
4. 你理解公开版本仍将按照 `AGPL-3.0-only` 向社区提供。

如果你没有权利授予上述许可，请不要提交该贡献。重大企业贡献或权属复杂的贡献，维护者可以要求另行签署 Contributor License Agreement（CLA）。

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

提交贡献即表示你确认拥有提交权，并同意项目继续以 `AGPL-3.0-only` 和独立商业许可证双重授权该贡献。贡献者保留版权；普通贡献无需额外签署 CLA 或 DCO。只有重大企业贡献或权属复杂时，维护者才可能要求补充授权文件。

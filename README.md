# 表格批量 AI 处理器

面向 Codex/SkillHub 的表格批量 AI 处理技能。支持 CSV、JSONL、模板预检、限速、有限重试、逐行落盘和断点续跑。

```powershell
python scripts/batch_process.py --input data.csv --output result.csv --template "总结：{text}" --dry-run
```

实时调用必须额外提供模型、环境变量中的密钥和 `--confirm-live-run`。详见 `SKILL.md`。

## 测试

```powershell
python -m unittest discover -s scripts -p "test_*.py" -v
```

MIT License

# Training Operation Copilot v0.1

当前开发范围严格限定为 Engineering Spec V2.0 的单项目、线下培训模板 MVP。

## 当前已实现

- Offline Training v1.0 初始化数据加载
- 项目创建
- 根据 `event_date + milestone.offset_days` 实例化 64 个项目任务
- 模板、里程碑、任务和风险规则的关系数据库模型

## 本地运行

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

接口文档默认位于 `http://127.0.0.1:8000/docs`。

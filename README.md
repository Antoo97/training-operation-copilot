# Training Operation Copilot v0.2

当前代码已完成确认范围内的 v0.2 Phase 1–5，同时保留并兼容 v0.1 单次线下培训能力。

## 当前已实现

- Offline Training v1.0 初始化数据加载与原 20 个节点、64 个任务、9 条风险规则
- Program → 可选 Cohort → Activity 项目层级；旧 Project 自动兼容迁移为同名 Program 下唯一 Activity
- 线下培训 Activity 继续实例化标准节点与任务；其他 Activity 可不使用模板
- 任务五种状态、开始/截止日期、负责人、完成标准、备注、质量评分与复盘反馈
- 子任务、自动/人工进度切换、批量完成、项目动态与轻量使用者署名
- Activity 预算申请、Program 预算聚合、精确金额计算与参考价格快照
- 常见费用参考价格库、轻量物料需求、宣传需求和全局需求协同筛选
- Program 运营 Dashboard、届别汇总、未来 7 天重点、跨项目待办和年度培训地图
- 六类确定性预警、Offline Training 原 9 条规则适配、预警处理和可解释健康度
- SOP/资料链接、项目复盘、中文 Excel 和全天 `.ics` 日历导出
- Alembic 数据库版本管理和 Render 启动时自动升级

## 本地运行

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m app.migrate
.venv/bin/uvicorn app.main:app --reload
```

工作台默认位于 `http://127.0.0.1:8000/`，接口文档位于 `http://127.0.0.1:8000/docs`。

## 测试

```bash
.venv/bin/pytest
```

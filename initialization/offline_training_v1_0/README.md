# Offline Training v1.0 初始化数据说明

数据来源：`Offline_Training_Template_v1.0_System_Initialization_Spec.md`。

本目录仅做结构化映射，没有新增里程碑、任务或风险规则，也没有修改源文件中的业务文本。

## 文件

- `template.json`：模板元数据。
- `milestones.json`：20 个里程碑。
- `template_tasks.json`：64 个模板任务。
- `risk_rules.json`：9 条明确编号的风险规则。

## 映射规则

- `deadline = project.event_date + milestone.offset_days`。
- 模板任务通过 `milestone_id` 继承里程碑期限。
- 只有源文件明确写为 `Risk Rule` 的内容进入 `risk_rules.json`。
- 普通 `Risk` 文本写入里程碑的 `risk_if_missing`，没有擅自升级成可执行规则。
- `M14` 所在阶段明确为 `T`，因此 `offset_days` 映射为 `0`。

## Business Confirmation Update

已根据 `Offline_Training_Template_v1.0_Business_Confirmation_Update.md` 更新：

1. M19 的 `offset_days` 为 14，M20 为 21。
2. 已确认的 milestone 及其 template tasks 写入对应 `required` 值。
3. 所有风险规则使用 `severity_strategy: "dynamic"`，`severity` 保留为 `null`，运行时动态计算。
4. 9 条风险规则均已补充业务确认的 `recommended_action`。

M02、M08、M12、M14 及其任务未在 Business Confirmation Update 中指定 required 值，因此继续保留为 `null`，没有自行补全。

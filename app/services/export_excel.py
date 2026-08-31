from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import select

from app.models import Milestone, ProjectActivityLog, TemplateTask
from app.services.dashboard import dashboard


HEADER_FILL = PatternFill("solid", fgColor="176F61")
SECTION_FILL = PatternFill("solid", fgColor="E8F4F1")
THIN = Side(style="thin", color="DCE4E7")


def add_sheet(wb, title, headers, rows):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(bottom=THIN)
    for column in ws.columns:
        width = min(42, max(10, max(len(str(c.value or "")) for c in column) + 2))
        ws.column_dimensions[column[0].column_letter].width = width
    return ws


def t_label(offset: int | None) -> str:
    if offset is None or offset == 0:
        return "T"
    return f"T+{offset}" if offset > 0 else f"T{offset}"


def build_operations_workbook(db, program):
    summary = dashboard(db, program.id)
    wb = Workbook()
    overview = wb.active
    overview.title = "运营总览"
    overview.sheet_view.showGridLines = False
    overview.merge_cells("A1:F1")
    overview["A1"] = f"{program.name}｜项目运营总览"
    overview["A1"].font = Font(size=18, bold=True, color="FFFFFF")
    overview["A1"].fill = HEADER_FILL
    overview["A1"].alignment = Alignment(vertical="center")
    overview.row_dimensions[1].height = 30
    metrics = [
        ("项目负责人", program.owner_name or "未填写", "项目周期", f"{program.start_date} 至 {program.end_date}", "当前阶段", program.current_phase or "未设置"),
        ("任务进度", summary["progress"] / 100, "时间进度", summary["time_progress"] / 100, "健康度", summary["health"]["label"]),
        ("培养活动", summary["outcomes"]["activity_count"], "覆盖人数", summary["outcomes"]["participant_count"], "开放预警", summary["health"]["open_alert_count"]),
        ("预计预算", float(summary["specialty"]["budget"]["estimated_total"]), "预算通过进度", summary["specialty"]["budget"]["progress"] / 100, "未来7天重点", len(summary["focus"])),
    ]
    for row in metrics:
        overview.append(row)
    for row in range(2, 6):
        for col in (1, 3, 5):
            overview.cell(row, col).font = Font(bold=True, color="176F61")
            overview.cell(row, col).fill = SECTION_FILL
        for col in range(1, 7):
            overview.cell(row, col).border = Border(bottom=THIN)
            overview.cell(row, col).alignment = Alignment(vertical="center", wrap_text=True)
    overview["B3"].number_format = "0%"; overview["D3"].number_format = "0%"
    overview["B5"].number_format = "¥#,##0.00"; overview["D5"].number_format = "0%"
    overview.append([])
    overview.append(["培养活动", "活动类型", "开始日期", "结束日期", "负责人", "任务完成度"])
    header_row = overview.max_row
    for cell in overview[header_row]:
        cell.font = Font(bold=True, color="FFFFFF"); cell.fill = HEADER_FILL
    activity_dash = {item["id"]: item for item in summary["activities"]}
    for activity in program.activities:
        item = activity_dash.get(activity.id, {})
        overview.append([activity.name, activity.activity_type or activity.type, activity.start_date, activity.end_date or activity.event_date, activity.owner_name, item.get("progress", 0) / 100])
        overview.cell(overview.max_row, 6).number_format = "0%"
    for column, width in {"A":28,"B":18,"C":14,"D":14,"E":22,"F":14}.items():
        overview.column_dimensions[column].width = width
    overview.freeze_panes = "A7"

    milestone_templates = {item.id: item for item in db.scalars(select(Milestone)).all()}
    task_templates = {item.id: item for item in db.scalars(select(TemplateTask)).all()}
    detail_rows = []
    for activity in program.activities:
        milestone_map = {item.id: item for item in activity.milestones}
        for task in sorted(activity.tasks, key=lambda item: (item.project_milestone.sort_order if item.project_milestone else 999, item.sort_order)):
            milestone = milestone_map.get(task.project_milestone_id)
            template_milestone = milestone_templates.get(milestone.template_milestone_id) if milestone else None
            template_task = task_templates.get(task.template_task_id)
            base = [activity.name, t_label(template_milestone.offset_days if template_milestone else None), milestone.code if milestone else "", milestone.name if milestone else task.milestone_name, milestone.start_date if milestone else task.start_date, milestone.deadline if milestone else task.deadline]
            detail_rows.append(base + ["主任务", template_task.code if template_task else "自定义", task.title, "", task.start_date, task.deadline, task.status, task.effective_progress_percent / 100, task.owner, task.quality_score, task.completion_criteria, task.notes, task.progress_note, task.retrospective_note])
            for sub in sorted((item for item in task.subtasks if item.status != "cancelled"), key=lambda item: item.sort_order):
                detail_rows.append(base + ["分支任务", template_task.code if template_task else "自定义", task.title, sub.title, sub.start_date, sub.deadline, sub.status, sub.progress_percent / 100, sub.owner, None, None, sub.notes, None, None])
    detail = add_sheet(wb, "节点任务明细", ["活动", "模板T日期", "节点代码", "节点名称", "节点开始", "节点截止", "层级", "任务代码", "主任务", "分支任务", "工作开始", "工作截止", "状态", "进度", "负责人", "完成质量(1-5)", "完成标准", "任务详情/备注", "进度备注", "复盘反馈"], detail_rows)
    for row in range(2, detail.max_row + 1):
        detail.cell(row, 14).number_format = "0%"
        if detail.cell(row, 7).value == "主任务":
            for cell in detail[row]:
                cell.fill = SECTION_FILL
                if cell.column in {1, 3, 4, 7, 9}: cell.font = Font(bold=True)

    add_sheet(wb, "预算", ["活动", "状态", "负责人", "预计申请日", "预计总额", "备注"], [[x.activity.name if x.activity else "项目级", x.status, x.owner_name, x.planned_apply_date, float(x.estimated_total), x.notes] for x in program.budget_sheets])
    add_sheet(wb, "物料", ["活动", "物料", "数量", "规格", "负责人", "内容截止", "预计交付", "状态", "计入预算", "备注"], [[x.activity.name if x.activity else "项目级", x.name, float(x.quantity) if x.quantity is not None else None, x.specification, x.owner_name, x.content_due_date, x.expected_delivery_date, x.status, "是" if x.include_in_budget else "否", x.notes] for x in program.material_requirements])
    add_sheet(wb, "宣传", ["活动", "内容类型", "形式", "数量", "负责人", "开始日期", "制作截止", "预计发布", "状态", "备注"], [[x.activity.name if x.activity else "项目级", x.content_type, x.format, x.quantity, x.owner_name, x.start_date, x.expected_completion_date, x.publish_date, x.status, x.notes] for x in program.publicity_requirements])
    logs = db.scalars(select(ProjectActivityLog).where(ProjectActivityLog.program_id == program.id).order_by(ProjectActivityLog.occurred_at)).all()
    add_sheet(wb, "项目动态", ["时间", "记录人", "模块", "摘要"], [[x.occurred_at.replace(tzinfo=None) if x.occurred_at.tzinfo else x.occurred_at, x.actor_name, x.module, x.summary] for x in logs])
    output = BytesIO(); wb.save(output); return output.getvalue()

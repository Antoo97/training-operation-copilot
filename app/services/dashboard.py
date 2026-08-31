from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Alert, Cohort, MaterialRequirement, Program, Project, ProjectActivityLog, ProjectTask, PublicityRequirement


DONE_SPECIALTY = {"done", "published", "approved"}


def percent(done: int, total: int) -> int:
    return round(done * 100 / total) if total else 0


def time_progress(start: date, end: date, today: date) -> int:
    if end <= start:
        return 100 if today >= end else 0
    return max(0, min(100, round((today - start).days * 100 / (end - start).days)))


def load_program(db: Session, program_id: str) -> Program | None:
    return db.scalar(select(Program).options(
        selectinload(Program.activities).selectinload(Project.tasks).selectinload(ProjectTask.subtasks),
        selectinload(Program.activities).selectinload(Project.milestones),
        selectinload(Program.cohorts).selectinload(Cohort.activities).selectinload(Project.tasks),
        selectinload(Program.budget_sheets), selectinload(Program.material_requirements),
        selectinload(Program.publicity_requirements), selectinload(Program.alerts),
    ).where(Program.id == program_id))


def program_progress(program: Program) -> int:
    tasks = [task for activity in program.activities if activity.status != "archived" for task in activity.tasks if task.status != "cancelled"]
    return round(sum(task.effective_progress_percent for task in tasks) / len(tasks)) if tasks else 0


def activity_progress(activity: Project) -> int:
    tasks = [task for task in activity.tasks if task.status != "cancelled"]
    return activity.progress_override if activity.progress_override is not None else (round(sum(t.effective_progress_percent for t in tasks) / len(tasks)) if tasks else 0)


def health(program: Program) -> dict:
    open_alerts = [a for a in program.alerts if a.status in {"open", "acknowledged"}]
    level = "risk" if any(a.severity == "risk" for a in open_alerts) else "attention" if open_alerts else "normal"
    return {"code": level, "label": {"normal": "正常", "attention": "需要关注", "risk": "风险"}[level], "open_alert_count": len(open_alerts), "reasons": [a.title for a in open_alerts[:5]]}


def next_item(program: Program, today: date) -> dict | None:
    candidates = []
    for activity in program.activities:
        for milestone in activity.milestones:
            if milestone.status == "active" and milestone.deadline >= today:
                candidates.append((milestone.deadline, "关键节点" if milestone.required else "节点", milestone.name, activity.name))
    if not candidates:
        return None
    due, kind, title, activity = min(candidates)
    return {"date": due, "type": kind, "title": title, "activity_name": activity}


def specialty(program: Program) -> dict:
    budgets = list(program.budget_sheets)
    materials = [x for x in program.material_requirements if x.status != "cancelled"]
    publicity = list(program.publicity_requirements)
    budget_done = sum(x.status == "approved" for x in budgets)
    return {
        "budget": {"total": len(budgets), "done": budget_done, "progress": percent(budget_done, len(budgets)), "estimated_total": float(sum((x.estimated_total for x in budgets), Decimal(0)))},
        "material": {"total": len(materials), "done": sum(x.status == "done" for x in materials), "progress": percent(sum(x.status == "done" for x in materials), len(materials))},
        "publicity": {"total": len(publicity), "done": sum(x.status in DONE_SPECIALTY for x in publicity), "progress": percent(sum(x.status in DONE_SPECIALTY for x in publicity), len(publicity))},
        "activity": {"total": len(program.activities), "done": sum(x.status in {"done", "completed"} for x in program.activities), "progress": percent(sum(x.status in {"done", "completed"} for x in program.activities), len(program.activities))},
    }


def focus_items(program: Program, today: date, days: int = 7) -> list[dict]:
    end = today + timedelta(days=days)
    items = []
    for activity in program.activities:
        for milestone in activity.milestones:
            if milestone.status == "active" and milestone.required and today <= milestone.deadline <= end:
                items.append({"date": milestone.deadline, "type": "关键节点", "title": milestone.name, "activity_name": activity.name, "required": True})
        for task in activity.tasks:
            if task.status not in {"done", "cancelled"} and today <= task.deadline <= end and (task.required or (task.deadline - today).days <= 3):
                items.append({"date": task.deadline, "type": "关键任务" if task.required else "临期任务", "title": task.title, "activity_name": activity.name, "required": bool(task.required)})
    return sorted(items, key=lambda x: (x["date"], not x["required"], x["title"]))


def dashboard(db: Session, program_id: str, today: date | None = None) -> dict | None:
    program = load_program(db, program_id)
    if not program:
        return None
    today = today or date.today()
    tasks = [t for a in program.activities for t in a.tasks if t.status != "cancelled"]
    result = {
        "id": program.id, "name": program.name, "program_type": program.program_type,
        "owner_name": program.owner_name, "current_phase": program.current_phase,
        "start_date": program.start_date, "end_date": program.end_date,
        "progress": program_progress(program), "time_progress": time_progress(program.start_date, program.end_date, today),
        "health": health(program), "next_item": next_item(program, today), "specialty": specialty(program),
        "outcomes": {"activity_count": len(program.activities), "completed_activity_count": sum(a.status in {"done", "completed"} for a in program.activities), "participant_count": program.participant_count or sum(c.participant_count for c in program.cohorts), "task_count": len(tasks), "completed_task_count": sum(t.status == "done" for t in tasks)},
        "activities": [{"id": a.id, "name": a.name, "type": a.activity_type or a.type, "start_date": a.start_date, "end_date": a.end_date or a.start_date, "status": a.status, "progress": activity_progress(a), "owner_name": a.owner_name} for a in program.activities],
        "cohorts": [{"id": c.id, "name": c.name, "business_unit": c.business_unit, "participant_count": c.participant_count, "start_date": c.start_date, "end_date": c.end_date, "status": c.status, "graduated": c.graduated, "progress": c.progress_override if c.progress_override is not None else (round(sum(activity_progress(a) for a in c.activities) / len(c.activities)) if c.activities else 0), "completed_activity_count": sum(a.status in {"done", "completed"} for a in c.activities), "activity_count": len(c.activities), "next_activity": next(({"id": a.id, "name": a.name, "start_date": a.start_date} for a in sorted(c.activities, key=lambda a: a.start_date) if a.start_date >= today), None)} for c in program.cohorts],
        "focus": focus_items(program, today),
    }
    result["recent_logs"] = [{"occurred_at": x.occurred_at, "actor_name": x.actor_name, "summary": x.summary} for x in db.scalars(select(ProjectActivityLog).where(ProjectActivityLog.program_id == program.id).order_by(ProjectActivityLog.occurred_at.desc()).limit(10)).all()]
    return result

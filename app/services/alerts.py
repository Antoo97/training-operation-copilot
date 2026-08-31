from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, RiskRule
from app.services.dashboard import load_program, program_progress, specialty, time_progress

THRESHOLDS = {"due_soon_days": 3, "stale_days": 7, "schedule_lag_points": 20, "specialty_lag_points": 25}


def candidate(code, kind, severity, title, reason, action, entity_type, entity_id, activity_id=None, data=None):
    return {"rule_code": code, "alert_type": kind, "severity": severity, "title": title, "reason": reason, "recommended_action": action, "source_entity_type": entity_type, "source_entity_id": entity_id, "activity_id": activity_id, "current_data_json": data or {}}


def evaluate_candidates(program, today: date, template_rules: list[RiskRule] | None = None) -> list[dict]:
    rows = []
    for activity in program.activities:
        for task in activity.tasks:
            if task.status in {"done", "cancelled"}:
                continue
            days = (task.deadline - today).days
            if days < 0:
                rows.append(candidate("GEN_OVERDUE", "overdue", "risk" if task.required else "attention", "任务已逾期", f"“{task.title}”已逾期 {-days} 天。", "确认阻塞原因并更新完成计划。", "task", task.id, activity.id, {"deadline": str(task.deadline), "days_overdue": -days}))
            elif days <= THRESHOLDS["due_soon_days"]:
                rows.append(candidate("GEN_DUE_SOON", "due_soon", "attention", "任务即将截止", f"“{task.title}”将在 {days} 天内截止。", "确认负责人和交付状态。", "task", task.id, activity.id, {"deadline": str(task.deadline), "days_left": days}))
            if task.required and task.status == "blocked":
                rows.append(candidate("GEN_KEY_BLOCKED", "milestone_risk", "risk", "关键任务阻塞", f"关键任务“{task.title}”处于阻塞状态。", "立即明确解除阻塞的责任人和日期。", "task", task.id, activity.id))
            updated = task.last_progress_at.date() if task.last_progress_at else activity.start_date
            if task.required and (today - updated).days >= THRESHOLDS["stale_days"]:
                rows.append(candidate("GEN_STALE", "stale_update", "attention", "关键任务长期未更新", f"“{task.title}”已 {(today-updated).days} 天未更新进度。", "请负责人更新实际进度和备注。", "task", task.id, activity.id, {"last_update": str(updated)}))
        for milestone in activity.milestones:
            days = (milestone.deadline - today).days
            open_required = [t for t in milestone.tasks if t.required and t.status not in {"done", "cancelled"}]
            if milestone.status == "active" and milestone.required and 0 <= days <= THRESHOLDS["due_soon_days"] and open_required:
                rows.append(candidate("GEN_KEY_MILESTONE", "milestone_risk", "attention", "关键节点临近", f"“{milestone.name}”临近，仍有 {len(open_required)} 项关键任务未完成。", "逐项确认关键任务交付状态。", "milestone", milestone.id, activity.id, {"deadline": str(milestone.deadline), "open_required_tasks": len(open_required)}))
    progress = program_progress(program)
    tprogress = time_progress(program.start_date, program.end_date, today)
    if program.status == "active" and tprogress - progress > THRESHOLDS["schedule_lag_points"]:
        rows.append(candidate("GEN_SCHEDULE_LAG", "schedule_lag", "attention", "项目节奏偏慢", f"时间进度 {tprogress}% 高于任务进度 {progress}%。", "检查关键路径并调整近期计划。", "program", program.id, data={"time_progress": tprogress, "task_progress": progress}))
    for name, info in specialty(program).items():
        if name == "activity" or info["total"] < 3:
            continue
        if progress - info["progress"] > THRESHOLDS["specialty_lag_points"]:
            label = {"budget": "预算", "material": "物料", "publicity": "宣传"}[name]
            rows.append(candidate(f"GEN_SPECIALTY_{name.upper()}", "specialty_lag", "attention", f"{label}专项滞后", f"{label}进度 {info['progress']}%，低于项目进度 {progress}%。", f"检查{label}未完成项并更新责任人与日期。", "program", program.id, data={"specialty_progress": info["progress"], "program_progress": progress}))
    for activity in program.activities:
        if not activity.template_id or not activity.event_date:
            continue
        milestones = {m.template_milestone_id: m for m in activity.milestones}
        for rule in template_rules or []:
            milestone = milestones.get(rule.target_milestone_id)
            if not milestone or milestone.status != "active":
                continue
            active_tasks = [t for t in milestone.tasks if t.status != "cancelled"]
            done = bool(active_tasks) and all(t.status == "done" for t in active_tasks)
            triggered = False
            if rule.trigger_type in {"milestone_incomplete_after_offset", "milestone_not_started_after_offset"}:
                trigger_date = activity.event_date + timedelta(days=int(rule.trigger_config.get("offset_days", 0)))
                triggered = today > trigger_date and (not done if rule.trigger_type == "milestone_incomplete_after_offset" else all(t.status == "todo" for t in active_tasks))
            elif rule.trigger_type == "external_dependency_fields_missing":
                triggered = today >= activity.start_date and bool(active_tasks) and any(not t.owner for t in active_tasks)
                trigger_date = milestone.deadline
            else:
                trigger_date = milestone.deadline
            if triggered:
                rows.append(candidate(rule.code, "milestone_risk", "risk" if milestone.required else "attention", rule.name, rule.source_trigger, rule.recommended_action, "milestone", milestone.id, activity.id, {"milestone": milestone.name, "trigger_date": str(trigger_date), "completed": done}))
    return rows


def evaluate(db: Session, program_id: str, today: date | None = None) -> list[Alert]:
    program = load_program(db, program_id)
    if not program:
        raise ValueError("培养项目不存在")
    now, today = datetime.now(UTC), today or date.today()
    candidates = evaluate_candidates(program, today, list(db.scalars(select(RiskRule)).all()))
    active_keys = {(x["rule_code"], x["source_entity_type"], x["source_entity_id"]) for x in candidates}
    existing = list(db.scalars(select(Alert).where(Alert.program_id == program_id)).all())
    by_key = {(x.rule_code, x.source_entity_type, x.source_entity_id): x for x in existing}
    for data in candidates:
        key = (data["rule_code"], data["source_entity_type"], data["source_entity_id"])
        alert = by_key.get(key)
        if alert:
            for field, value in data.items(): setattr(alert, field, value)
            alert.status = "open" if alert.status in {"resolved", "dismissed"} else alert.status
            alert.resolved_at = None; alert.last_detected_at = now
        else:
            db.add(Alert(id=str(uuid4()), first_detected_at=now, last_detected_at=now, status="open", program_id=program_id, **data))
    for alert in existing:
        key = (alert.rule_code, alert.source_entity_type, alert.source_entity_id)
        if alert.status in {"open", "acknowledged"} and key not in active_keys:
            alert.status = "resolved"; alert.resolved_at = now
    db.commit()
    return list(db.scalars(select(Alert).where(Alert.program_id == program_id).order_by(Alert.severity.desc(), Alert.last_detected_at.desc())).all())

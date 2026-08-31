from __future__ import annotations

from urllib.parse import unquote
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models import Project, ProjectActivityLog


def clean_actor_name(value: str | None) -> str:
    cleaned = " ".join(unquote(value or "").strip().split())
    return cleaned[:100] or "系统用户"


def add_activity_log(
    db: Session,
    *,
    program_id: str,
    activity_id: str | None,
    actor_name: str | None,
    module: str,
    action: str,
    summary: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    changes: dict | None = None,
    source: str = "system",
    is_manual_entry: bool = False,
) -> ProjectActivityLog:
    log = ProjectActivityLog(
        id=str(uuid4()),
        program_id=program_id,
        activity_id=activity_id,
        actor_name=clean_actor_name(actor_name),
        module=module,
        action=action,
        summary=summary,
        entity_type=entity_type,
        entity_id=entity_id,
        changes_json=jsonable_encoder(changes or {}),
        source=source,
        is_manual_entry=is_manual_entry,
    )
    db.add(log)
    return log


def task_program_id(db: Session, activity_id: str) -> str:
    activity = db.get(Project, activity_id)
    if activity is None or activity.program_id is None:
        raise ValueError("task activity has no program")
    return activity.program_id

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Milestone, Project, ProjectMilestone, ProjectTask, ProjectTemplate, TemplateTask
from app.schemas import ProjectCreate


class TemplateNotFoundError(ValueError):
    pass


def create_project(db: Session, payload: ProjectCreate) -> Project:
    template = db.get(ProjectTemplate, payload.template_id)
    if template is None:
        raise TemplateNotFoundError(payload.template_id)
    if payload.event_date < payload.start_date:
        raise ValueError("event_date must be on or after start_date")

    template_milestones = db.scalars(
        select(Milestone)
        .where(Milestone.template_id == payload.template_id)
        .order_by(Milestone.sort_order)
    ).all()
    template_tasks = db.scalars(
        select(TemplateTask)
        .where(TemplateTask.template_id == payload.template_id)
        .order_by(TemplateTask.milestone_id, TemplateTask.sort_order)
    ).all()

    project = Project(
        id=str(uuid4()),
        name=payload.name,
        type=template.type,
        start_date=payload.start_date,
        event_date=payload.event_date,
        status="active",
        template_id=template.id,
    )
    db.add(project)

    project_milestones: dict[str, ProjectMilestone] = {}
    for milestone in template_milestones:
        instance = ProjectMilestone(
            id=str(uuid4()),
            template_milestone_id=milestone.id,
            code=milestone.code,
            name=milestone.name,
            phase=milestone.phase,
            deadline=payload.event_date + timedelta(days=milestone.offset_days),
            required=milestone.required,
            status="active",
            sort_order=milestone.sort_order,
        )
        project.milestones.append(instance)
        project_milestones[milestone.id] = instance

    for template_task in template_tasks:
        milestone = project_milestones[template_task.milestone_id]
        project.tasks.append(
            ProjectTask(
                id=str(uuid4()),
                template_task_id=template_task.id,
                milestone_id=template_task.milestone_id,
                project_milestone=milestone,
                title=template_task.title,
                status="todo",
                deadline=milestone.deadline,
                required=template_task.required,
            )
        )

    db.commit()
    db.refresh(project)
    return project


def backfill_project_milestones(db: Session) -> None:
    """Create project milestone instances for projects created before this model existed."""
    projects = db.scalars(select(Project)).all()
    for project in projects:
        existing = {
            item.template_milestone_id: item
            for item in db.scalars(
                select(ProjectMilestone).where(ProjectMilestone.project_id == project.id)
            ).all()
            if item.template_milestone_id
        }
        template_milestones = db.scalars(
            select(Milestone)
            .where(Milestone.template_id == project.template_id)
            .order_by(Milestone.sort_order)
        ).all()
        for milestone in template_milestones:
            instance = existing.get(milestone.id)
            if instance is None:
                instance = ProjectMilestone(
                    id=str(uuid4()),
                    project_id=project.id,
                    template_milestone_id=milestone.id,
                    code=milestone.code,
                    name=milestone.name,
                    phase=milestone.phase,
                    deadline=project.event_date + timedelta(days=milestone.offset_days),
                    required=milestone.required,
                    status="active",
                    sort_order=milestone.sort_order,
                )
                db.add(instance)
                db.flush()
                existing[milestone.id] = instance
            tasks = db.scalars(
                select(ProjectTask).where(
                    ProjectTask.project_id == project.id,
                    ProjectTask.milestone_id == milestone.id,
                    ProjectTask.project_milestone_id.is_(None),
                )
            ).all()
            for task in tasks:
                task.project_milestone_id = instance.id
    db.commit()
